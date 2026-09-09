"""Atomic, bounded admission with FIFO fairness among eligible tenants."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


class AdmissionRejected(RuntimeError):
    """The bounded queue is full or its wait deadline expired."""


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    active: int
    waiting: int
    max_active: int
    max_waiting: int


class AdmissionLease:
    def __init__(self, controller: AdmissionController, tenant: str) -> None:
        self._controller = controller
        self._tenant = tenant
        self._released = False

    async def release(self) -> None:
        await asyncio.shield(self._release())

    async def _release(self) -> None:
        async with self._controller._condition:
            if self._released:
                return
            self._released = True
            self._controller._active -= 1
            self._controller._tenants[self._tenant] -= 1
            if not self._controller._tenants[self._tenant]:
                del self._controller._tenants[self._tenant]
            self._controller._condition.notify_all()


class AdmissionController:
    """Reserve global and tenant capacity together, never while waiting."""

    def __init__(
        self,
        *,
        max_concurrent: int,
        max_concurrent_per_tenant: int,
        max_queue_depth: int,
        queue_wait_seconds: float,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._tenant_limit = max_concurrent_per_tenant
        self._max_queue_depth = max_queue_depth
        self._queue_wait_seconds = queue_wait_seconds
        self._condition = asyncio.Condition()
        self._active = 0
        self._tenants: defaultdict[str, int] = defaultdict(int)
        self._queue: list[tuple[object, str]] = []

    async def snapshot(self) -> AdmissionSnapshot:
        async with self._condition:
            return AdmissionSnapshot(
                self._active, len(self._queue), self._max_concurrent, self._max_queue_depth
            )

    def _eligible(self, tenant: str) -> bool:
        return (
            self._active < self._max_concurrent
            and self._tenants.get(tenant, 0) < self._tenant_limit
        )

    def _first_eligible(self) -> object | None:
        return next((ticket for ticket, tenant in self._queue if self._eligible(tenant)), None)

    async def acquire(self, tenant_id: str) -> AdmissionLease:
        ticket = object()
        async with self._condition:
            if self._eligible(tenant_id) and self._first_eligible() is None:
                self._active += 1
                self._tenants[tenant_id] += 1
                return AdmissionLease(self, tenant_id)
            if len(self._queue) >= self._max_queue_depth:
                raise AdmissionRejected("inference queue is full")
            self._queue.append((ticket, tenant_id))
            try:
                async with asyncio.timeout(self._queue_wait_seconds):
                    await self._condition.wait_for(lambda: self._first_eligible() is ticket)
                self._active += 1
                self._tenants[tenant_id] += 1
                return AdmissionLease(self, tenant_id)
            except TimeoutError as exc:
                raise AdmissionRejected("inference capacity wait timed out") from exc
            finally:
                self._queue.remove((ticket, tenant_id))
                self._condition.notify_all()

    @asynccontextmanager
    async def admit(self, tenant_id: str) -> AsyncIterator[None]:
        lease = await self.acquire(tenant_id)
        try:
            yield
        finally:
            await lease.release()
