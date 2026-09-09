"""Transport-neutral inference domain models."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Task(StrEnum):
    CHAT = "chat"
    EMBEDDING = "embedding"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = ""


class StreamOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_usage: bool = False


class ChatCompletionRequest(BaseModel):
    """Supported subset of the OpenAI Chat Completions request."""

    model_config = ConfigDict(extra="forbid")

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    stream_options: StreamOptions | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=128, ge=1)


class CompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatChoice]
    usage: CompletionUsage
    system_fingerprint: str | None = None


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    input: str | list[str]

    @model_validator(mode="after")
    def validate_input(self) -> EmbeddingRequest:
        values = [self.input] if isinstance(self.input, str) else self.input
        if not values or any(not value for value in values):
            raise ValueError("input must contain at least one non-empty string")
        return self


class EmbeddingItem(BaseModel):
    object: Literal["embedding"] = "embedding"
    embedding: list[float]
    index: int


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[EmbeddingItem]
    model: str
    usage: CompletionUsage


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "inferencemesh"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]
