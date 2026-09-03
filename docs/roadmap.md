# Roadmap

## v0.1 - Gateway foundation

- [x] OpenAI-compatible unary chat and SSE streaming
- [x] Embeddings contract
- [x] Deterministic backend adapter
- [x] Bounded global, tenant, and queue admission
- [x] Explainable eligibility and weighted routing
- [x] API-key mode, limits, request IDs, and metrics
- [x] Tests, containers, CI, Kubernetes manifests, and gRPC contract

## v0.2 - Real serving engines

- [ ] vLLM adapter with cancellation, health, usage, and metrics
- [ ] Triton gRPC adapter for embeddings or reranking
- [ ] Backend circuit breaker and half-open probes
- [ ] Direct-backend versus gateway benchmark harness
- [ ] GPU Compose profile and pinned public model revisions

## v0.3 - Multi-tenant caching

- [ ] Salted tenant API-key store and atomic Redis quotas
- [ ] Exact cache with tenant/model/policy isolation
- [ ] Triton-generated embeddings and Redis semantic cache
- [ ] Hard-negative cache evaluation and false-hit gate

## v0.4 - Safe model rollout

- [ ] Database-backed MLflow registry
- [ ] Immutable gateway route snapshots
- [ ] Champion/candidate aliases
- [ ] Shadow evaluation and deterministic canaries
- [ ] Automated rollback and audit evidence

## v0.5 - Batch and operations

- [ ] Kafka batch jobs, transactional outbox, and dead-letter path
- [ ] OpenTelemetry traces and production dashboards
- [ ] Helm deployment for CPU and GPU node pools
- [ ] Failure injection and reproducible benchmark release

## v1.0 - Public recruiter demonstration

- [ ] Restricted guest-session flow
- [ ] Live streaming and route explanation
- [ ] Safe canary-failure and rollback scenario
- [ ] Published benchmark report and raw artifacts
- [ ] Portfolio links, architecture video, and anonymous access verification

Ray Serve remains deferred until a measured multi-stage model pipeline requires Python-native composition or independent stage autoscaling.
