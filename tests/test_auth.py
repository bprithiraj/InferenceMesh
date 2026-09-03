from fastapi.testclient import TestClient

from inferencemesh.api import create_app
from inferencemesh.config import Settings


def test_api_key_can_be_required() -> None:
    app = create_app(Settings(require_api_key=True, api_key="test-secret", fake_token_delay_ms=0))
    with TestClient(app) as client:
        unauthorized = client.get("/v1/models")
        authorized = client.get("/v1/models", headers={"Authorization": "Bearer test-secret"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
