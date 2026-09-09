"""Backend lifecycle, bounded failover, and streaming without midstream rerouting."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Any

from inferencemesh.backends.base import BackendAdapter, BackendCompletion, BackendUnavailable
from inferencemesh.domain import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    CompletionUsage,
    EmbeddingItem,
    EmbeddingResponse,
    Task,
)
from inferencemesh.metrics import REQUEST_LATENCY, REQUESTS, TIME_TO_FIRST_TOKEN
from inferencemesh.routing import RouteDecision, Router


class InferenceService:
    def __init__(
        self,
        router: Router,
        adapters: dict[str, BackendAdapter],
        *,
        health_interval_seconds: float = 5,
    ) -> None:
        self.router = router
        self._adapters = adapters
        self._health_interval = health_interval_seconds
        self._next_health = 0.0
        self._health_lock = asyncio.Lock()

    async def refresh_health(self) -> None:
        if time.monotonic() < self._next_health:
            return
        async with self._health_lock:
            if time.monotonic() < self._next_health:
                return
            results = await asyncio.gather(*(a.health() for a in self._adapters.values()))
            for candidate in self.router.candidates:
                candidate.healthy = dict(zip(self._adapters, results, strict=True))[candidate.name]
            self._next_health = time.monotonic() + self._health_interval

    async def aclose(self) -> None:
        await asyncio.gather(*(adapter.aclose() for adapter in self._adapters.values()))

    def _record(self, decision: RouteDecision, started: float, outcome: str, task: str) -> None:
        elapsed = time.perf_counter() - started
        self.router.finished(
            decision.backend,
            elapsed=elapsed,
            outcome=outcome,
            was_probe="half_open_probe" in decision.reason_codes,
        )
        REQUESTS.labels(task=task, backend=decision.backend, status=outcome).inc()
        REQUEST_LATENCY.labels(task=task, backend=decision.backend).observe(elapsed)

    def _response(
        self, request: ChatCompletionRequest, completion: BackendCompletion
    ) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            model=request.model,
            choices=[
                ChatChoice(
                    message=ChatMessage(role="assistant", content=completion.text),
                    finish_reason=completion.finish_reason,
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=completion.prompt_tokens,
                completion_tokens=completion.completion_tokens,
                total_tokens=completion.prompt_tokens + completion.completion_tokens,
            ),
            system_fingerprint=completion.system_fingerprint,
        )

    async def complete_chat(
        self, request: ChatCompletionRequest
    ) -> tuple[ChatCompletionResponse, RouteDecision]:
        await self.refresh_health()
        excluded: set[str] = set()
        while True:
            decision = self.router.select(
                task=Task.CHAT, model=request.model, exclude=frozenset(excluded)
            )
            self.router.started(decision.backend)
            started = time.perf_counter()
            outcome = "cancelled"
            try:
                completion = await self._adapters[decision.backend].complete(request)
                outcome = "success"
                return self._response(request, completion), decision
            except BackendUnavailable:
                outcome = "error"
                excluded.add(decision.backend)
            finally:
                self._record(decision, started, outcome, "chat")

    async def prepare_stream(
        self,
        request: ChatCompletionRequest,
    ) -> tuple[AsyncGenerator[str, None], RouteDecision, str]:
        await self.refresh_health()
        excluded: set[str] = set()
        while True:
            decision = self.router.select(
                task=Task.CHAT,
                model=request.model,
                require_streaming=True,
                exclude=frozenset(excluded),
            )
            self.router.started(decision.backend)
            started = time.perf_counter()
            stream = self._adapters[decision.backend].stream(request)
            try:
                first = await anext(stream)
            except (BackendUnavailable, StopAsyncIteration):
                await stream.aclose()
                self._record(decision, started, "error", "chat")
                excluded.add(decision.backend)
                continue
            except BaseException:
                await stream.aclose()
                self._record(decision, started, "cancelled", "chat")
                raise
            rendered = self._stream(request, decision, stream, first, started)
            role_chunk = await anext(rendered)
            return rendered, decision, role_chunk

    async def _stream(
        self,
        request: ChatCompletionRequest,
        decision: RouteDecision,
        upstream: AsyncGenerator[dict[str, Any], None],
        first: dict[str, Any],
        started: float,
    ) -> AsyncGenerator[str, None]:
        outcome = "cancelled"
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        base = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": request.model,
        }
        first_content = True
        try:
            yield (
                "data: "
                + json.dumps(
                    {
                        **base,
                        "choices": [
                            {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
                        ],
                    }
                )
                + "\n\n"
            )
            async with aclosing(upstream):
                chunk: dict[str, Any] | None = first
                while chunk is not None:
                    if first_content and any(
                        c.get("delta", {}).get("content") for c in chunk.get("choices", [])
                    ):
                        TIME_TO_FIRST_TOKEN.labels(backend=decision.backend).observe(
                            time.perf_counter() - started
                        )
                        first_content = False
                    outgoing = dict(chunk)
                    if not (request.stream_options and request.stream_options.include_usage):
                        outgoing.pop("usage", None)
                    if outgoing.get("choices") or outgoing.get("usage"):
                        yield "data: " + json.dumps({**outgoing, **base}) + "\n\n"
                    chunk = await anext(upstream, None)
            outcome = "success"
            yield "data: [DONE]\n\n"
        except BackendUnavailable:
            outcome = "error"
            # Headers and possibly content are already sent. Do not retry or emit a false [DONE].
            yield (
                "data: "
                + json.dumps(
                    {"error": {"type": "upstream_error", "message": "backend stream interrupted"}}
                )
                + "\n\n"
            )
        finally:
            try:
                await asyncio.shield(upstream.aclose())
            finally:
                self._record(decision, started, outcome, "chat")

    async def embed(self, texts: list[str], model: str) -> tuple[EmbeddingResponse, RouteDecision]:
        await self.refresh_health()
        excluded: set[str] = set()
        while True:
            decision = self.router.select(
                task=Task.EMBEDDING, model=model, exclude=frozenset(excluded)
            )
            self.router.started(decision.backend)
            started = time.perf_counter()
            outcome = "cancelled"
            try:
                result = await self._adapters[decision.backend].embed(texts)
                outcome = "success"
                return EmbeddingResponse(
                    data=[
                        EmbeddingItem(embedding=vector, index=i)
                        for i, vector in enumerate(result.vectors)
                    ],
                    model=model,
                    usage=CompletionUsage(
                        prompt_tokens=result.prompt_tokens,
                        completion_tokens=0,
                        total_tokens=result.prompt_tokens,
                    ),
                ), decision
            except BackendUnavailable:
                outcome = "error"
                excluded.add(decision.backend)
            finally:
                self._record(decision, started, outcome, "embedding")
