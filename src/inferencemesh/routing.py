"""Explainable, deterministic inference routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from inferencemesh.domain import Task


class NoEligibleBackend(RuntimeError):
    """Raised when hard eligibility filters remove every backend."""


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


@dataclass(frozen=True, slots=True)
class RouteDecision:
    backend: str
    model: str
    score: float
    reason_codes: tuple[str, ...]
    policy_version: str


class Router:
    """Apply hard safety filters before scoring eligible candidates."""

    def __init__(
        self,
        candidates: list[BackendCandidate],
        *,
        policy_version: str = "local-v1",
    ) -> None:
        self._candidates = {candidate.name: candidate for candidate in candidates}
        self.policy_version = policy_version

    @property
    def candidates(self) -> tuple[BackendCandidate, ...]:
        return tuple(self._candidates.values())

    def select(self, *, task: Task, require_streaming: bool = False) -> RouteDecision:
        eligible = [
            candidate
            for candidate in self._candidates.values()
            if task in candidate.tasks
            and candidate.healthy
            and not candidate.circuit_open
            and (not require_streaming or candidate.streaming)
        ]
        if not eligible:
            raise NoEligibleBackend(f"no healthy backend supports task={task}")

        scored = sorted(
            ((self._score(candidate), candidate) for candidate in eligible),
            key=lambda pair: (pair[0], pair[1].name),
        )
        score, selected = scored[0]
        reasons = (
            "capability_match",
            "healthy",
            "circuit_closed",
            "lowest_weighted_score",
        )
        return RouteDecision(
            backend=selected.name,
            model=selected.model,
            score=round(score, 6),
            reason_codes=reasons,
            policy_version=self.policy_version,
        )

    def _score(self, candidate: BackendCandidate) -> float:
        return (
            0.35 * (candidate.predicted_latency_ms / 1_000)
            + 0.25 * candidate.queue_utilization
            + 0.15 * candidate.estimated_cost
            + 0.15 * candidate.quality_penalty
            + 0.10 * candidate.recent_error_rate
        )

    def is_ready(self) -> bool:
        return any(
            candidate.healthy and not candidate.circuit_open
            for candidate in self._candidates.values()
        )
