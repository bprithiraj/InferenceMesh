"""Backend adapter protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from inferencemesh.domain import ChatCompletionRequest


@dataclass(frozen=True, slots=True)
class BackendCompletion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str = "stop"
    system_fingerprint: str | None = None


class BackendAdapter(Protocol):
    name: str

    async def complete(self, request: ChatCompletionRequest) -> BackendCompletion: ...

    def stream(self, request: ChatCompletionRequest) -> AsyncIterator[str]: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def health(self) -> bool: ...
