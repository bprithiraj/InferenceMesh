"""Transport-neutral orchestration of routing and backend calls."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator

from inferencemesh.backends.base import BackendAdapter
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
    def __init__(self, router: Router, adapters: dict[str, BackendAdapter]) -> None:
        self.router = router
        self._adapters = adapters

    def route_chat(self, *, stream: bool) -> RouteDecision:
        return self.router.select(task=Task.CHAT, require_streaming=stream)

    def route_embedding(self) -> RouteDecision:
        return self.router.select(task=Task.EMBEDDING)

    async def complete_chat(
        self,
        request: ChatCompletionRequest,
        decision: RouteDecision,
    ) -> ChatCompletionResponse:
        started = time.perf_counter()
        adapter = self._adapters[decision.backend]
        try:
            completion = await adapter.complete(request)
        except Exception:
            REQUESTS.labels(task="chat", backend=decision.backend, status="error").inc()
            raise
        else:
            REQUESTS.labels(task="chat", backend=decision.backend, status="success").inc()
            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex}",
                model=request.model,
                choices=[
                    ChatChoice(
                        message=ChatMessage(role="assistant", content=completion.text),
                        finish_reason="length" if completion.finish_reason == "length" else "stop",
                    )
                ],
                usage=CompletionUsage(
                    prompt_tokens=completion.prompt_tokens,
                    completion_tokens=completion.completion_tokens,
                    total_tokens=completion.prompt_tokens + completion.completion_tokens,
                ),
                system_fingerprint=completion.system_fingerprint,
            )
        finally:
            REQUEST_LATENCY.labels(task="chat", backend=decision.backend).observe(
                time.perf_counter() - started
            )

    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        decision: RouteDecision,
    ) -> AsyncIterator[str]:
        started = time.perf_counter()
        first_token = True
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        adapter = self._adapters[decision.backend]

        role_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": request.model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(role_chunk)}\n\n"

        try:
            async for text in adapter.stream(request):
                if first_token:
                    TIME_TO_FIRST_TOKEN.labels(backend=decision.backend).observe(
                        time.perf_counter() - started
                    )
                    first_token = False
                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": request.model,
                    "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": request.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            REQUESTS.labels(task="chat", backend=decision.backend, status="error").inc()
            raise
        else:
            REQUESTS.labels(task="chat", backend=decision.backend, status="success").inc()
        finally:
            REQUEST_LATENCY.labels(task="chat", backend=decision.backend).observe(
                time.perf_counter() - started
            )

    async def embed(
        self,
        texts: list[str],
        model: str,
        decision: RouteDecision,
    ) -> EmbeddingResponse:
        started = time.perf_counter()
        adapter = self._adapters[decision.backend]
        try:
            vectors = await adapter.embed(texts)
        except Exception:
            REQUESTS.labels(task="embedding", backend=decision.backend, status="error").inc()
            raise
        else:
            token_count = sum(len(text.split()) for text in texts)
            REQUESTS.labels(task="embedding", backend=decision.backend, status="success").inc()
            return EmbeddingResponse(
                data=[
                    EmbeddingItem(embedding=vector, index=index)
                    for index, vector in enumerate(vectors)
                ],
                model=model,
                usage=CompletionUsage(
                    prompt_tokens=token_count,
                    completion_tokens=0,
                    total_tokens=token_count,
                ),
            )
        finally:
            REQUEST_LATENCY.labels(task="embedding", backend=decision.backend).observe(
                time.perf_counter() - started
            )
