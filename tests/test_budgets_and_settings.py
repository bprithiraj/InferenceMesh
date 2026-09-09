import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from inferencemesh.api import create_app
from inferencemesh.config import Settings


def test_metrics_require_separate_key() -> None:
    with TestClient(
        create_app(
            Settings(metrics_api_key="metrics-only", api_key="inference", require_api_key=True)
        )
    ) as client:
        assert client.get("/metrics").status_code == 401
        assert (
            client.get("/metrics", headers={"Authorization": "Bearer inference"}).status_code == 401
        )
        assert (
            client.get("/metrics", headers={"Authorization": "Bearer metrics-only"}).status_code
            == 200
        )
    with TestClient(create_app(Settings())) as client:
        assert client.get("/metrics").status_code == 404


def test_request_and_reserved_output_budgets() -> None:
    payload = {
        "model": "inferencemesh-local",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 2,
    }
    with TestClient(create_app(Settings(requests_per_minute=2, fake_token_delay_ms=0))) as client:
        assert client.post("/v1/chat/completions", json=payload).status_code == 200
        assert client.post("/v1/chat/completions", json=payload).status_code == 200
        rejected = client.post("/v1/chat/completions", json=payload)
        assert rejected.status_code == 429
        assert rejected.headers["Retry-After"] == "60"
    with TestClient(
        create_app(Settings(output_tokens_per_minute=3, fake_token_delay_ms=0))
    ) as client:
        assert client.post("/v1/chat/completions", json=payload).status_code == 200
        assert client.post("/v1/chat/completions", json=payload).status_code == 429


def test_real_mode_and_public_demo_fail_closed_without_configuration() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        Settings(backend_mode="http")
    with pytest.raises(ValidationError, match="non-default"):
        Settings(environment="public-demo")


async def test_non_ascii_invalid_keys_return_401() -> None:
    from fastapi import HTTPException

    from inferencemesh.auth import ApiKeyAuthenticator

    auth = ApiKeyAuthenticator(
        Settings(require_api_key=True, api_key="valid", metrics_api_key="metrics")
    )
    with pytest.raises(HTTPException) as failure:
        await auth.authenticate(authorization="Bearer invalid-\u00fc", x_api_key=None)
    assert failure.value.status_code == 401
    with pytest.raises(HTTPException) as failure:
        await auth.authenticate_metrics(authorization="Bearer invalid-\u00fc", x_api_key=None)
    assert failure.value.status_code == 401
