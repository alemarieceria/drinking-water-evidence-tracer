"""Orchestration tests use local catalogs/PDFs and TestModel, never the archive."""

import csv
from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from app.archive import file_sha256, load_catalog
from app.extraction import ExtractionService
from app.models import ExtractionRequest
from app.pages import read_pages
from app.runs import RunStorageError, load_run, save_run
from tests.extraction_helpers import fixture_data, simple_pages, simple_row
from tests.pdf_helpers import write_pdf
from tests.test_extraction_agent import BrokenModel, CountingModel, SlowModel

pytestmark = pytest.mark.anyio


def make_archive(root: Path, doc_id: str = "DOC-0001", duplicate: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "source.pdf"
    if not path.exists():
        write_pdf(path, ("Sample SAMPLE-1 Lead 0.27 J", "J estimated"))
    (root / "registry").mkdir(exist_ok=True)
    with (root / "registry/documents.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        fields = [
            "doc_id",
            "status",
            "duplicate_of",
            "local_path",
            "sha256",
            "source_url",
            "title_as_posted",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            dict(
                zip(
                    fields,
                    [
                        doc_id,
                        "done",
                        "DOC-0002" if duplicate else "",
                        "source.pdf",
                        file_sha256(path),
                        "https://example.org/source.pdf",
                        "Test report",
                    ],
                    strict=True,
                )
            )
        )
    return path


@pytest.fixture
def service_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "archive"
    source = make_archive(root)
    monkeypatch.setenv("LLM_API_GATEWAY", "https://example.org/v1")
    monkeypatch.setenv("LLM_API_TOKEN", "fake-test-secret")
    monkeypatch.setenv("LLM_MODEL", "test-only")
    pages = read_pages(load_catalog(root)["DOC-0001"], 1, 2)
    line = next(
        i for i, s in enumerate(pages.results_text.splitlines(), 1) if "Lead" in s
    )
    output = {"status": "extracted", "rows": [simple_row(source_line=line)]}
    return root, source, tmp_path / "runs", output


async def test_records_success_with_real_local_pdf(service_setup, caplog) -> None:
    root, source, runs, output = service_setup
    service = ExtractionService(root, runs, TestModel(custom_output_args=output))
    request = ExtractionRequest(doc_id="DOC-0001", results_page=1, definitions_page=2)
    result = await service.run(request)
    assert result.status == "success" and result.total_rows == 1
    assert result.rows[0].doc_id == "DOC-0001"
    assert result.rows[0].review_status == "unconfirmed"
    saved = load_run(runs, result.run_id)
    assert saved.status == "success"
    assert saved.pages.sha256 == file_sha256(source)
    assert saved.attempt.prompt and saved.attempt.messages and saved.finished_at
    assert (
        "fake-test-secret"
        not in saved.model_dump_json() + result.model_dump_json() + caplog.text
    )
    other = await service.run(request)
    assert other.run_id != result.run_id


@pytest.mark.parametrize("name,count", [("DOC-0033-p6", 21), ("DOC-0003-p7", 35)])
async def test_records_fixture_protocol(
    service_setup, monkeypatch, name, count
) -> None:
    root, _source, runs, _ = service_setup
    pages, output = fixture_data(name)
    make_archive(root, pages.doc_id)
    monkeypatch.setattr("app.extraction.read_pages", lambda *args: pages)
    result = await ExtractionService(
        root, runs, TestModel(custom_output_args=output)
    ).run(
        ExtractionRequest(
            doc_id=pages.doc_id,
            results_page=pages.results_page,
            definitions_page=pages.definitions_page,
        )
    )
    assert result.status == "success" and len(result.rows) == count
    assert len(load_run(runs, result.run_id).rows) == count


@pytest.mark.parametrize(
    "kind,code",
    [
        ("unknown", "unknown_document"),
        ("duplicate", "unknown_document"),
        ("missing", "missing_file"),
        ("changed", "changed_file"),
        ("page", "invalid_page"),
        ("empty", "empty_page"),
        ("config", "configuration_error"),
        ("archive", "archive_unavailable"),
        ("model", "model_failure"),
        ("timeout", "model_timeout"),
        ("unclear", "unclear_page"),
    ],
)
async def test_failures_preserve_request_and_record_without_rows(
    service_setup, monkeypatch, kind, code
) -> None:
    root, source, runs, output = service_setup
    root = change_source(kind, root, source)
    doc_id = "DOC-0001"
    page = 1
    model = TestModel(custom_output_args=output)
    if kind == "unknown":
        doc_id = "DOC-9999"
    if kind == "page":
        page = 99
    if kind == "config":
        monkeypatch.delenv("LLM_MODEL")
    if kind == "model":
        model = BrokenModel()
    if kind == "timeout":
        monkeypatch.setattr("app.agent.MODEL_DEADLINE_SECONDS", 0.001)
        model = SlowModel()
    if kind == "unclear":
        model = TestModel(
            custom_output_args={
                "status": "unclear",
                "reason": "uncertain boundary",
                "rows": [],
            }
        )
    request = ExtractionRequest(doc_id=doc_id, results_page=page, definitions_page=2)
    result = await ExtractionService(root, runs, model).run(request)
    assert result.error_code == code
    assert result.rows == [] and result.total_rows == 0 and result.request == request
    saved = load_run(runs, result.run_id)
    assert saved.status in {"error", "unclear"} and saved.error_code == code
    assert str(root) not in result.message


def change_source(kind: str, root: Path, source: Path) -> Path:
    if kind == "duplicate":
        make_archive(root, duplicate=True)
    if kind == "missing":
        source.unlink()
    if kind == "changed":
        source.write_bytes(b"changed")
    if kind == "empty":
        write_pdf(source, ("", "J estimated"))
        make_archive(root)
    return root / "missing" if kind == "archive" else root


@pytest.mark.parametrize("size,expected_calls", [(60000, 1), (60001, 0)])
async def test_character_limit_before_model(
    service_setup, monkeypatch, size, expected_calls
) -> None:
    root, _, runs, _ = service_setup
    pages = simple_pages()
    pages.results_text += " " * (
        size - len(pages.results_text) - len(pages.definitions_text)
    )
    monkeypatch.setattr("app.extraction.read_pages", lambda *args: pages)
    model = CountingModel({"status": "extracted", "rows": [simple_row()]})
    result = await ExtractionService(root, runs, model).run(
        ExtractionRequest(doc_id="DOC-0001", results_page=1, definitions_page=2)
    )
    assert model.calls == expected_calls
    assert result.status == ("success" if expected_calls else "error")
    assert load_run(runs, result.run_id).pages is not None


@pytest.mark.parametrize("failure_at", [1, 3])
async def test_storage_failure_never_presents_success(
    service_setup, monkeypatch, failure_at
) -> None:
    root, _, runs, output = service_setup
    model = CountingModel(output)
    calls = 0

    def flaky_save(root, record):
        nonlocal calls
        calls += 1
        if calls == failure_at:
            raise RunStorageError("unwritable")
        save_run(root, record)

    monkeypatch.setattr("app.extraction.save_run", flaky_save)
    result = await ExtractionService(root, runs, model).run(
        ExtractionRequest(doc_id="DOC-0001", results_page=1, definitions_page=2)
    )
    assert (
        result.status == "error"
        and result.error_code == "storage_error"
        and result.rows == []
    )
    assert model.calls == (0 if failure_at == 1 else 1)
    if failure_at == 3:
        assert load_run(runs, result.run_id).status == "running"
