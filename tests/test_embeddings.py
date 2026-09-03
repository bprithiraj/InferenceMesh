import math

from fastapi.testclient import TestClient


def test_embeddings_are_deterministic_and_normalized(client: TestClient) -> None:
    payload = {"model": "inferencemesh-embedding-local", "input": ["alpha", "beta"]}

    first = client.post("/v1/embeddings", json=payload)
    second = client.post("/v1/embeddings", json=payload)

    assert first.status_code == 200
    assert first.json() == second.json()
    vectors = [item["embedding"] for item in first.json()["data"]]
    assert len(vectors) == 2
    assert all(len(vector) == 16 for vector in vectors)
    assert all(
        math.isclose(sum(value * value for value in vector), 1.0, abs_tol=1e-6)
        for vector in vectors
    )
    assert first.headers["x-inferencemesh-backend"] == "deterministic-local"


def test_embeddings_reject_unknown_and_chat_only_models(client: TestClient) -> None:
    for model in ("does-not-exist", "inferencemesh-local"):
        response = client.post(
            "/v1/embeddings",
            json={"model": model, "input": "alpha"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == f"model '{model}' is not available for embedding"
