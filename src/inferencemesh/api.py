"""OpenAI-compatible gateway with bounded admission and explicit backend profiles."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.background import BackgroundTask
from starlette.middleware.base import RequestResponseEndpoint

from inferencemesh import __version__
from inferencemesh.admission import AdmissionController, AdmissionRejected
from inferencemesh.auth import ApiKeyAuthenticator, Principal
from inferencemesh.backends.base import BackendAdapter
from inferencemesh.backends.fake import FakeBackend
from inferencemesh.backends.http import HTTPBackend
from inferencemesh.budget import RequestBudget
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
from inferencemesh.routing import BackendCandidate, NoEligibleBackend, RouteDecision, Router
from inferencemesh.service import InferenceService


def _error(status_code: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type, "param": None, "code": None}},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    adapters: dict[str, BackendAdapter] = {}
    candidates: list[BackendCandidate] = []
    supported: dict[Task, set[str]] = {task: set() for task in Task}
    if settings.backend_mode == "demo":
        fake = FakeBackend(token_delay_seconds=settings.fake_token_delay_ms / 1000)
        adapters[fake.name] = fake
        supported[Task.CHAT].add("inferencemesh-local")
        supported[Task.EMBEDDING].add("inferencemesh-embedding-local")
        candidates.append(
            BackendCandidate(
                name=fake.name,
                model="inferencemesh-local",
                tasks=frozenset(Task),
                streaming=True,
                predicted_latency_ms=25,
                capacity=settings.max_concurrent_requests,
                public_models=frozenset({"inferencemesh-local", "inferencemesh-embedding-local"}),
                metadata={"engine": "deterministic-demo"},
            )
        )
    else:
        for config in settings.backends:
            adapters[config.name] = HTTPBackend(config)
            candidates.append(
                BackendCandidate(
                    name=config.name,
                    model=config.public_model,
                    tasks=frozenset(config.tasks),
                    streaming=Task.CHAT in config.tasks,
                    healthy=False,
                    capacity=config.capacity,
                    metadata={"engine": "openai-compatible-http"},
                )
            )
            for task in config.tasks:
                supported[task].add(config.public_model)
    router = Router(
        candidates,
        policy_version="local-v1" if settings.backend_mode == "demo" else "http-v2",
        failure_threshold=settings.circuit_failure_threshold,
        cooldown_seconds=settings.circuit_cooldown_seconds,
    )
    service = InferenceService(
        router, adapters, health_interval_seconds=settings.health_interval_seconds
    )
    admission = AdmissionController(
        max_concurrent=settings.max_concurrent_requests,
        max_concurrent_per_tenant=settings.max_concurrent_per_tenant,
        max_queue_depth=settings.max_queue_depth,
        queue_wait_seconds=settings.queue_wait_ms / 1000,
    )
    authenticator = ApiKeyAuthenticator(settings)
    budget = RequestBudget(settings.requests_per_minute, settings.output_tokens_per_minute)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await service.refresh_health()
        try:
            yield
        finally:
            await service.aclose()

    app = FastAPI(title="InferenceMesh", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.router = router
    app.state.service = service
    app.state.admission = admission

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Do not reflect arbitrary caller-controlled strings into response headers/logs.
        request_id = f"req-{uuid.uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-inferencemesh-request-id"] = request_id
        return response

    @app.exception_handler(AdmissionRejected)
    async def admission_error(_request: Request, exc: AdmissionRejected) -> JSONResponse:
        reason = "queue_full" if "full" in str(exc) else "queue_timeout"
        ADMISSION_REJECTIONS.labels(reason=reason).inc()
        response = _error(429, str(exc), "capacity_error")
        response.headers["Retry-After"] = "1"
        return response

    @app.exception_handler(NoEligibleBackend)
    async def route_error(_request: Request, exc: NoEligibleBackend) -> JSONResponse:
        return _error(503, str(exc), "routing_error")

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> Response:
        await service.refresh_health()
        if not router.is_ready():
            return _error(503, "no eligible serving backend", "readiness_error")
        return JSONResponse({"status": "ready", "policy_version": router.policy_version})

    async def refresh_admission_metrics() -> None:
        snapshot = await admission.snapshot()
        ADMISSION_ACTIVE.set(snapshot.active)
        ADMISSION_WAITING.set(snapshot.waiting)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(
        _principal: Principal = Depends(authenticator.authenticate_metrics),
    ) -> Response:
        await refresh_admission_metrics()
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
    async def models(_principal: Principal = Depends(authenticator.authenticate)) -> ModelList:
        return ModelList(
            data=[ModelCard(id=model) for model in sorted(set().union(*supported.values()))]
        )

    def validate_model(model: str, task: Task) -> None:
        if model not in supported[task]:
            raise HTTPException(404, detail=f"model '{model}' is not available for {task.value}")

    def route_headers(decision: RouteDecision) -> dict[str, str]:
        return {
            "x-inferencemesh-backend": decision.backend,
            "x-inferencemesh-model-version": decision.model,
            "x-inferencemesh-policy-version": decision.policy_version,
            "x-inferencemesh-route-reason": ",".join(decision.reason_codes),
        }

    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse, tags=["openai"])
    async def chat_completions(
        request: ChatCompletionRequest,
        principal: Principal = Depends(authenticator.authenticate),
    ) -> Response:
        validate_model(request.model, Task.CHAT)
        if sum(len(message.content) for message in request.messages) > settings.max_input_chars:
            raise HTTPException(400, detail="input exceeds configured character limit")
        if request.max_tokens > settings.max_output_tokens:
            raise HTTPException(400, detail="max_tokens exceeds configured limit")
        await budget.reserve(principal.tenant_id, request.max_tokens)
        lease = await admission.acquire(principal.tenant_id)
        if request.stream:
            try:
                stream, decision, role_chunk = await service.prepare_stream(request)
            except BaseException:
                await lease.release()
                raise

            async def cleanup() -> None:
                try:
                    await stream.aclose()
                finally:
                    await lease.release()

            async def stream_with_release() -> AsyncIterator[str]:
                try:
                    yield role_chunk
                    async for chunk in stream:
                        yield chunk
                finally:
                    await cleanup()

            return StreamingResponse(
                stream_with_release(),
                media_type="text/event-stream",
                headers={
                    **route_headers(decision),
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
                background=BackgroundTask(cleanup),
            )
        try:
            result, decision = await service.complete_chat(request)
            return JSONResponse(result.model_dump(mode="json"), headers=route_headers(decision))
        finally:
            await lease.release()

    @app.post("/v1/embeddings", response_model=EmbeddingResponse, tags=["openai"])
    async def embeddings(
        request: EmbeddingRequest,
        principal: Principal = Depends(authenticator.authenticate),
    ) -> Response:
        texts = [request.input] if isinstance(request.input, str) else request.input
        validate_model(request.model, Task.EMBEDDING)
        if sum(len(text) for text in texts) > settings.max_input_chars:
            raise HTTPException(400, detail="input exceeds configured character limit")
        await budget.reserve(principal.tenant_id)
        lease = await admission.acquire(principal.tenant_id)
        try:
            result, decision = await service.embed(texts, request.model)
            return JSONResponse(result.model_dump(mode="json"), headers=route_headers(decision))
        finally:
            await lease.release()

    return app
