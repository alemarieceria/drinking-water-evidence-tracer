"""Every test is offline, including tests that use the model protocol."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic_ai.models import override_allow_model_requests

from app.archive import load_catalog
from app.pages import read_pages
from tests.extraction_helpers import simple_row
from tests.pdf_helpers import make_archive


@pytest.fixture(autouse=True)
def block_live_models() -> Iterator[None]:
    with override_allow_model_requests(False):
        yield


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
