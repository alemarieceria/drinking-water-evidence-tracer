"""Scoring is exact; live experiments require an unchanged, reviewed reference."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from app.archive import load_catalog
from app.evaluation import score_rows
from app.extraction import ExtractionService
from app.models import PageExtraction
from app.pages import read_pages
from app.rules import prepare_rows
from scripts.evaluate_extraction import EvaluationError, evaluate_fixture, main
from tests.extraction_helpers import FIXTURES, fixture_data
from tests.test_extraction_agent import CountingModel


def rows_for(name: str):
    pages, data = fixture_data(name)
    with (FIXTURES / name / "expected_rows.csv").open(
        encoding="utf-8", newline=""
    ) as file:
        expected = list(csv.DictReader(file))
    return expected, prepare_rows(PageExtraction.model_validate(data), pages)


def test_field_scores_expose_invented_mdl_and_wrong_qualifier() -> None:
    expected, actual = rows_for("DOC-0003-p7")
    actual[0] = actual[0].model_copy(update={"mdl": "0"})
    actual[10] = actual[10].model_copy(update={"qualifier": None})
    report = score_rows(expected, actual)
    assert report.expected_rows == 35
    assert report.field_matches["mdl"] == 34
    assert report.field_matches["qualifier"] == 34
    assert report.field_matches["units"] == 35
    assert report.missing_rows == [] and report.extra_rows == []


def test_decimal_spelling_is_not_normalized() -> None:
    expected, actual = rows_for("DOC-0033-p6")
    actual[0] = actual[0].model_copy(update={"result_as_written": "<0.02"})
    assert score_rows(expected, actual).field_matches["result_as_written"] == 20


def test_missing_extra_and_duplicate_rows_are_visible() -> None:
    expected, actual = rows_for("DOC-0003-p7")
    changed = actual[0].model_copy(update={"sample_id": "OTHER"})
    report = score_rows(expected, [changed, *actual[1:]])
    assert len(report.missing_rows) == len(report.extra_rows) == 1
    assert report.field_matches["units"] == 34
    duplicated = score_rows(expected, [*actual, actual[0]])
    assert len(duplicated.extra_rows) == 1
    assert duplicated.expected_rows == 35


def test_row_order_is_checked_without_affecting_field_matches() -> None:
    expected, actual = rows_for("DOC-0003-p7")
    report = score_rows(expected, list(reversed(actual)))
    assert not report.order_matches
    assert report.field_matches["result_as_written"] == 35


def test_cli_requires_explicit_live_flag(capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--fixture", "DOC-0033-p6"])
    assert caught.value.code == 2
    assert "--live" in capsys.readouterr().err


def stamp(source: dict) -> None:
    canonical = json.dumps(
        source["inputs"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    source["review"]["inputs_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()


def reviewed_fixture(folder: Path, root: Path) -> dict:
    folder.mkdir()
    pages = read_pages(load_catalog(root)["DOC-0001"], 1, 2)
    (folder / "page.txt").write_text(pages.results_text, encoding="utf-8", newline="\n")
    (folder / "definitions.txt").write_text(
        pages.definitions_text, encoding="utf-8", newline="\n"
    )
    (folder / "expected_rows.csv").write_text(
        "sample_id,lab_sample_id,analyte,method,result_as_written,qualifier,reporting_limit,mdl,units,dilution,analysis_date\nSAMPLE-1,,Lead,,0.27,J,,,,,\n",
        encoding="utf-8",
        newline="\n",
    )
    inputs = {
        k: v
        for k, v in pages.model_dump().items()
        if k not in {"results_text", "definitions_text", "sha256"}
    }
    inputs["pdf_sha256"] = pages.sha256
    inputs["file_hashes"] = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in ["page.txt", "definitions.txt", "expected_rows.csv"]
    }
    source = {
        "inputs": inputs,
        "review": {
            "status": "reviewed",
            "reviewed_by": "Test reviewer",
            "reviewed_at": "2026-11-05T20:00:00+00:00",
            "inputs_sha256": None,
        },
    }
    stamp(source)
    (folder / "source.json").write_text(json.dumps(source), encoding="utf-8")
    return source


@pytest.mark.anyio
async def test_explicit_evaluation_records_a_score_without_network(
    service_setup, tmp_path
) -> None:
    root, _, runs, output = service_setup
    folder = tmp_path / "fixture"
    reviewed_fixture(folder, root)
    model = CountingModel(output)
    report = await evaluate_fixture(folder, ExtractionService(root, runs, model))
    assert report.expected_rows == 1
    assert set(report.field_matches.values()) == {1}
    assert model.calls == 1
    saved = json.loads((runs / f"{report.run_id}.score.json").read_text())
    assert saved["reference_inputs_sha256"]
    assert saved["model_settings"]["model_name"] == "test-only"
    assert "fake-test-secret" not in json.dumps(saved)


def tamper(kind: str, folder: Path, source: dict) -> None:
    changes = {
        "draft": lambda: source["review"].update(status="draft"),
        "reviewer": lambda: source["review"].update(reviewed_by=None),
        "review_hash": lambda: source["review"].update(inputs_sha256="0" * 64),
        "metadata": lambda: source["inputs"].update(title="Changed title"),
        "reader": lambda: source["inputs"]["reader_versions"].update(pdfplumber="0.0"),
        "options": lambda: source["inputs"]["extraction_options"].update(x_tolerance=9),
        "fingerprint": lambda: source["inputs"].update(pdf_sha256="0" * 64),
        "path": lambda: source["inputs"]["file_hashes"].update(
            {"../../.env": "0" * 64}
        ),
    }
    if kind in changes:
        changes[kind]()
    if kind in {"csv", "text"}:
        name = "expected_rows.csv" if kind == "csv" else "page.txt"
        (folder / name).write_bytes((folder / name).read_bytes() + b"CHANGED")
        if kind == "text":
            source["inputs"]["file_hashes"][name] = hashlib.sha256(
                (folder / name).read_bytes()
            ).hexdigest()
    if kind in {"reader", "options", "fingerprint", "text", "path"}:
        stamp(source)
    (folder / "source.json").write_text(json.dumps(source), encoding="utf-8")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kind",
    [
        "draft",
        "reviewer",
        "review_hash",
        "metadata",
        "reader",
        "options",
        "fingerprint",
        "text",
        "csv",
        "path",
    ],
)
async def test_unreviewed_or_changed_reference_blocks_before_model(
    service_setup, tmp_path, kind
) -> None:
    root, _, runs, output = service_setup
    folder = tmp_path / "fixture"
    source = reviewed_fixture(folder, root)
    tamper(kind, folder, source)
    model = CountingModel(output)
    with pytest.raises(EvaluationError):
        await evaluate_fixture(folder, ExtractionService(root, runs, model))
    assert model.calls == 0
    assert not list(runs.glob("*.score.json"))


@pytest.mark.anyio
async def test_failed_extraction_is_not_a_successful_score(
    service_setup, tmp_path
) -> None:
    root, _, runs, _ = service_setup
    folder = tmp_path / "fixture"
    reviewed_fixture(folder, root)
    model = CountingModel({"status": "unclear", "reason": "Ambiguous page", "rows": []})
    with pytest.raises(EvaluationError):
        await evaluate_fixture(folder, ExtractionService(root, runs, model))
    assert not list(runs.glob("*.score.json"))


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["title", "source_url"])
async def test_catalog_metadata_drift_blocks_before_model(
    service_setup, tmp_path, field
) -> None:
    root, _, runs, output = service_setup
    folder = tmp_path / "fixture"
    reviewed_fixture(folder, root)
    catalog = root / "registry" / "documents.csv"
    original = "Test report" if field == "title" else "https://example.org/source.pdf"
    catalog.write_text(
        catalog.read_text(encoding="utf-8").replace(original, "Changed metadata"),
        encoding="utf-8",
    )
    model = CountingModel(output)
    with pytest.raises(EvaluationError):
        await evaluate_fixture(folder, ExtractionService(root, runs, model))
    assert model.calls == 0
    assert not list(runs.glob("*.score.json"))


@pytest.mark.anyio
async def test_source_replacement_after_preflight_blocks_before_model(
    service_setup, tmp_path, monkeypatch
) -> None:
    from scripts import evaluate_extraction
    from tests.pdf_helpers import make_archive, write_pdf

    root, source, runs, output = service_setup
    folder = tmp_path / "fixture"
    reviewed_fixture(folder, root)
    original_preflight = evaluate_extraction._preflight

    def replace_after_check(fixture, service):
        pages = original_preflight(fixture, service)
        write_pdf(source, ("Sample SAMPLE-1 Lead 0.28 J", "J estimated"))
        make_archive(root)
        return pages

    monkeypatch.setattr(evaluate_extraction, "_preflight", replace_after_check)
    model = CountingModel(output)
    with pytest.raises(EvaluationError):
        await evaluate_fixture(folder, ExtractionService(root, runs, model))
    assert model.calls == 0
    assert not list(runs.glob("*.score.json"))
