import asyncio
import json

import httpx
import pytest
from test_http_backend import GatedStream, sse

from inferencemesh.api import create_app
from inferencemesh.backends.http import HTTPBackend
from inferencemesh.config import BackendConfig, Settings
from inferencemesh.domain import ChatCompletionRequest, Task
from inferencemesh.routing import BackendCandidate, NoEligibleBackend, Router
from inferencemesh.service import InferenceService


def make_config(name: str) -> BackendConfig:
    return BackendConfig(
        name=name, public_model="alias", upstream_model="model", base_url=f"http://{name}/v1"
    )


def make_request() -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="alias", messages=[{"role": "user", "content": "hello"}], max_tokens=2
    )


async def test_failure_fallback_circuit_open_half_open_recovery() -> None:
    failing = True
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal failing
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "model"}]})
        calls.append(req.url.host)
        if req.url.host == "a" and failing:
            return httpx.Response(503, text="private upstream diagnostic")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": req.url.host}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    adapters = {
        name: HTTPBackend(make_config(name), transport=httpx.MockTransport(handler))
        for name in ("a", "b")
    }
    candidates = [
        BackendCandidate(name=name, model="alias", tasks=frozenset({Task.CHAT}), streaming=True)
        for name in adapters
    ]
    router = Router(candidates, failure_threshold=1, cooldown_seconds=0.01)
    service = InferenceService(router, adapters)
    try:
        result, decision = await service.complete_chat(make_request())
        assert result.choices[0].message.content == "b"
        assert decision.backend == "b"
        assert candidates[0].circuit_open
        assert calls == ["a", "b"]
        assert all(candidate.active == 0 for candidate in candidates)
        failing = False
        await asyncio.sleep(0.02)
        candidates[1].healthy = False
        result, decision = await service.complete_chat(make_request())
        assert decision.backend == "a"
        assert "half_open_probe" in decision.reason_codes
        assert not candidates[0].circuit_open
        assert candidates[0].predicted_latency_ms != 100
    finally:
        await service.aclose()


async def test_no_midstream_failover_and_no_false_done() -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "model"}]})
        calls.append(req.url.host)
        return httpx.Response(
            200,
            content=sse({"choices": [{"delta": {"content": "partial"}, "finish_reason": None}]}),
        )

    adapters = {
        name: HTTPBackend(make_config(name), transport=httpx.MockTransport(handler))
        for name in ("a", "b")
    }
    candidates = [
        BackendCandidate(name=name, model="alias", tasks=frozenset({Task.CHAT}), streaming=True)
        for name in adapters
    ]
    service = InferenceService(Router(candidates, failure_threshold=1), adapters)
    try:
        stream, decision, role = await service.prepare_stream(make_request())
        result = role + "".join([chunk async for chunk in stream])
        assert decision.backend == "a"
        assert calls == ["a"]
        assert "partial" in result and "upstream_error" in result
        assert "[DONE]" not in result
        assert candidates[0].circuit_open
        assert candidates[0].active == 0
    finally:
        await service.aclose()


async def test_disconnect_releases_backend_and_gateway_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = GatedStream()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "model"}]})
        return httpx.Response(200, stream=gate)

    monkeypatch.setattr(
        "inferencemesh.api.HTTPBackend",
        lambda config: HTTPBackend(config, transport=httpx.MockTransport(handler)),
    )
    app = create_app(Settings(backend_mode="http", backends=[make_config("a")]))
    body = json.dumps(
        {
            "model": "alias",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
            "max_tokens": 2,
        }
    ).encode()
    disconnected = asyncio.Event()
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and b"first" in message.get("body", b""):
            disconnected.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/chat/completions",
        "raw_path": b"/v1/chat/completions",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "server": ("localhost", 80),
        "client": ("127.0.0.1", 1234),
    }
    try:
        await asyncio.wait_for(app(scope, receive, send), 2)
        await asyncio.wait_for(gate.closed.wait(), 0.2)
        await asyncio.sleep(0)
        assert (await app.state.admission.snapshot()).active == 0
        assert app.state.router.candidates[0].active == 0
    finally:
        await app.state.service.aclose()


def test_model_registry_filters_and_capacity() -> None:
    router = Router(
        [BackendCandidate(name="a", model="alias", tasks=frozenset({Task.CHAT}), capacity=1)]
    )
    with pytest.raises(NoEligibleBackend):
        router.select(task=Task.CHAT, model="other")
    router.started("a")
    with pytest.raises(NoEligibleBackend):
        router.select(task=Task.CHAT, model="alias")
    router.finished("a", elapsed=0.1, outcome="cancelled")
    assert router.select(task=Task.CHAT, model="alias").backend == "a"


def test_saturated_healthy_backend_remains_ready() -> None:
    router = Router(
        [BackendCandidate(name="a", model="alias", tasks=frozenset({Task.CHAT}), capacity=1)]
    )
    router.started("a")
    assert router.is_ready()
    with pytest.raises(NoEligibleBackend):
        router.select(task=Task.CHAT)
    router.finished("a", elapsed=0.1, outcome="success")


def test_old_request_cannot_close_or_clear_half_open_probe() -> None:
    candidate = BackendCandidate(name="a", model="alias", tasks=frozenset({Task.CHAT}), capacity=3)
    router = Router([candidate], failure_threshold=1, cooldown_seconds=0.01)
    router.started("a")
    router.started("a")
    router.finished("a", elapsed=0.1, outcome="error")
    candidate.retry_at = 0
    decision = router.select(task=Task.CHAT)
    assert "half_open_probe" in decision.reason_codes
    router.started("a")
    assert candidate.probing
    router.finished("a", elapsed=0.1, outcome="success")
    assert candidate.circuit_open and candidate.probing
    with pytest.raises(NoEligibleBackend):
        router.select(task=Task.CHAT)
    router.finished("a", elapsed=0.1, outcome="cancelled", was_probe=True)
    assert not candidate.probing
    assert router.select(task=Task.CHAT).backend == "a"


async def test_stream_fails_over_before_content_and_preserves_combined_finish_usage() -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "model"}]})
        calls.append(req.url.host)
        if req.url.host == "a":
            return httpx.Response(503)
        return httpx.Response(
            200,
            content=b"".join(
                [
                    sse({"choices": [{"delta": {"content": "answer"}, "finish_reason": None}]}),
                    sse(
                        {
                            "choices": [{"delta": {}, "finish_reason": "length"}],
                            "usage": {
                                "prompt_tokens": 1,
                                "completion_tokens": 2,
                                "total_tokens": 3,
                            },
                        }
                    ),
                    b"data: [DONE]\n\n",
                ]
            ),
        )

    adapters = {
        name: HTTPBackend(make_config(name), transport=httpx.MockTransport(handler))
        for name in ("a", "b")
    }
    candidates = [
        BackendCandidate(name=name, model="alias", tasks=frozenset({Task.CHAT}), streaming=True)
        for name in adapters
    ]
    service = InferenceService(Router(candidates, failure_threshold=1), adapters)
    try:
        stream, decision, role = await service.prepare_stream(make_request())
        result = role + "".join([chunk async for chunk in stream])
        assert calls == ["a", "b"] and decision.backend == "b"
        assert '"finish_reason": "length"' in result
        assert '"usage"' not in result
        assert "[DONE]" in result
        assert all(candidate.active == 0 for candidate in candidates)
    finally:
        await service.aclose()
