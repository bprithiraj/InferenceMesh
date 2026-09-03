"""Harmless live probe for a running local gateway."""

import sys

import httpx


def main() -> int:
    base_url = "http://127.0.0.1:8000"
    with httpx.Client(base_url=base_url, timeout=10) as client:
        ready = client.get("/health/ready")
        ready.raise_for_status()
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "inferencemesh-local",
                "messages": [{"role": "user", "content": "Run the smoke test."}],
                "temperature": 0,
                "max_tokens": 64,
            },
        )
        response.raise_for_status()

    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert response.headers["x-inferencemesh-backend"] == "deterministic-local"
    print(f"SMOKE_OK request={response.headers['x-inferencemesh-request-id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
