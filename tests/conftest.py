from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from inferencemesh.api import create_app
from inferencemesh.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        require_api_key=False,
        fake_token_delay_ms=0,
        max_concurrent_requests=4,
        max_concurrent_per_tenant=2,
        max_queue_depth=4,
        queue_wait_ms=50,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
