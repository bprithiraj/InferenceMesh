# Roadmap and scope

## v0.1 — completed gateway foundation

OpenAI-shaped unary/SSE and embeddings contracts, deterministic adapter,
bounded admission, weighted routing, API-key mode, health/metrics, tests and
deployment definitions.

## v0.2 — implemented real HTTP serving milestone

- [x] Configurable model/capability registry and OpenAI-compatible HTTP adapter.
- [x] Local Ollama and vLLM configuration examples.
- [x] Stream usage/finish preservation and upstream cleanup on disconnect.
- [x] Fair atomic global/tenant admission with cancellation/timeout regression tests.
- [x] Measured load/latency, health probes and recoverable circuit breakers.
- [x] Bounded failover before output; no midstream switching.
- [x] Protected full metrics and per-process request/output budgets.
- [x] Direct-versus-gateway benchmark tool with raw CSV/JSON artifacts.
- [ ] Native vLLM GPU execution and reproducible GPU benchmark evidence.
- [ ] Native Triton gRPC embeddings/reranking adapter.

## Later milestones, intentionally not required for the local v0.2 project

- Distributed tenant authentication and atomic shared quotas.
- Exact/semantic caches with tenant/model/policy isolation and false-hit evaluation.
- Durable route snapshots, model registry integration, shadow/canary rollout and rollback.
- Batch jobs, outbox/dead-letter flows and production telemetry.
- Authenticated guest-session UI and independently verified public deployment.

These are future work, not shipped features. Add infrastructure only when a measured
workload needs it. Ray Serve remains deferred unless independent pipeline-stage
composition or scaling becomes necessary.
