"""Minimal Python client without an OpenAI SDK dependency."""

import httpx

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "inferencemesh-local",
            "messages": [{"role": "user", "content": "Explain the route you selected."}],
            "temperature": 0,
            "max_tokens": 96,
        },
    )
    response.raise_for_status()
    print(response.json()["choices"][0]["message"]["content"])
    print("backend:", response.headers["x-inferencemesh-backend"])
