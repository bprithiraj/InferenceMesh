"""Direct-backend versus gateway streaming probe with inspectable raw artifacts."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * quantile))]


def safe_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("benchmark URLs must not contain credentials, query strings or fragments")
    return urlunsplit(parsed)


async def run_request(
    client: httpx.AsyncClient,
    model: str,
    max_tokens: int,
    prompt: str,
    index: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "index": index,
        "status": None,
        "success": False,
        "error": None,
        "ttft_ms": None,
        "latency_ms": None,
        "completion_tokens": None,
        "prompt_tokens": None,
        "finish_reason": None,
    }
    try:
        async with client.stream(
            "POST",
            "chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "stream_options": {"include_usage": True},
                "temperature": 0,
                "max_tokens": max_tokens,
            },
        ) as response:
            result["status"] = response.status_code
            if response.status_code != 200:
                result["error"] = f"http_{response.status_code}"
                return result
            result["backend"] = response.headers.get("x-inferencemesh-backend")
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    result["success"] = result["finish_reason"] is not None
                    break
                chunk = json.loads(payload)
                if "error" in chunk:
                    result["error"] = "stream_error"
                    break
                for choice in chunk.get("choices", []):
                    if choice.get("delta", {}).get("content") and result["ttft_ms"] is None:
                        result["ttft_ms"] = (time.perf_counter() - started) * 1000
                    if choice.get("finish_reason"):
                        result["finish_reason"] = choice["finish_reason"]
                if chunk.get("usage"):
                    result["completion_tokens"] = chunk["usage"].get("completion_tokens")
                    result["prompt_tokens"] = chunk["usage"].get("prompt_tokens")
            if not result["success"] and result["error"] is None:
                result["error"] = "incomplete_stream"
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        result["error"] = type(exc).__name__
    finally:
        result["latency_ms"] = (time.perf_counter() - started) * 1000
    return result


def summarize(results: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    successful = [item for item in results if item["success"]]
    latencies = [float(item["latency_ms"]) for item in successful]
    ttft = [float(item["ttft_ms"]) for item in successful if item["ttft_ms"] is not None]
    token_count = sum(item["completion_tokens"] or 0 for item in successful)
    return {
        "requests": len(results),
        "successes": len(successful),
        "rejections_429": sum(item["status"] == 429 for item in results),
        "unavailable_503": sum(item["status"] == 503 for item in results),
        "errors": sum(not item["success"] for item in results),
        "elapsed_seconds": elapsed,
        "successful_requests_per_second": len(successful) / elapsed,
        "observed_completion_tokens_per_second": token_count / elapsed,
        "requests_missing_usage": sum(item["completion_tokens"] is None for item in successful),
        "latency_ms": {
            "mean": statistics.mean(latencies) if latencies else None,
            "p50": percentile(latencies, 0.5),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
        "ttft_ms": {
            "p50": percentile(ttft, 0.5),
            "p95": percentile(ttft, 0.95),
            "p99": percentile(ttft, 0.99),
        },
    }


async def run_target(
    name: str,
    url: str,
    model: str,
    arguments: argparse.Namespace,
) -> dict[str, Any]:
    key = os.environ.get(f"INFERENCEMESH_BENCHMARK_{name.upper()}_KEY", "")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with httpx.AsyncClient(
        base_url=safe_url(url).rstrip("/") + "/",
        timeout=arguments.timeout_seconds,
        headers=headers,
        limits=httpx.Limits(max_connections=arguments.concurrency),
    ) as client:
        for index in range(arguments.warmup):
            warmup = await run_request(
                client, model, arguments.max_tokens, arguments.prompt, -index - 1
            )
            if not warmup["success"]:
                raise RuntimeError(f"{name} warmup failed: {warmup['error']}")
        semaphore = asyncio.Semaphore(arguments.concurrency)

        async def bounded(index: int) -> dict[str, Any]:
            async with semaphore:
                return await run_request(
                    client, model, arguments.max_tokens, arguments.prompt, index
                )

        started = time.perf_counter()
        results = await asyncio.gather(*(bounded(index) for index in range(arguments.requests)))
        elapsed = time.perf_counter() - started
    return {
        "target": name,
        "base_url": safe_url(url),
        "model": model,
        "summary": summarize(results, elapsed),
        "requests": results,
    }


def git_output(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def source_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in [*sorted((root / "src").rglob("*.py")), root / "pyproject.toml"]:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode())
    return digest.hexdigest()


async def main(arguments: argparse.Namespace) -> None:
    targets = []
    if arguments.direct_url:
        targets.append(("direct", arguments.direct_url, arguments.direct_model or arguments.model))
    targets.append(("gateway", arguments.gateway_url, arguments.model))
    runs = [await run_target(name, url, model, arguments) for name, url, model in targets]
    git_status = git_output("status", "--porcelain")
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "git_sha": git_output("rev-parse", "HEAD"),
        "working_tree_dirty": None if git_status is None else bool(git_status),
        "source_sha256": source_digest(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
            "httpx": importlib.metadata.version("httpx"),
        },
        "hardware_notes": arguments.hardware,
        "model_revision": arguments.model_revision,
        "workload": {
            "prompt": arguments.prompt,
            "requests": arguments.requests,
            "concurrency": arguments.concurrency,
            "max_tokens": arguments.max_tokens,
            "warmup": arguments.warmup,
            "arrival_pattern": "closed-loop fixed concurrency",
            "target_order": [name for name, _, _ in targets],
        },
        "limitations": [
            "Single synthetic prompt; consult hardware notes for CPU/GPU context.",
            "Latency quantiles cover successes; errors and rejections have separate counts.",
            "TTFT includes gateway queueing; role-only events do not count as tokens.",
            "Output-token budgets reserve max_tokens; warmups also consume gateway budgets.",
            "Inspect hardware, model revision and raw samples before drawing conclusions.",
        ],
        "runs": runs,
    }
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    rows = [{"target": run["target"], **row} for run in runs for row in run["requests"]]
    fields = sorted(set().union(*(row.keys() for row in rows)))
    with (arguments.output / "requests.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({run["target"]: run["summary"] for run in runs}, indent=2))
    print(f"Artifacts: {arguments.output.resolve()}")


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--direct-url")
    parser.add_argument("--model", default="inferencemesh-local")
    parser.add_argument("--direct-model")
    parser.add_argument("--requests", type=positive_int, default=20)
    parser.add_argument("--concurrency", type=positive_int, default=2)
    parser.add_argument("--max-tokens", type=positive_int, default=32)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument(
        "--prompt", default="Explain why a server queue should have a finite size in one sentence."
    )
    parser.add_argument("--hardware", default="not supplied")
    parser.add_argument("--model-revision", default="not supplied")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results/local"))
    options = parser.parse_args()
    if options.warmup < 0 or options.timeout_seconds <= 0:
        parser.error("warmup must be nonnegative and timeout must be positive")
    asyncio.run(main(options))
