# Validation: InferenceMesh v0.2

Verified on 10 September 2026 in a Windows workspace.

- 36 automated tests passed, including tenant fairness, bounded queues, HTTP/SSE contracts, upstream failure recovery, circuit probe concurrency, readiness under saturation, malformed responses, auth/budgets and actual ASGI client-disconnect cleanup.
- Strict mypy passed on 15 source files; Ruff lint and formatting passed; the final fresh-environment check covered 43 files.
- A separate fresh workspace virtual environment also passed all 36 tests, strict mypy, Ruff and pip consistency checks. Its tested versions are captured in requirements-lock.txt; the measured run retains its original dependency snapshot beside the raw results.
- Actual local model: Ollama 0.33.3, Qwen2.5 0.5B Q4_K_M, CPU execution, cloud disabled.
- Real unary chat returned content, `finish_reason=length`, and usage of 37 input / 16 output tokens.
- Real streaming integration: 10/10 direct requests and 10/10 gateway requests succeeded, with usage present for every request and zero HTTP errors or rejections.

The [raw JSON report](benchmarks/results/local-cpu/report.json) and [per-request CSV](benchmarks/results/local-cpu/requests.csv) record code commit `2bfb55a293035ef4855c2e01136f7aaaa026f2d6`, a clean working tree, the source fingerprint, model digest, workload and actual timing samples.

## Measurement limits

This was a functional CPU integration probe on a shared Intel i7-1370P Windows development machine with 31.4 GiB RAM and substantial concurrent memory/build activity. It used one prompt, 10 measured requests per path, concurrency 1 and 32 output tokens, after a warmup. Direct and gateway runs were sequential. It does not isolate gateway overhead or establish production p95/p99 latency, throughput capacity, or GPU performance. The gateway run was slower in this sample; inspect the raw measurements rather than treating them as a performance claim.

The automated failure tests use controlled HTTP transports where needed. A live vLLM GPU deployment, native Triton adapter, distributed quotas and cloud deployment are outside this verified release. The repository contains explicit setup instructions and a measurement runner for further controlled experiments.
