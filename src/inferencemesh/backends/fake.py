"""Deterministic local backend used to exercise the complete gateway contract."""

from __future__ import annotations

import asyncio
import hashlib
import math
from collections.abc import AsyncIterator

from inferencemesh.backends.base import BackendCompletion
from inferencemesh.domain import ChatCompletionRequest


class FakeBackend:
    """A predictable backend for local development, CI, demos, and fault tests."""

    name = "deterministic-local"

    def __init__(self, *, token_delay_seconds: float = 0.0) -> None:
        self._token_delay_seconds = token_delay_seconds

    @staticmethod
    def _answer(request: ChatCompletionRequest) -> str:
        latest_user = next(
            message.content for message in reversed(request.messages) if message.role == "user"
        )
        summary = " ".join(latest_user.strip().split())[:160]
        return (
            "InferenceMesh accepted the request and selected the deterministic local backend. "
            f"Prompt preview: {summary}"
        )

    async def complete(self, request: ChatCompletionRequest) -> BackendCompletion:
        text = self._answer(request)
        words = text.split()
        limited_words = words[: request.max_tokens]
        limited_text = " ".join(limited_words)
        finish_reason = "length" if len(limited_words) < len(words) else "stop"
        return BackendCompletion(
            text=limited_text,
            prompt_tokens=sum(len(message.content.split()) for message in request.messages),
            completion_tokens=len(limited_words),
            finish_reason=finish_reason,
            system_fingerprint="fake-v1",
        )

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        completion = await self.complete(request)
        words = completion.text.split()
        for index, word in enumerate(words):
            if self._token_delay_seconds:
                await asyncio.sleep(self._token_delay_seconds)
            suffix = "" if index == len(words) - 1 else " "
            yield word + suffix

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embedding(text) for text in texts]

    @staticmethod
    def _embedding(text: str, dimensions: int = 16) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [((digest[index] / 255.0) * 2.0) - 1.0 for index in range(dimensions)]
        norm = math.sqrt(sum(value * value for value in raw)) or 1.0
        return [round(value / norm, 8) for value in raw]

    async def health(self) -> bool:
        return True
