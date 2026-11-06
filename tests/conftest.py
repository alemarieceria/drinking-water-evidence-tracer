"""Every test is offline, including tests that use the model protocol."""

from collections.abc import Iterator

import pytest
from pydantic_ai.models import override_allow_model_requests


@pytest.fixture(autouse=True)
def block_live_models() -> Iterator[None]:
    with override_allow_model_requests(False):
        yield


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
