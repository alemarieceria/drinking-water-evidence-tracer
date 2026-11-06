"""Draft data for offline protocol tests; these helpers do not establish accuracy."""

import csv
import json
from pathlib import Path

from app.pages import PagePair

FIXTURES = Path(__file__).parent / "fixtures" / "extraction"


def fixture_data(name: str) -> tuple[PagePair, dict]:
    folder = FIXTURES / name
    inputs = json.loads((folder / "source.json").read_text(encoding="utf-8"))["inputs"]
    pages = PagePair(
        **{
            key: value
            for key, value in inputs.items()
            if key not in {"file_hashes", "pdf_sha256"}
        },
        sha256=inputs["pdf_sha256"],
        results_text=(folder / "page.txt").read_text(encoding="utf-8"),
        definitions_text=(folder / "definitions.txt").read_text(encoding="utf-8"),
    )
    with (folder / "expected_rows.csv").open(encoding="utf-8", newline="") as file:
        expected = list(csv.DictReader(file))
    lines = pages.results_text.splitlines()
    rows = []
    cursor = 0
    for row in expected:
        index = next(
            i
            for i in range(cursor, len(lines))
            if row["analyte"] in lines[i] and row["result_as_written"] in lines[i]
        )
        rows.append(
            {
                **{k: v or None for k, v in row.items()},
                "source_line": index + 1,
                "source_excerpt": lines[index].strip(),
            }
        )
        cursor = index + 1
    return pages, {"status": "extracted", "reason": None, "rows": rows}


def simple_pages() -> PagePair:
    return PagePair(
        doc_id="DOC-0001",
        title="Test report",
        source_url="https://example.org/source.pdf",
        sha256="a" * 64,
        results_page=1,
        definitions_page=2,
        results_text="Sample SAMPLE-1\nLead 0.27 J\nBarium <0.020",
        definitions_text="J estimated; U not detected",
    )


def simple_row(**changes: object) -> dict:
    return {
        "sample_id": "SAMPLE-1",
        "analyte": "Lead",
        "result_as_written": "0.27",
        "qualifier": "J",
        "source_line": 2,
        "source_excerpt": "Lead 0.27 J",
        **changes,
    }
