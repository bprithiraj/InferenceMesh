# Changelog

## 0.2.0 — local real-serving milestone

- Added configurable OpenAI-compatible HTTP adapters and model/capability aliases.
- Preserved stream finish reasons and optional token usage; cleaned up upstream
  connections and admission on disconnect.
- Fixed cross-tenant admission starvation by reserving global/tenant capacity atomically.
- Added measured routing load/latency, circuit recovery and bounded pre-output failover.
- Protected full metrics using a separate key; added conservative per-process
  request/output budgets and fail-closed external demo configuration.
- Added direct-versus-gateway benchmark JSON/CSV reporting and local CPU setup docs.
- Expanded tests for concurrency, cancellation, truncated streams, circuit recovery,
  model mapping, budgets and endpoint access.

This is a single-process serving milestone. Native Triton, distributed caches/quotas,
model rollout control and GPU performance evidence remain outside this release.
A Git tag or running deployment is a separate action.

## 0.1.0 — gateway foundation

Deterministic chat/embedding adapter, OpenAI-shaped API, bounded admission, static
eligibility/weighted routing, optional auth, deployment definitions and contributor docs.
Unknown/task-incompatible model IDs return 404.

## Verification policy

Run Ruff lint/format, strict mypy and pytest before committing a release.
Container definitions require an actual container build/run before claiming runtime
verification. Performance claims must link to actual raw artifacts and environment
metadata; a mock or CPU probe is not a GPU benchmark.
