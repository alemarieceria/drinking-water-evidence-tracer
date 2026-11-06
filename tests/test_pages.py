"""Reader boundaries: source integrity, exact page selection, and raw text."""

import csv
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.pages import PageReadError, read_pages
from tests.pdf_helpers import document_for, write_pdf

FIXTURES = Path(__file__).parent / "fixtures" / "extraction"


def test_reads_both_pages(tmp_path: Path) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("Results page <0.020", "Definitions page J estimated"))
    pages = read_pages(document_for(path), 1, 2)
    assert "Results page <0.020" in pages.results_text
    assert "Definitions page J estimated" in pages.definitions_text
    assert pages.results_page == 1
    assert pages.definitions_page == 2
    assert pages.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert pages.reader_versions["pdfplumber"] == "0.11.10"


def test_accepts_same_page_twice(tmp_path: Path) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("Results and definitions",))
    pages = read_pages(document_for(path), 1, 1)
    assert pages.results_text == pages.definitions_text


@pytest.mark.parametrize("number", [True, 1.0])
def test_rejects_noninteger_definitions_page(tmp_path: Path, number: int) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("Results and definitions",))
    with pytest.raises(PageReadError):
        read_pages(document_for(path), 1, number)


@pytest.mark.parametrize("number", [0, -1, 3, True, 1.5])
def test_rejects_out_of_range_page(tmp_path: Path, number: int) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("Results", "Definitions"))
    with pytest.raises(PageReadError) as caught:
        read_pages(document_for(path), number, 2)
    assert caught.value.code == "invalid_page"


def test_rejects_unreadable_pdf(tmp_path: Path) -> None:
    path = tmp_path / "input.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(PageReadError) as caught:
        read_pages(document_for(path), 1, 1)
    assert caught.value.code == "unreadable_pdf"
    assert str(tmp_path) not in str(caught.value)


def test_rejects_empty_page(tmp_path: Path) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("",))
    with pytest.raises(PageReadError) as caught:
        read_pages(document_for(path), 1, 1)
    assert caught.value.code == "empty_page"


def test_rejects_changed_file_before_read(tmp_path: Path) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("Results",))
    document = replace(document_for(path), sha256="0" * 64)
    with pytest.raises(PageReadError) as caught:
        read_pages(document, 1, 1)
    assert caught.value.code == "changed_file"


def test_rejects_missing_fingerprint_or_file(tmp_path: Path) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("Results",))
    document = document_for(path)
    with pytest.raises(PageReadError) as caught:
        read_pages(replace(document, sha256=""), 1, 1)
    assert caught.value.code == "missing_fingerprint"
    path.unlink()
    with pytest.raises(PageReadError) as caught:
        read_pages(document, 1, 1)
    assert caught.value.code == "missing_file"


def test_rejects_changed_file_after_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "input.pdf"
    write_pdf(path, ("Results",))
    document = document_for(path)
    fingerprints = iter([document.sha256, "0" * 64])
    monkeypatch.setattr("app.pages.file_sha256", lambda _: next(fingerprints))
    with pytest.raises(PageReadError) as caught:
        read_pages(document, 1, 1)
    assert caught.value.code == "changed_file"


@pytest.mark.parametrize("name,count", [("DOC-0033-p6", 21), ("DOC-0003-p7", 35)])
def test_stored_fixtures_are_reviewed_and_reproducible(name: str, count: int) -> None:
    folder = FIXTURES / name
    source = json.loads((folder / "source.json").read_text(encoding="utf-8"))
    review = source["review"]
    assert review["status"] == "reviewed"
    assert review["reviewed_by"] == "A. Ceria"
    assert review["reviewed_at"]
    canonical = json.dumps(
        source["inputs"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert review["inputs_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    for filename, digest in source["inputs"]["file_hashes"].items():
        data = (folder / filename).read_bytes()
        assert b"\r" not in data
        assert hashlib.sha256(data).hexdigest() == digest
    with (folder / "expected_rows.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    text = (folder / "page.txt").read_text(encoding="utf-8")
    assert len(rows) == count
    if count == 21:
        assert text.count("Perylene-d12") == 3
        assert text.count("Triphenylphosphate") == 3
        assert text.count("2-Nitro-m-xylene") == 3
        assert len({row["sample_id"] for row in rows}) == 3
        assert "10" in text
        assert all(row["result_as_written"].startswith("<") for row in rows)
    else:
        assert rows[0]["mdl"] == ""
        assert rows[10]["result_as_written"] == "0.29"
        assert rows[10]["qualifier"] == "J"
        assert sum(row["result_as_written"] == "ND" for row in rows) == 32
