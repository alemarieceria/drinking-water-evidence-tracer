"""Find source PDFs through the shared archive's catalog.

The archive (a Google Shared Drive) stores each downloaded file under `raw/` and
records it in `registry/documents.csv`. This module reads that catalog, so the
application uses the archived files instead of hand-copied ones.

Check the version 1 set from the repository root:

    uv run python -m app.archive
"""

import argparse
import csv
import hashlib
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

CATALOG_FILE = Path("registry") / "documents.csv"
V1_DOCUMENT_LIST = Path(__file__).resolve().parent.parent / "data" / "v1_documents.txt"
PATH_SEPARATOR = "; "
HASH_CHUNK_BYTES = 1024 * 1024


class ArchiveError(Exception):
    """The archive or its catalog cannot supply the requested documents."""


@dataclass(frozen=True)
class ArchivedDocument:
    """One cataloged file, with the fields needed to open and cite it."""

    doc_id: str
    title: str
    library_id: str
    sdg: str
    doc_type: str
    path: Path
    sha256: str
    source_url: str


def archive_root_from_env() -> Path:
    """Return the archive folder named by the ARCHIVE_ROOT environment variable."""
    value = os.environ.get("ARCHIVE_ROOT", "").strip()
    if not value:
        raise ArchiveError(
            "ARCHIVE_ROOT is not set. Add it to .env (see .env.example)."
        )
    root = Path(value)
    if not (root / CATALOG_FILE).is_file():
        raise ArchiveError(
            f"No catalog found at {root / CATALOG_FILE}. "
            "Check ARCHIVE_ROOT and that the Shared Drive is available."
        )
    return root


def load_catalog(archive_root: Path) -> dict[str, ArchivedDocument]:
    """Read the catalog, keeping only downloaded files that are not duplicates."""
    catalog_path = archive_root / CATALOG_FILE
    try:
        with catalog_path.open(newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
    except FileNotFoundError as error:
        raise ArchiveError(f"No catalog found at {catalog_path}.") from error
    return {
        row["doc_id"]: _to_document(archive_root, row)
        for row in rows
        if _is_usable(row)
    }


def _field(row: Mapping[str, str | None], column: str) -> str:
    return (row.get(column) or "").strip()


def _is_usable(row: Mapping[str, str | None]) -> bool:
    return (
        _field(row, "status") == "done"
        and not _field(row, "duplicate_of")
        and bool(_field(row, "local_path"))
    )


def _to_document(archive_root: Path, row: Mapping[str, str | None]) -> ArchivedDocument:
    # A web page can have several files (PDF and HTML); the first is the primary copy.
    first_path = _field(row, "local_path").split(PATH_SEPARATOR)[0].strip()
    return ArchivedDocument(
        doc_id=_field(row, "doc_id"),
        title=_field(row, "title_as_posted"),
        library_id=_field(row, "library_id"),
        sdg=_field(row, "sdg"),
        doc_type=_field(row, "doc_type"),
        path=archive_root / first_path,
        sha256=_field(row, "sha256").lower(),
        source_url=_field(row, "source_url"),
    )


def read_document_list(list_path: Path) -> list[str]:
    """Read doc_ids from a text file, one per line; `#` starts a comment."""
    doc_ids: list[str] = []
    for line in list_path.read_text(encoding="utf-8").splitlines():
        doc_id = line.split("#", 1)[0].strip()
        if doc_id:
            doc_ids.append(doc_id)
    return doc_ids


def select_documents(
    catalog: Mapping[str, ArchivedDocument], doc_ids: Iterable[str]
) -> list[ArchivedDocument]:
    """Return the requested documents in order, or explain which are unavailable."""
    requested = list(doc_ids)
    missing = [doc_id for doc_id in requested if doc_id not in catalog]
    if missing:
        raise ArchiveError(
            "Not available in the catalog: "
            + ", ".join(missing)
            + ". Check their status and duplicate_of columns in registry/documents.csv."
        )
    return [catalog[doc_id] for doc_id in requested]


def file_sha256(path: Path) -> str:
    """Compute a file's SHA-256 fingerprint without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def find_file_problems(documents: Iterable[ArchivedDocument]) -> list[str]:
    """List documents whose file is missing or differs from its recorded fingerprint."""
    problems: list[str] = []
    for document in documents:
        if not document.path.is_file():
            problems.append(f"{document.doc_id}: file not found at {document.path}")
        elif document.sha256 and file_sha256(document.path) != document.sha256:
            problems.append(
                f"{document.doc_id}: file differs from its catalog fingerprint ({document.path})"
            )
        elif not document.sha256:
            problems.append(
                f"{document.doc_id}: no fingerprint recorded in the catalog"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Check that every listed document is cataloged, present, and unchanged."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--list", type=Path, default=V1_DOCUMENT_LIST, help="file of doc_ids to check"
    )
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        root = archive_root_from_env()
        documents = select_documents(load_catalog(root), read_document_list(args.list))
    except ArchiveError as error:
        print(error, file=sys.stderr)
        return 1

    problems = find_file_problems(documents)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(
        f"{len(documents)} documents found in {root}; all files present and unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
