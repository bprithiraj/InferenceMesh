"""OpenAI-compatible HTTP adapter for local Ollama or self-hosted vLLM."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from inferencemesh.backends.base import BackendCompletion, BackendEmbedding, BackendUnavailable
from inferencemesh.config import BackendConfig
from inferencemesh.domain import ChatCompletionRequest


class HTTPBackend:
    def __init__(self, config: BackendConfig, *, transport: httpx.AsyncBaseTransport | None = None):
        self.name = config.name
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else {},
            timeout=httpx.Timeout(config.timeout_seconds, connect=5),
            transport=transport,
            follow_redirects=False,
        )

    def _payload(self, request: ChatCompletionRequest, *, stream: bool) -> dict[str, Any]:
        payload = request.model_dump(exclude={"stream_options"})
        payload.update(model=self._config.upstream_model, stream=stream)
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    async def complete(self, request: ChatCompletionRequest) -> BackendCompletion:
        try:
            response = await self._client.post(
                "chat/completions", json=self._payload(request, stream=False)
            )
            response.raise_for_status()
            body = response.json()
            choice = body["choices"][0]
            usage = body["usage"]
            text = choice["message"].get("content") or ""
            reason = choice["finish_reason"]
            if not isinstance(text, str) or not isinstance(reason, str) or not reason:
                raise ValueError("invalid completion shape")
            if int(usage["prompt_tokens"]) < 0 or int(usage["completion_tokens"]) < 0:
                raise ValueError("invalid completion usage")
            return BackendCompletion(
                text=text,
                prompt_tokens=int(usage["prompt_tokens"]),
                completion_tokens=int(usage["completion_tokens"]),
                finish_reason=reason,
                system_fingerprint=body.get("system_fingerprint"),
            )
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
        ) as exc:
            raise BackendUnavailable(f"backend {self.name} failed") from exc

    async def stream(self, request: ChatCompletionRequest) -> AsyncGenerator[dict[str, Any], None]:
        finished = False
        try:
            async with self._client.stream(
                "POST", "chat/completions", json=self._payload(request, stream=True)
            ) as response:
                response.raise_for_status()
                data: list[str] = []
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        payload = "\n".join(data)
                        data.clear()
                        if payload == "[DONE]":
                            if not finished:
                                raise BackendUnavailable("upstream ended without a finish reason")
                            return
                        chunk = json.loads(payload)
                        if not isinstance(chunk, dict) or "error" in chunk:
                            raise BackendUnavailable("upstream returned an invalid stream event")
                        choices = chunk.get("choices", [])
                        if not isinstance(choices, list):
                            raise BackendUnavailable("upstream returned invalid choices")
                        if any(
                            not isinstance(choice, dict)
                            or not isinstance(choice.get("delta", {}), dict)
                            for choice in choices
                        ):
                            raise BackendUnavailable("upstream returned invalid choice data")
                        finished = finished or any(
                            choice.get("finish_reason") for choice in choices
                        )
                        # Ignore role-only events so the gateway can still fail over before output.
                        if chunk.get("usage") or any(
                            choice.get("delta", {}).get("content") or choice.get("finish_reason")
                            for choice in choices
                        ):
                            yield chunk
                raise BackendUnavailable("upstream stream ended before [DONE]")
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
        ) as exc:
            raise BackendUnavailable(f"backend {self.name} stream failed") from exc

    async def embed(self, texts: list[str]) -> BackendEmbedding:
        try:
            response = await self._client.post(
                "embeddings", json={"model": self._config.upstream_model, "input": texts}
            )
            response.raise_for_status()
            body = response.json()
            items = sorted(body["data"], key=lambda item: item["index"])
            if len(items) != len(texts):
                raise ValueError("embedding count mismatch")
            return BackendEmbedding(
                vectors=[[float(value) for value in item["embedding"]] for item in items],
                prompt_tokens=int(body["usage"]["prompt_tokens"]),
            )
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
        ) as exc:
            raise BackendUnavailable(f"backend {self.name} embedding failed") from exc

    async def health(self) -> bool:
        try:
            response = await self._client.get("models", timeout=3)
            response.raise_for_status()
            return any(
                item["id"] == self._config.upstream_model for item in response.json()["data"]
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return False

    async def aclose(self) -> None:
        await self._client.aclose()
