"""FastAPI transport for the initial InferenceMesh gateway."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import RequestResponseEndpoint

from inferencemesh import __version__
from inferencemesh.admission import AdmissionController, AdmissionLease, AdmissionRejected
from inferencemesh.auth import ApiKeyAuthenticator, Principal
from inferencemesh.backends import FakeBackend
from inferencemesh.config import Settings, get_settings
from inferencemesh.domain import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelCard,
    ModelList,
    Task,
)
from inferencemesh.metrics import ADMISSION_ACTIVE, ADMISSION_REJECTIONS, ADMISSION_WAITING
from inferencemesh.routing import BackendCandidate, NoEligibleBackend, Router
from inferencemesh.service import InferenceService

LOGGER = logging.getLogger("inferencemesh")

# These are public API model IDs, rather than backend implementation names.
# Keeping the allow-list per task prevents a request from being silently routed
# to a backend that does not actually serve the requested capability.
SUPPORTED_MODELS: dict[Task, frozenset[str]] = {
    Task.CHAT: frozenset({"inferencemesh-local"}),
    Task.EMBEDDING: frozenset({"inferencemesh-embedding-local"}),
}


def _error(status_code: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type, "param": None, "code": None}},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    backend = FakeBackend(token_delay_seconds=settings.fake_token_delay_ms / 1_000)
    router = Router(
        [
            BackendCandidate(
                name=backend.name,
                model="inferencemesh-local",
                tasks=frozenset({Task.CHAT, Task.EMBEDDING}),
                streaming=True,
                predicted_latency_ms=25,
                metadata={"engine": "deterministic-fake"},
            )
        ]
    )
    service = InferenceService(router, {backend.name: backend})
    admission = AdmissionController(
        max_concurrent=settings.max_concurrent_requests,
        max_concurrent_per_tenant=settings.max_concurrent_per_tenant,
        max_queue_depth=settings.max_queue_depth,
        queue_wait_seconds=settings.queue_wait_ms / 1_000,
    )
    authenticator = ApiKeyAuthenticator(settings)

    app = FastAPI(
        title="InferenceMesh",
        version=__version__,
        description="SLO-aware, OpenAI-compatible inference control plane.",
    )
    app.state.settings = settings
    app.state.router = router
    app.state.service = service
    app.state.admission = admission

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", f"req-{uuid.uuid4().hex}")
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-inferencemesh-request-id"] = request_id
        return response

    @app.exception_handler(AdmissionRejected)
    async def admission_error(_request: Request, exc: AdmissionRejected) -> JSONResponse:
        reason = "queue_full" if "full" in str(exc) else "queue_timeout"
        ADMISSION_REJECTIONS.labels(reason=reason).inc()
        response = _error(status.HTTP_429_TOO_MANY_REQUESTS, str(exc), "capacity_error")
        response.headers["Retry-After"] = "1"
        return response

    @app.exception_handler(NoEligibleBackend)
    async def route_error(_request: Request, exc: NoEligibleBackend) -> JSONResponse:
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), "routing_error")

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> Response:
        if not router.is_ready():
            return _error(503, "no eligible serving backend", "readiness_error")
        return JSONResponse({"status": "ready", "policy_version": router.policy_version})

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/demo/metrics/summary", tags=["demo"])
    async def metrics_summary() -> dict[str, int | str]:
        snapshot = await admission.snapshot()
        return {
            "status": "ready" if router.is_ready() else "degraded",
            "active_requests": snapshot.active,
            "queued_requests": snapshot.waiting,
            "active_limit": snapshot.max_active,
            "queue_limit": snapshot.max_waiting,
            "policy_version": router.policy_version,
        }

    @app.get("/v1/models", response_model=ModelList, tags=["openai"])
    async def models(
        _principal: Principal = Depends(authenticator.authenticate),
    ) -> ModelList:
        return ModelList(
            data=[
                ModelCard(id="inferencemesh-local"),
                ModelCard(id="inferencemesh-embedding-local"),
            ]
        )

    def validate_chat(request: ChatCompletionRequest) -> None:
        validate_model(request.model, Task.CHAT)
        input_chars = sum(len(message.content) for message in request.messages)
        if input_chars > settings.max_input_chars:
            raise HTTPException(status_code=400, detail="input exceeds configured character limit")
        if request.max_tokens > settings.max_output_tokens:
            raise HTTPException(status_code=400, detail="max_tokens exceeds configured limit")

    def validate_model(model: str, task: Task) -> None:
        if model not in SUPPORTED_MODELS[task]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"model '{model}' is not available for {task.value}",
            )

    async def refresh_admission_metrics() -> None:
        snapshot = await admission.snapshot()
        ADMISSION_ACTIVE.set(snapshot.active)
        ADMISSION_WAITING.set(snapshot.waiting)

    @app.post(
        "/v1/chat/completions",
        response_model=ChatCompletionResponse,
        tags=["openai"],
    )
    async def chat_completions(
        request: ChatCompletionRequest,
        principal: Principal = Depends(authenticator.authenticate),
    ) -> Response:
        validate_chat(request)
        decision = service.route_chat(stream=request.stream)
        lease = await admission.acquire(principal.tenant_id)
        await refresh_admission_metrics()
        headers = {
            "x-inferencemesh-backend": decision.backend,
            "x-inferencemesh-model-version": decision.model,
            "x-inferencemesh-policy-version": decision.policy_version,
            "x-inferencemesh-route-reason": ",".join(decision.reason_codes),
        }

        if request.stream:

            async def stream_with_release() -> AsyncIterator[str]:
                try:
                    async for chunk in service.stream_chat(request, decision):
                        yield chunk
                finally:
                    await lease.release()
                    await refresh_admission_metrics()

            return StreamingResponse(
                stream_with_release(),
                media_type="text/event-stream",
                headers=headers,
            )

        try:
            result = await service.complete_chat(request, decision)
            return JSONResponse(result.model_dump(mode="json"), headers=headers)
        finally:
            await lease.release()
            await refresh_admission_metrics()

    @app.post("/v1/embeddings", response_model=EmbeddingResponse, tags=["openai"])
    async def embeddings(
        request: EmbeddingRequest,
        principal: Principal = Depends(authenticator.authenticate),
    ) -> Response:
        texts = [request.input] if isinstance(request.input, str) else request.input
        validate_model(request.model, Task.EMBEDDING)
        if sum(len(text) for text in texts) > settings.max_input_chars:
            raise HTTPException(status_code=400, detail="input exceeds configured character limit")
        decision = service.route_embedding()
        lease: AdmissionLease = await admission.acquire(principal.tenant_id)
        await refresh_admission_metrics()
        try:
            result = await service.embed(texts, request.model, decision)
            return JSONResponse(
                result.model_dump(mode="json"),
                headers={
                    "x-inferencemesh-backend": decision.backend,
                    "x-inferencemesh-model-version": decision.model,
                    "x-inferencemesh-policy-version": decision.policy_version,
                },
            )
        finally:
            await lease.release()
            await refresh_admission_metrics()

    return app
