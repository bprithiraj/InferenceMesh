import json

from fastapi.testclient import TestClient


def test_openai_compatible_chat_completion(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "inferencemesh-local",
            "messages": [{"role": "user", "content": "Explain bounded admission control."}],
            "temperature": 0,
            "max_tokens": 64,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "inferencemesh-local"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert "bounded admission control" in body["choices"][0]["message"]["content"]
    assert body["usage"]["total_tokens"] > 0
    assert response.headers["x-inferencemesh-backend"] == "deterministic-local"
    assert "lowest_weighted_score" in response.headers["x-inferencemesh-route-reason"]


def test_chat_completion_stream_uses_sse_and_done_sentinel(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "inferencemesh-local",
            "messages": [{"role": "user", "content": "Stream this response."}],
            "stream": True,
            "max_tokens": 64,
        },
    ) as response:
        lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert lines[-1] == "data: [DONE]"
    chunks = [json.loads(line[6:]) for line in lines[:-1]]
    assert chunks[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_output_token_limit_is_enforced(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "inferencemesh-local",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "max_tokens exceeds configured limit"


def test_chat_rejects_unknown_and_embedding_only_models(client: TestClient) -> None:
    for model in ("does-not-exist", "inferencemesh-embedding-local"):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == f"model '{model}' is not available for chat"


def test_unknown_fields_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "inferencemesh-local",
            "messages": [{"role": "user", "content": "hello"}],
            "unsupported": True,
        },
    )

    assert response.status_code == 422
