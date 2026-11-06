"""Preserve source values, reject false grounding, and keep all results drafts."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import ExtractedRow, ExtractionRequest, PageExtraction
from app.rules import UnclearExtraction, interpret_result, prepare_rows
from tests.extraction_helpers import fixture_data, simple_pages, simple_row


@pytest.mark.parametrize(
    "text,qualifier,expected",
    [
        ("<0.020", None, (None, True)),
        ("ND", "U", (None, True)),
        ("0.50 U", "U", (None, True)),
        ("0.50", "UJ", (None, True)),
        ("0.29", "J", (Decimal("0.29"), False)),
        ("0.27 J", "J", (Decimal("0.27"), False)),
        ("0.270", None, (Decimal("0.270"), False)),
    ],
)
def test_interprets_values_without_turning_limits_into_detections(
    text, qualifier, expected
) -> None:
    assert interpret_result(text, qualifier) == expected


@pytest.mark.parametrize("text", ["NaN", "Infinity", "", "1 3.7", "unknown", "<NaN"])
def test_ambiguous_numeric_text_is_unclear(text: str) -> None:
    with pytest.raises(UnclearExtraction):
        interpret_result(text, None)


@pytest.mark.parametrize(
    "field", ["sample_id", "analyte", "result_as_written", "source_excerpt"]
)
@pytest.mark.parametrize("value", ["", "  "])
def test_rejects_blank_required_fields(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        ExtractedRow.model_validate(simple_row(**{field: value}))


@pytest.mark.parametrize(
    "changes",
    [
        {"source_line": 99},
        {"source_excerpt": "invented"},
        {"sample_id": "another sample"},
        {"source_line": 1},
    ],
)
def test_source_references_must_point_to_the_current_page(changes: dict) -> None:
    output = PageExtraction(
        status="extracted", rows=[ExtractedRow.model_validate(simple_row(**changes))]
    )
    with pytest.raises(UnclearExtraction):
        prepare_rows(output, simple_pages())


def test_duplicate_or_out_of_order_references_are_unclear() -> None:
    row = ExtractedRow.model_validate(simple_row())
    output = PageExtraction(status="extracted", rows=[row, row])
    with pytest.raises(UnclearExtraction):
        prepare_rows(output, simple_pages())


def test_review_and_provenance_are_server_owned() -> None:
    with pytest.raises(ValidationError):
        ExtractedRow.model_validate(
            simple_row(review_status="confirmed", doc_id="DOC-9999")
        )
    output = PageExtraction(
        status="extracted", rows=[ExtractedRow.model_validate(simple_row())]
    )
    row = prepare_rows(output, simple_pages())[0]
    assert (row.doc_id, row.page_number, row.row_number, row.review_status) == (
        "DOC-0001",
        1,
        1,
        "unconfirmed",
    )


@pytest.mark.parametrize("name,count", [("DOC-0033-p6", 21), ("DOC-0003-p7", 35)])
def test_prepares_fixture_rows_without_changing_raw_fields(
    name: str, count: int
) -> None:
    pages, data = fixture_data(name)
    rows = prepare_rows(PageExtraction.model_validate(data), pages)
    assert len(rows) == count
    assert all(row.review_status == "unconfirmed" for row in rows)
    if count == 21:
        assert rows[0].result_as_written == "<0.020"
        assert all(row.value is None and row.is_nondetect for row in rows)
    else:
        assert rows[0].mdl is None
        assert rows[10].value == Decimal("0.29")
        assert not rows[10].is_nondetect


@pytest.mark.parametrize(
    "data",
    [
        {"status": "extracted", "rows": []},
        {"status": "unclear", "reason": " ", "rows": []},
        {"status": "unclear", "reason": "ambiguous", "rows": [simple_row()]},
    ],
)
def test_unclear_or_empty_outputs_cannot_claim_extraction(data: dict) -> None:
    with pytest.raises(ValidationError):
        PageExtraction.model_validate(data)


@pytest.mark.parametrize("page", [0, -1, True, 1.0, "1"])
def test_request_requires_positive_integer_pdf_pages(page: object) -> None:
    with pytest.raises(ValidationError):
        ExtractionRequest(doc_id="DOC-0001", results_page=page, definitions_page=2)
