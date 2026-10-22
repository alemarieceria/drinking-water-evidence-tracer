"""Basic page and API contract checks, independent of placeholder values."""

from fastapi.testclient import TestClient
from pydantic_ai.models import override_allow_model_requests

from app.main import app


def test_page_loads_with_form() -> None:
    with override_allow_model_requests(False), TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "<form" in response.text


def test_trace_accepts_sample_and_returns_declared_fields() -> None:
    with override_allow_model_requests(False), TestClient(app) as client:
        response = client.post(
            "/trace",
            json={"sample_id": "220113-I1-HT03", "analyte": "Lead"},
        )

    assert response.status_code == 200
    assert set(response.json()) == {
        "placeholder",
        "message",
        "sample",
        "inventory",
        "trace",
        "source_preview",
        "evidence_sets",
    }
