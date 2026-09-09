"""Explicit deterministic demo/test backend; it does not run a language model."""

from __future__ import annotations

import asyncio
import hashlib
import math
from collections.abc import AsyncGenerator
from typing import Any

from inferencemesh.backends.base import BackendCompletion, BackendEmbedding
from inferencemesh.domain import ChatCompletionRequest


class FakeBackend:
    name = "deterministic-local"

    def __init__(self, *, token_delay_seconds: float = 0.0) -> None:
        self._token_delay_seconds = token_delay_seconds

    async def complete(self, request: ChatCompletionRequest) -> BackendCompletion:
        latest = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        text = (
            "InferenceMesh accepted the request and selected the deterministic local backend. "
            f"Prompt preview: {' '.join(latest.strip().split())[:160]}"
        )
        words = text.split()
        limited = words[: request.max_tokens]
        return BackendCompletion(
            text=" ".join(limited),
            prompt_tokens=sum(len(m.content.split()) for m in request.messages),
            completion_tokens=len(limited),
            finish_reason="length" if len(limited) < len(words) else "stop",
            system_fingerprint="fake-v2",
        )

    async def stream(self, request: ChatCompletionRequest) -> AsyncGenerator[dict[str, Any], None]:
        completion = await self.complete(request)
        words = completion.text.split()
        for index, word in enumerate(words):
            if self._token_delay_seconds:
                await asyncio.sleep(self._token_delay_seconds)
            suffix = "" if index == len(words) - 1 else " "
            yield {
                "choices": [
                    {"index": 0, "delta": {"content": word + suffix}, "finish_reason": None}
                ]
            }
        yield {"choices": [{"index": 0, "delta": {}, "finish_reason": completion.finish_reason}]}
        yield {
            "choices": [],
            "usage": {
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "total_tokens": completion.prompt_tokens + completion.completion_tokens,
            },
        }

    async def embed(self, texts: list[str]) -> BackendEmbedding:
        return BackendEmbedding(
            [self._embedding(text) for text in texts], sum(len(text.split()) for text in texts)
        )

    @staticmethod
    def _embedding(text: str, dimensions: int = 16) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [((digest[index] / 255.0) * 2.0) - 1.0 for index in range(dimensions)]
        norm = math.sqrt(sum(value * value for value in raw)) or 1.0
        return [round(value / norm, 8) for value in raw]

    async def health(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass
