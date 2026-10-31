"""Archive catalog lookups, using a small catalog built in a temporary folder."""

import csv
import hashlib
import re
from pathlib import Path

import pytest

from app.archive import (
    CATALOG_FILE,
    V1_DOCUMENT_LIST,
    ArchiveError,
    archive_root_from_env,
    find_file_problems,
    load_catalog,
    read_document_list,
    select_documents,
)

COLUMNS = [
    "doc_id",
    "title_as_posted",
    "library_id",
    "sdg",
    "doc_type",
    "status",
    "duplicate_of",
    "sha256",
    "local_path",
]
PDF_BYTES = b"%PDF-1.7 example"


def write_catalog(root: Path, rows: list[dict[str, str]]) -> None:
    catalog = root / CATALOG_FILE
    catalog.parent.mkdir(parents=True)
    with catalog.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, restval="")
        writer.writeheader()
        writer.writerows(rows)


def write_pdf(root: Path, relative_path: str) -> str:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PDF_BYTES)
    return hashlib.sha256(PDF_BYTES).hexdigest()


def test_catalog_skips_duplicates_and_files_not_yet_downloaded(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        [
            {"doc_id": "DOC-0053", "status": "done", "local_path": "raw/a.pdf"},
            {
                "doc_id": "DOC-0051",
                "status": "done",
                "duplicate_of": "DOC-0053",
                "local_path": "raw/b.pdf",
            },
            {"doc_id": "DOC-0160", "status": "to_find"},
        ],
    )

    assert list(load_catalog(tmp_path)) == ["DOC-0053"]


def test_catalog_uses_the_first_of_several_paths(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        [
            {
                "doc_id": "DOC-0001",
                "status": "done",
                "local_path": "web-captures/page.pdf; web-captures/page.html",
            }
        ],
    )

    assert (
        load_catalog(tmp_path)["DOC-0001"].path
        == tmp_path / "web-captures" / "page.pdf"
    )


def test_document_list_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    list_path = tmp_path / "list.txt"
    list_path.write_text(
        "# heading\n\nDOC-0010  # lab report\nDOC-0032\n", encoding="utf-8"
    )

    assert read_document_list(list_path) == ["DOC-0010", "DOC-0032"]


def test_selecting_a_duplicate_names_it_as_unavailable(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        [
            {"doc_id": "DOC-0053", "status": "done", "local_path": "raw/a.pdf"},
            {
                "doc_id": "DOC-0051",
                "status": "done",
                "duplicate_of": "DOC-0053",
                "local_path": "raw/b.pdf",
            },
        ],
    )

    with pytest.raises(ArchiveError, match="DOC-0051"):
        select_documents(load_catalog(tmp_path), ["DOC-0053", "DOC-0051"])


def test_file_check_passes_unchanged_files_and_reports_missing_or_changed_ones(
    tmp_path: Path,
) -> None:
    fingerprint = write_pdf(tmp_path, "raw/same.pdf")
    write_pdf(tmp_path, "raw/changed.pdf")
    (tmp_path / "raw" / "changed.pdf").write_bytes(b"%PDF-1.7 edited")
    write_catalog(
        tmp_path,
        [
            {
                "doc_id": "DOC-0001",
                "status": "done",
                "sha256": fingerprint,
                "local_path": "raw/same.pdf",
            },
            {
                "doc_id": "DOC-0002",
                "status": "done",
                "sha256": fingerprint,
                "local_path": "raw/changed.pdf",
            },
            {
                "doc_id": "DOC-0003",
                "status": "done",
                "sha256": fingerprint,
                "local_path": "raw/gone.pdf",
            },
        ],
    )

    problems = find_file_problems(load_catalog(tmp_path).values())

    assert [problem.split(":")[0] for problem in problems] == ["DOC-0002", "DOC-0003"]


def test_archive_root_must_be_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIVE_ROOT", raising=False)

    with pytest.raises(ArchiveError, match="ARCHIVE_ROOT is not set"):
        archive_root_from_env()


def test_archive_root_must_contain_the_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARCHIVE_ROOT", str(tmp_path))

    with pytest.raises(ArchiveError, match="No catalog found"):
        archive_root_from_env()

    write_catalog(tmp_path, [])
    assert archive_root_from_env() == tmp_path


def test_version_1_list_names_27_distinct_documents() -> None:
    doc_ids = read_document_list(V1_DOCUMENT_LIST)

    assert len(doc_ids) == 27
    assert len(set(doc_ids)) == 27
    assert all(re.fullmatch(r"DOC-\d{4}", doc_id) for doc_id in doc_ids)
