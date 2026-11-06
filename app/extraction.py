"""Connect archive lookup, PDF reading, bounded extraction, rules, and run storage."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic_ai.models import Model

from app.agent import ModelConfigError, extract_rows, load_model_config
from app.archive import (
    ArchivedDocument,
    ArchiveError,
    archive_root_from_env,
    load_catalog,
    select_documents,
)
from app.models import ExtractionRequest, ExtractionResponse, RunRecord
from app.pages import PagePair, PageReadError, read_pages
from app.rules import UnclearExtraction, prepare_rows
from app.runs import RunStorageError, save_run

RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"
MAX_INPUT_CHARACTERS = 60000


class ExtractionFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _lookup(root: Path | None, doc_id: str) -> ArchivedDocument:
    try:
        catalog = load_catalog(root if root is not None else archive_root_from_env())
    except ArchiveError, OSError:
        raise ExtractionFailure(
            "archive_unavailable",
            "The document archive is unavailable; check ARCHIVE_ROOT.",
        ) from None
    try:
        return select_documents(catalog, [doc_id])[0]
    except ArchiveError:
        raise ExtractionFailure(
            "unknown_document",
            "The document ID is not available; check its catalog status or duplicate entry.",
        ) from None


def _record_failure(record: RunRecord, error: Exception) -> None:
    record.status = "error"
    record.rows = []
    if isinstance(error, (PageReadError, ExtractionFailure)):
        record.error_code, record.message = error.code, str(error)
    elif isinstance(error, ModelConfigError):
        record.error_code, record.message = "configuration_error", str(error)
    elif isinstance(error, UnclearExtraction):
        record.status = "unclear"
        record.error_code, record.message = "unclear_page", str(error)
    elif isinstance(error, RunStorageError):
        record.error_code, record.message = (
            "storage_error",
            "The local run record could not be saved; no results are presented.",
        )
    else:
        record.error_code, record.message = (
            "extraction_failed",
            "Extraction failed; inspect the local run record.",
        )


def _response(record: RunRecord, *, persisted: bool = True) -> ExtractionResponse:
    status = record.status
    if status == "running":
        status = "error"
    return ExtractionResponse(
        request=record.request,
        run_id=record.run_id if persisted else None,
        status=status,
        error_code=record.error_code,
        message=record.message,
        pages=record.pages,
        rows=record.rows,
    )


@dataclass
class ExtractionService:
    archive_root: Path | None = None
    runs_root: Path = RUNS_ROOT
    model: Model | None = None
    expected_pages: PagePair | None = None

    async def _process(self, record: RunRecord) -> None:
        request = record.request
        document = await asyncio.to_thread(_lookup, self.archive_root, request.doc_id)
        pages = await asyncio.to_thread(
            read_pages, document, request.results_page, request.definitions_page
        )
        record.pages = pages
        await asyncio.to_thread(save_run, self.runs_root, record)
        if self.expected_pages is not None and pages != self.expected_pages:
            raise ExtractionFailure(
                "reference_changed",
                "The extraction input differs from the reviewed fixture; no model was called.",
            )
        if len(pages.results_text) + len(pages.definitions_text) > MAX_INPUT_CHARACTERS:
            raise ExtractionFailure(
                "input_too_large",
                "The two pages exceed the 60,000-character model-input limit.",
            )
        config = load_model_config()
        attempt = await extract_rows(pages, config, model=self.model)
        record.attempt = attempt
        if attempt.error_code is not None:
            message = (
                "The model request timed out."
                if attempt.error_code == "model_timeout"
                else "The model did not return a usable extraction."
            )
            raise ExtractionFailure(attempt.error_code, message)
        if attempt.output is None:
            raise ExtractionFailure(
                "model_failure", "The model did not return an extraction."
            )
        record.rows = prepare_rows(attempt.output, pages)
        record.status = "success"
        record.message = "Unconfirmed model output; completeness has not been verified."

    async def run(self, request: ExtractionRequest) -> ExtractionResponse:
        record = RunRecord(request=request)
        try:
            await asyncio.to_thread(save_run, self.runs_root, record)
        except RunStorageError as error:
            _record_failure(record, error)
            return _response(record, persisted=False)
        try:
            await self._process(record)
        except (
            PageReadError,
            ExtractionFailure,
            ModelConfigError,
            UnclearExtraction,
            RunStorageError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            _record_failure(record, error)
        record.finished_at = datetime.now(UTC)
        try:
            await asyncio.to_thread(save_run, self.runs_root, record)
        except RunStorageError as error:
            _record_failure(record, error)
        return _response(record)
