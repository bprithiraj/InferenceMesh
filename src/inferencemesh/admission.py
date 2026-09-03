"""Bounded admission control for protecting backend capacity."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


class AdmissionRejected(RuntimeError):
    """Raised when a request cannot enter the bounded execution pool."""


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    active: int
    waiting: int
    max_active: int
    max_waiting: int


class AdmissionLease:
    """A capacity reservation that is safe to release exactly once."""

    def __init__(self, controller: AdmissionController, tenant: asyncio.Semaphore) -> None:
        self._controller = controller
        self._tenant = tenant
        self._released = False

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._tenant.release()
        self._controller._global.release()
        await self._controller._leave_active()


class AdmissionController:
    """Bound active and waiting work globally and per tenant."""

    def __init__(
        self,
        *,
        max_concurrent: int,
        max_concurrent_per_tenant: int,
        max_queue_depth: int,
        queue_wait_seconds: float,
    ) -> None:
        self._global = asyncio.Semaphore(max_concurrent)
        self._tenant_limit = max_concurrent_per_tenant
        self._tenants: defaultdict[str, asyncio.Semaphore] = defaultdict(self._new_tenant_semaphore)
        self._max_concurrent = max_concurrent
        self._max_queue_depth = max_queue_depth
        self._queue_wait_seconds = queue_wait_seconds
        self._state_lock = asyncio.Lock()
        self._active = 0
        self._waiting = 0

    def _new_tenant_semaphore(self) -> asyncio.Semaphore:
        return asyncio.Semaphore(self._tenant_limit)

    async def snapshot(self) -> AdmissionSnapshot:
        async with self._state_lock:
            return AdmissionSnapshot(
                active=self._active,
                waiting=self._waiting,
                max_active=self._max_concurrent,
                max_waiting=self._max_queue_depth,
            )

    async def _enter_queue(self) -> None:
        async with self._state_lock:
            if self._waiting >= self._max_queue_depth:
                raise AdmissionRejected("inference queue is full")
            self._waiting += 1

    async def _leave_queue(self, *, admitted: bool) -> None:
        async with self._state_lock:
            self._waiting -= 1
            if admitted:
                self._active += 1

    async def _leave_active(self) -> None:
        async with self._state_lock:
            self._active -= 1

    async def acquire(self, tenant_id: str) -> AdmissionLease:
        """Acquire capacity before transport response headers are sent."""

        await self._enter_queue()
        global_acquired = False
        tenant_acquired = False
        admitted = False
        tenant = self._tenants[tenant_id]

        try:
            async with asyncio.timeout(self._queue_wait_seconds):
                await self._global.acquire()
                global_acquired = True
                await tenant.acquire()
                tenant_acquired = True
            admitted = True
            return AdmissionLease(self, tenant)
        except TimeoutError as exc:
            raise AdmissionRejected("inference capacity wait timed out") from exc
        finally:
            await self._leave_queue(admitted=admitted)
            if not admitted:
                if tenant_acquired:
                    tenant.release()
                if global_acquired:
                    self._global.release()

    @asynccontextmanager
    async def admit(self, tenant_id: str) -> AsyncIterator[None]:
        """Reserve bounded global and tenant capacity for one request."""
        lease = await self.acquire(tenant_id)
        try:
            yield
        finally:
            await lease.release()
