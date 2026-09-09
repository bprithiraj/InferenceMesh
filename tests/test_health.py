from fastapi.testclient import TestClient


def test_liveness_and_readiness(client: TestClient) -> None:
    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "policy_version": "local-v1"}
    assert ready.headers["x-inferencemesh-request-id"].startswith("req-")


def test_metrics_are_exposed(client: TestClient) -> None:
    response = client.get("/metrics", headers={"Authorization": "Bearer test-metrics"})

    assert response.status_code == 200
    assert "inferencemesh_requests_total" in response.text


def test_sanitized_metrics_summary(client: TestClient) -> None:
    response = client.get("/demo/metrics/summary")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "active_requests": 0,
        "queued_requests": 0,
        "active_limit": 4,
        "queue_limit": 4,
        "policy_version": "local-v1",
    }
