"""Explainable routing with measured load and recoverable circuit breakers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from inferencemesh.domain import Task


class NoEligibleBackend(RuntimeError):
    """No matching healthy backend can accept this request."""


@dataclass(slots=True)
class BackendCandidate:
    name: str
    model: str
    tasks: frozenset[Task]
    streaming: bool = False
    healthy: bool = True
    circuit_open: bool = False
    predicted_latency_ms: float = 100.0
    queue_utilization: float = 0.0
    estimated_cost: float = 0.0
    quality_penalty: float = 0.0
    recent_error_rate: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)
    public_models: frozenset[str] = frozenset()
    capacity: int = 4
    active: int = 0
    failures: int = 0
    retry_at: float = 0
    probing: bool = False


@dataclass(frozen=True, slots=True)
class RouteDecision:
    backend: str
    model: str
    score: float
    reason_codes: tuple[str, ...]
    policy_version: str


class Router:
    def __init__(
        self,
        candidates: list[BackendCandidate],
        *,
        policy_version: str = "local-v1",
        failure_threshold: int = 2,
        cooldown_seconds: float = 5,
    ) -> None:
        self._candidates = {candidate.name: candidate for candidate in candidates}
        self.policy_version = policy_version
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    @property
    def candidates(self) -> tuple[BackendCandidate, ...]:
        return tuple(self._candidates.values())

    def _available(self, candidate: BackendCandidate, *, include_capacity: bool = True) -> bool:
        circuit_ready = not candidate.circuit_open or (
            time.monotonic() >= candidate.retry_at and not candidate.probing
        )
        return (
            candidate.healthy
            and circuit_ready
            and (not include_capacity or candidate.active < candidate.capacity)
        )

    def select(
        self,
        *,
        task: Task,
        require_streaming: bool = False,
        model: str | None = None,
        exclude: frozenset[str] = frozenset(),
    ) -> RouteDecision:
        eligible = [
            candidate
            for candidate in self._candidates.values()
            if task in candidate.tasks
            and self._available(candidate)
            and candidate.name not in exclude
            and (model is None or model == candidate.model or model in candidate.public_models)
            and (not require_streaming or candidate.streaming)
        ]
        if not eligible:
            raise NoEligibleBackend(f"no healthy backend supports task={task}")
        score, selected = min(
            ((self._score(candidate), candidate) for candidate in eligible),
            key=lambda pair: (pair[0], pair[1].name),
        )
        return RouteDecision(
            selected.name,
            selected.model,
            round(score, 6),
            (
                "capability_match",
                "healthy",
                "half_open_probe" if selected.circuit_open else "circuit_closed",
                "lowest_weighted_score",
            ),
            self.policy_version,
        )

    def _score(self, candidate: BackendCandidate) -> float:
        return (
            0.35 * (candidate.predicted_latency_ms / 1000)
            + 0.25 * candidate.queue_utilization
            + 0.15 * candidate.estimated_cost
            + 0.15 * candidate.quality_penalty
            + 0.10 * candidate.recent_error_rate
        )

    def started(self, name: str) -> None:
        candidate = self._candidates[name]
        candidate.active += 1
        candidate.queue_utilization = candidate.active / candidate.capacity
        if candidate.circuit_open:
            candidate.probing = True

    def finished(self, name: str, *, elapsed: float, outcome: str, was_probe: bool = False) -> None:
        candidate = self._candidates[name]
        candidate.active -= 1
        candidate.queue_utilization = candidate.active / candidate.capacity
        if was_probe:
            candidate.probing = False
        if outcome == "success":
            candidate.predicted_latency_ms = (
                0.8 * candidate.predicted_latency_ms + 0.2 * elapsed * 1000
            )
            candidate.recent_error_rate *= 0.8
            if not candidate.circuit_open or was_probe:
                candidate.failures = 0
                candidate.circuit_open = False
        elif outcome == "error":
            candidate.recent_error_rate = 0.8 * candidate.recent_error_rate + 0.2
            candidate.failures += 1
            if candidate.failures >= self.failure_threshold or candidate.circuit_open:
                candidate.circuit_open = True
                candidate.retry_at = time.monotonic() + self.cooldown_seconds

    def is_ready(self) -> bool:
        return any(
            self._available(candidate, include_capacity=False)
            for candidate in self._candidates.values()
        )
