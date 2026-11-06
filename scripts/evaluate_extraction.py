"""Run a deliberate live experiment only against an unchanged reviewed fixture."""

import argparse
import asyncio
import csv
import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.archive import (
    ArchiveError,
    archive_root_from_env,
    load_catalog,
    select_documents,
)
from app.evaluation import EXPECTED_FIELDS, ScoreReport, fixture_input_hash, score_rows
from app.extraction import ExtractionService
from app.pages import PagePair, PageReadError, read_pages
from app.runs import RunStorageError, load_run, save_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "extraction"
FILES = {"page.txt", "definitions.txt", "expected_rows.csv"}


class EvaluationError(Exception):
    """Safe experiment failure; no score is claimed."""


class FixtureInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    doc_id: str = Field(pattern=r"^DOC-\d{4}$")
    title: str
    source_url: str
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    results_page: int = Field(ge=1)
    definitions_page: int = Field(ge=1)
    reader_versions: dict[str, str]
    extraction_options: dict[str, bool | int | float]
    file_hashes: dict[str, str]


class FixtureReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["draft", "reviewed"]
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    inputs_sha256: str | None = None


class FixtureSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: FixtureInputs
    review: FixtureReview


@dataclass
class ReviewedFixture:
    source: FixtureSource
    expected: list[dict[str, str | None]]
    results_text: str
    definitions_text: str


def _check_review(source: FixtureSource) -> None:
    review = source.review
    if review.status != "reviewed" or not (review.reviewed_by or "").strip():
        raise EvaluationError(
            "The expected rows require a named human review before live scoring."
        )
    if review.reviewed_at is None or review.reviewed_at.tzinfo is None:
        raise EvaluationError("The fixture review needs a UTC-aware timestamp.")
    if review.inputs_sha256 != fixture_input_hash(
        source.inputs.model_dump(mode="json")
    ):
        raise EvaluationError(
            "The reviewed fixture inputs have changed; review them again."
        )


def _check_files(folder: Path, source: FixtureSource) -> None:
    if set(source.inputs.file_hashes) != FILES:
        raise EvaluationError(
            "The fixture must identify exactly its three reference files."
        )
    for name, expected in source.inputs.file_hashes.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise EvaluationError(f"The reviewed {name} has changed; review it again.")


def _expected_rows(folder: Path) -> list[dict[str, str | None]]:
    with (folder / "expected_rows.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or set(reader.fieldnames) != set(EXPECTED_FIELDS):
            raise EvaluationError(
                "The expected-rows CSV has missing or unexpected columns."
            )
        rows = list(reader)
    if not rows or any(
        not (row.get("sample_id") or "").strip()
        or not (row.get("analyte") or "").strip()
        for row in rows
    ):
        raise EvaluationError("Every reference row needs a sample ID and analyte.")
    if any(
        set(row) != set(EXPECTED_FIELDS)
        or any(not isinstance(value, str) for value in row.values())
        for row in rows
    ):
        raise EvaluationError("A reference CSV row has a missing or extra cell.")
    return [{field: row[field] or None for field in EXPECTED_FIELDS} for row in rows]


def load_reviewed_fixture(folder: Path) -> ReviewedFixture:
    try:
        source = FixtureSource.model_validate_json(
            (folder / "source.json").read_bytes()
        )
        _check_review(source)
        _check_files(folder, source)
        return ReviewedFixture(
            source,
            _expected_rows(folder),
            (folder / "page.txt").read_text(encoding="utf-8"),
            (folder / "definitions.txt").read_text(encoding="utf-8"),
        )
    except OSError, ValidationError, UnicodeError, csv.Error:
        raise EvaluationError(
            "The reviewed fixture is unavailable or invalid."
        ) from None


def _preflight(fixture: ReviewedFixture, service: ExtractionService) -> PagePair:
    inputs = fixture.source.inputs
    try:
        root = (
            service.archive_root
            if service.archive_root is not None
            else archive_root_from_env()
        )
        document = select_documents(load_catalog(root), [inputs.doc_id])[0]
        if document.sha256 != inputs.pdf_sha256:
            raise EvaluationError(
                "The archived PDF fingerprint differs from the reviewed fixture."
            )
        pages = read_pages(document, inputs.results_page, inputs.definitions_page)
    except ArchiveError, PageReadError, OSError:
        raise EvaluationError(
            "The archived source cannot be verified for this experiment."
        ) from None
    if (
        pages.doc_id != inputs.doc_id
        or pages.title != inputs.title
        or pages.source_url != inputs.source_url
    ):
        raise EvaluationError(
            "The archived document metadata differs from the reviewed fixture."
        )
    if (
        pages.reader_versions != inputs.reader_versions
        or pages.extraction_options != inputs.extraction_options
    ):
        raise EvaluationError(
            "The PDF reader version or settings differ from the reviewed fixture."
        )
    if (
        pages.results_text != fixture.results_text
        or pages.definitions_text != fixture.definitions_text
    ):
        raise EvaluationError(
            "The regenerated page text differs from the reviewed fixture."
        )
    return pages


async def evaluate_fixture(
    fixture_dir: Path, service: ExtractionService
) -> ScoreReport:
    fixture = await asyncio.to_thread(load_reviewed_fixture, fixture_dir)
    pages = await asyncio.to_thread(_preflight, fixture, service)
    from app.models import ExtractionRequest

    bound_service = replace(service, expected_pages=pages)
    result = await bound_service.run(
        ExtractionRequest(
            doc_id=pages.doc_id,
            results_page=pages.results_page,
            definitions_page=pages.definitions_page,
        )
    )
    if result.status != "success" or result.run_id is None:
        raise EvaluationError(
            f"No successful score: {result.message} Run ID: {result.run_id}."
        )
    report = score_rows(fixture.expected, result.rows)
    record = await asyncio.to_thread(load_run, service.runs_root, result.run_id)
    report.run_id = result.run_id
    report.reference_inputs_sha256 = fixture.source.review.inputs_sha256
    if record.attempt is not None:
        report.model_settings = record.attempt.public_config
        report.returned_model = record.attempt.returned_model
    await asyncio.to_thread(
        save_score, service.runs_root, result.run_id, report.model_dump_json(indent=2)
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Explicitly permit the configured model request.",
    )
    parser.add_argument(
        "--fixture", required=True, choices=["DOC-0033-p6", "DOC-0003-p7"]
    )
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("Live evaluation requires --live; pytest never runs a live model.")
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    try:
        report = asyncio.run(
            evaluate_fixture(FIXTURE_ROOT / args.fixture, ExtractionService())
        )
    except (EvaluationError, RunStorageError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
