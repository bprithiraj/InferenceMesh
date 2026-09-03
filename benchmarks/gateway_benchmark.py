"""Small reproducible gateway load probe; not a model-performance benchmark."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def run_request(client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> tuple[float, int]:
    async with semaphore:
        started = time.perf_counter()
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "inferencemesh-local",
                "messages": [{"role": "user", "content": "Benchmark bounded routing."}],
                "temperature": 0,
                "max_tokens": 64,
            },
        )
        return time.perf_counter() - started, response.status_code


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * quantile))
    return ordered[index]


async def main(requests: int, concurrency: int, base_url: str) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        started = time.perf_counter()
        results = await asyncio.gather(*(run_request(client, semaphore) for _ in range(requests)))
        elapsed = time.perf_counter() - started

    latencies = [latency for latency, _status in results]
    successful = sum(status == 200 for _latency, status in results)
    print(f"requests={requests} concurrency={concurrency} success={successful}")
    print(f"elapsed_s={elapsed:.4f} requests_per_second={requests / elapsed:.2f}")
    print(
        "latency_ms "
        f"mean={statistics.mean(latencies) * 1000:.2f} "
        f"p50={percentile(latencies, 0.50) * 1000:.2f} "
        f"p95={percentile(latencies, 0.95) * 1000:.2f} "
        f"p99={percentile(latencies, 0.99) * 1000:.2f}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.requests, arguments.concurrency, arguments.base_url))
