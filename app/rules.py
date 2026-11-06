"""Plain-Python evidence rules."""

import re
from decimal import Decimal, InvalidOperation

from app.models import DraftRow, PageExtraction
from app.pages import PagePair


def result_values_disagree(
    extracted_value: Decimal, detection_summary_value: Decimal
) -> bool:
    """Compare numeric values already matched to the same result and units.

    True identifies a disagreement; False allows further human review.
    """
    return extracted_value != detection_summary_value


class UnclearExtraction(Exception):
    """The complete model output must be held for investigation, not displayed."""


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_RESULT = re.compile(
    rf"(?P<less><)?\s*(?P<number>{_NUMBER})(?:\s+(?P<qual>[A-Za-z]+))?"
)


def interpret_result(
    result_as_written: str, qualifier: str | None
) -> tuple[Decimal | None, bool]:
    """Interpret a result without replacing its raw spelling or borrowing limits."""
    text = result_as_written.strip()
    if re.fullmatch(r"ND(?:\s+[A-Za-z]+)?", text, re.IGNORECASE):
        return None, True
    match = _RESULT.fullmatch(text)
    if match is None:
        raise UnclearExtraction("The result text cannot be interpreted safely.")
    try:
        value = Decimal(match["number"])
    except InvalidOperation as error:
        raise UnclearExtraction("The result is not a finite number.") from error
    if not value.is_finite():
        raise UnclearExtraction("The result is not a finite number.")
    qualifiers = re.findall(
        r"[A-Z]+", f"{qualifier or ''} {match['qual'] or ''}".upper()
    )
    nondetect = bool(match["less"]) or any(q in {"U", "UJ"} for q in qualifiers)
    return (None if nondetect else value), nondetect


def prepare_rows(output: PageExtraction, pages: PagePair) -> list[DraftRow]:
    """Check source references and order; this does not establish extraction accuracy."""
    if output.status == "unclear":
        raise UnclearExtraction(output.reason or "The page is unclear.")
    lines = pages.results_text.splitlines()
    previous = 0
    rows: list[DraftRow] = []
    for number, row in enumerate(output.rows, 1):
        if not previous < row.source_line <= len(lines):
            raise UnclearExtraction(
                "Source row references are missing, duplicated, or out of order."
            )
        if (
            row.source_excerpt not in lines[row.source_line - 1]
            or row.sample_id not in pages.results_text
        ):
            raise UnclearExtraction(
                "A result cannot be grounded in the selected source text."
            )
        value, nondetect = interpret_result(row.result_as_written, row.qualifier)
        rows.append(
            DraftRow(
                **row.model_dump(),
                doc_id=pages.doc_id,
                page_number=pages.results_page,
                row_number=number,
                value=value,
                is_nondetect=nondetect,
            )
        )
        previous = row.source_line
    return rows
