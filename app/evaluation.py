"""Exact field scoring against a reviewed reference; no model calls or file access."""

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from app.models import DraftRow

EXPECTED_FIELDS = (
    "sample_id",
    "lab_sample_id",
    "analyte",
    "method",
    "result_as_written",
    "qualifier",
    "reporting_limit",
    "mdl",
    "units",
    "dilution",
    "analysis_date",
)
RowKey = tuple[str, str, str | None, int]


class FieldDifference(BaseModel):
    row: RowKey
    field: str
    expected: str | None
    actual: str | None


class ScoreReport(BaseModel):
    expected_rows: int
    field_matches: dict[str, int]
    missing_rows: list[RowKey]
    extra_rows: list[RowKey]
    order_matches: bool
    differences: list[FieldDifference] = Field(default_factory=list)
    run_id: UUID | None = None
    reference_inputs_sha256: str | None = None
    model_settings: dict[str, JsonValue] = Field(default_factory=dict)
    returned_model: str | None = None


def fixture_input_hash(inputs: Mapping[str, JsonValue]) -> str:
    """Canonical UTF-8 JSON hash binds review to all source/text/reference inputs."""
    encoded = json.dumps(
        inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _keyed(
    rows: Sequence[Mapping[str, str | None]],
) -> dict[RowKey, Mapping[str, str | None]]:
    occurrences: Counter[tuple[str, str, str | None]] = Counter()
    result: dict[RowKey, Mapping[str, str | None]] = {}
    for row in rows:
        base = (row["sample_id"] or "", row["analyte"] or "", row.get("method"))
        occurrences[base] += 1
        result[(*base, occurrences[base])] = row
    return result


def score_rows(
    expected: Sequence[dict[str, str | None]], actual: Sequence[DraftRow]
) -> ScoreReport:
    """Match identity plus occurrence; missing rows count against every denominator."""
    reference = _keyed(
        [
            {field: row.get(field) or None for field in EXPECTED_FIELDS}
            for row in expected
        ]
    )
    observed = _keyed(
        [{field: getattr(row, field) for field in EXPECTED_FIELDS} for row in actual]
    )
    matches = dict.fromkeys(EXPECTED_FIELDS, 0)
    differences: list[FieldDifference] = []
    for key, row in reference.items():
        if key not in observed:
            continue
        for field in EXPECTED_FIELDS:
            if row[field] == observed[key][field]:
                matches[field] += 1
            else:
                differences.append(
                    FieldDifference(
                        row=key,
                        field=field,
                        expected=row[field],
                        actual=observed[key][field],
                    )
                )
    return ScoreReport(
        expected_rows=len(expected),
        field_matches=matches,
        missing_rows=[key for key in reference if key not in observed],
        extra_rows=[key for key in observed if key not in reference],
        order_matches=list(reference) == list(observed),
        differences=differences,
    )
