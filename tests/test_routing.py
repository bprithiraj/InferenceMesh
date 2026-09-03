import pytest

from inferencemesh.domain import Task
from inferencemesh.routing import BackendCandidate, NoEligibleBackend, Router


def candidate(name: str, *, latency: float, healthy: bool = True) -> BackendCandidate:
    return BackendCandidate(
        name=name,
        model=f"{name}-model",
        tasks=frozenset({Task.CHAT}),
        streaming=True,
        healthy=healthy,
        predicted_latency_ms=latency,
    )


def test_router_selects_lowest_score_deterministically() -> None:
    router = Router([candidate("slow", latency=300), candidate("fast", latency=20)])

    decision = router.select(task=Task.CHAT, require_streaming=True)

    assert decision.backend == "fast"
    assert decision.reason_codes[-1] == "lowest_weighted_score"


def test_router_applies_health_as_hard_filter() -> None:
    router = Router(
        [candidate("unhealthy", latency=1, healthy=False), candidate("healthy", latency=50)]
    )

    assert router.select(task=Task.CHAT).backend == "healthy"


def test_router_fails_when_no_backend_is_eligible() -> None:
    router = Router([candidate("down", latency=1, healthy=False)])

    with pytest.raises(NoEligibleBackend):
        router.select(task=Task.CHAT)
