import asyncio

import pytest

from inferencemesh.admission import AdmissionController, AdmissionRejected


def controller(queue_wait: float = 0.1) -> AdmissionController:
    return AdmissionController(
        max_concurrent=2,
        max_concurrent_per_tenant=1,
        max_queue_depth=8,
        queue_wait_seconds=queue_wait,
    )


async def test_saturated_tenant_does_not_reserve_another_tenants_slot() -> None:
    pool = controller()
    first = await pool.acquire("a")
    queued = asyncio.create_task(pool.acquire("a"))
    await asyncio.sleep(0)
    other = await asyncio.wait_for(pool.acquire("b"), timeout=0.05)
    assert (await pool.snapshot()).active == 2
    assert not queued.done()
    await first.release()
    second = await queued
    await asyncio.gather(second.release(), other.release())
    assert (await pool.snapshot()).active == 0


async def test_cancelled_and_timed_out_waiters_do_not_leak_capacity() -> None:
    pool = controller(queue_wait=0.03)
    first = await pool.acquire("a")
    waiting = asyncio.create_task(pool.acquire("a"))
    await asyncio.sleep(0)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    with pytest.raises(AdmissionRejected, match="timed out"):
        await pool.acquire("a")
    assert (await pool.snapshot()).waiting == 0
    await first.release()
    fresh = await pool.acquire("a")
    await asyncio.gather(*(fresh.release() for _ in range(10)))
    assert (await pool.snapshot()).active == 0
    assert not pool._tenants


async def test_fifo_for_eligible_tenants_and_zero_queue_capacity() -> None:
    pool = AdmissionController(
        max_concurrent=1,
        max_concurrent_per_tenant=1,
        max_queue_depth=0,
        queue_wait_seconds=0.1,
    )
    first = await pool.acquire("a")
    with pytest.raises(AdmissionRejected, match="full"):
        await pool.acquire("b")
    await first.release()
    second = await pool.acquire("b")
    await second.release()
