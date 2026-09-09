"""Transport-neutral backend responses and explicit upstream failures."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, Protocol

from inferencemesh.domain import ChatCompletionRequest


class BackendUnavailable(RuntimeError):
    """Upstream failed; its response body and credentials must stay private."""


@dataclass(frozen=True, slots=True)
class BackendCompletion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str = "stop"
    system_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class BackendEmbedding:
    vectors: list[list[float]]
    prompt_tokens: int


class BackendAdapter(Protocol):
    name: str

    async def complete(self, request: ChatCompletionRequest) -> BackendCompletion: ...
    def stream(self, request: ChatCompletionRequest) -> AsyncGenerator[dict[str, Any], None]: ...
    async def embed(self, texts: list[str]) -> BackendEmbedding: ...
    async def health(self) -> bool: ...
    async def aclose(self) -> None: ...
