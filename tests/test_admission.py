import asyncio

import pytest

from inferencemesh.admission import AdmissionController, AdmissionRejected


@pytest.mark.asyncio
async def test_admission_bounds_active_and_waiting_requests() -> None:
    controller = AdmissionController(
        max_concurrent=1,
        max_concurrent_per_tenant=1,
        max_queue_depth=1,
        queue_wait_seconds=0.2,
    )
    first = await controller.acquire("tenant-a")
    waiting = asyncio.create_task(controller.acquire("tenant-b"))
    await asyncio.sleep(0.01)

    with pytest.raises(AdmissionRejected, match="queue is full"):
        await controller.acquire("tenant-c")

    snapshot = await controller.snapshot()
    assert snapshot.active == 1
    assert snapshot.waiting == 1

    await first.release()
    second = await waiting
    await second.release()

    final = await controller.snapshot()
    assert final.active == 0
    assert final.waiting == 0


@pytest.mark.asyncio
async def test_admission_lease_release_is_idempotent() -> None:
    controller = AdmissionController(
        max_concurrent=1,
        max_concurrent_per_tenant=1,
        max_queue_depth=1,
        queue_wait_seconds=0.1,
    )
    lease = await controller.acquire("tenant")

    await lease.release()
    await lease.release()

    assert (await controller.snapshot()).active == 0
