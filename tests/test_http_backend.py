import asyncio
import json

import httpx
import pytest

from inferencemesh.backends.base import BackendUnavailable
from inferencemesh.backends.http import HTTPBackend
from inferencemesh.config import BackendConfig
from inferencemesh.domain import ChatCompletionRequest


def request() -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="alias",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=2,
        stream_options={"include_usage": True},
    )


def config() -> BackendConfig:
    return BackendConfig(
        name="server",
        public_model="alias",
        upstream_model="real-model",
        base_url="http://upstream/v1",
        api_key="private",
    )


def sse(chunk: object) -> bytes:
    return ("data: " + json.dumps(chunk) + "\n\n").encode()


async def test_real_http_payload_model_usage_and_embeddings() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer private"
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "real-model"}]})
        payload = json.loads(req.content)
        assert payload["model"] == "real-model"
        if req.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "data": [{"index": 0, "embedding": [0.2, 0.4]}],
                    "usage": {"prompt_tokens": 3},
                },
            )
        assert "stream_options" not in payload
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "actual answer"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                "system_fingerprint": "revision",
            },
        )

    backend = HTTPBackend(config(), transport=httpx.MockTransport(handler))
    try:
        assert await backend.health()
        completion = await backend.complete(request())
        assert (completion.text, completion.finish_reason, completion.prompt_tokens) == (
            "actual answer",
            "length",
            3,
        )
        assert completion.system_fingerprint == "revision"
        embedding = await backend.embed(["hello"])
        assert embedding.vectors == [[0.2, 0.4]]
        assert embedding.prompt_tokens == 3
    finally:
        await backend.aclose()


async def test_stream_preserves_terminal_reason_and_usage() -> None:
    content = b"".join(
        [
            sse({"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]}),
            sse({"choices": [{"delta": {"content": "answer"}, "finish_reason": None}]}),
            sse({"choices": [{"delta": {}, "finish_reason": "length"}]}),
            sse(
                {
                    "choices": [],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                }
            ),
            b"data: [DONE]\n\n",
        ]
    )

    def handler(req: httpx.Request) -> httpx.Response:
        assert json.loads(req.content)["stream_options"] == {"include_usage": True}
        return httpx.Response(200, content=content)

    backend = HTTPBackend(config(), transport=httpx.MockTransport(handler))
    try:
        chunks = [chunk async for chunk in backend.stream(request())]
        assert len(chunks) == 3
        assert chunks[1]["choices"][0]["finish_reason"] == "length"
        assert chunks[2]["usage"]["total_tokens"] == 5
    finally:
        await backend.aclose()


async def test_incomplete_stream_is_not_reported_as_success() -> None:
    backend = HTTPBackend(
        config(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=sse({"choices": [{"delta": {"content": "partial"}}]})
            )
        ),
    )
    try:
        with pytest.raises(BackendUnavailable, match="before"):
            _ = [chunk async for chunk in backend.stream(request())]
    finally:
        await backend.aclose()


class GatedStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = asyncio.Event()
        self.waiting = asyncio.Event()

    async def __aiter__(self):
        yield sse({"choices": [{"delta": {"content": "first"}, "finish_reason": None}]})
        self.waiting.set()
        await asyncio.Event().wait()

    async def aclose(self) -> None:
        self.closed.set()


async def test_cancelled_stream_closes_http_connection() -> None:
    gate = GatedStream()
    backend = HTTPBackend(
        config(), transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=gate))
    )

    async def consume() -> None:
        async for _ in backend.stream(request()):
            pass

    task = asyncio.create_task(consume())
    await gate.waiting.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(gate.closed.wait(), 0.1)
    await backend.aclose()


@pytest.mark.parametrize(
    "content",
    [
        {
            "choices": [{"message": {"content": 42}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
        {
            "choices": [{"message": [], "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    ],
)
async def test_malformed_upstream_completion_is_sanitized(content: object) -> None:
    backend = HTTPBackend(
        config(), transport=httpx.MockTransport(lambda _: httpx.Response(200, json=content))
    )
    try:
        with pytest.raises(BackendUnavailable, match="backend server failed"):
            await backend.complete(request())
    finally:
        await backend.aclose()
