# InferenceMesh Development Plan

**Source requirements:** [Current portfolio case study](src/content/projects/inference-mesh.mdx) and [approved architecture](InferenceMesh-architecture.md)

**Planning date:** 2026-07-23

---

## Goals

- Publish a separate, public InferenceMesh repository with reproducible local CPU and GPU profiles, automated verification, deployment manifests, and architecture decisions.
- Serve OpenAI-compatible unary and streaming chat completions through a FastAPI gateway backed by a real vLLM deployment.
- Serve embeddings or reranking through Triton gRPC and normalize both serving engines behind tested backend contracts.
- Expose a versioned gRPC inference API that shares authentication, routing, admission, and telemetry behavior with REST.
- Protect every online route with request validation, token limits, per-tenant quotas, bounded concurrency, bounded queueing, deadlines, cancellation, and circuit breaking.
- Route requests using hard capability and policy filters followed by explainable latency, queue, cost, quality, and error scoring.
- Implement exact caching and then a tenant-, model-, locale-, safety-, and policy-scoped semantic cache with a measured false-hit release gate.
- Use MLflow model aliases and evaluation evidence to execute shadow, canary, promotion, and rollback flows without redeploying the gateway.
- Process idempotent asynchronous batch jobs through Kafka with bounded retries, cancellation, object-storage results, and a dead-letter path.
- Deploy the system on Kubernetes with private data/model services, GPU scheduling, Helm configuration, observability, security controls, and cost limits.
- Publish direct-backend and gateway benchmarks covering latency, time to first token, inter-token latency, throughput, queue behavior, cache behavior, and failure recovery.
- Give recruiters a safe public demo, sanitized metrics, benchmark report, repository, video, and case study directly from the existing portfolio.

## Non-Goals

- Train or fine-tune models as part of the first public release.
- Accept arbitrary user model artifacts, plugins, or executable code.
- Implement every OpenAI endpoint or optional parameter.
- Transparently switch models after a response has begun streaming.
- Build a Kubernetes operator, custom GPU scheduler, or multi-region active-active platform.
- Implement a learned routing policy before the explainable rule-based router has a reproducible benchmark baseline.
- Add Ray Serve until a distinct multi-stage workload demonstrates that it provides value beyond the vLLM and Triton responsibilities.
- Expose MLflow, Grafana administration, Prometheus queries, Kafka, Redis, PostgreSQL, or model-server endpoints to public users.
- Publish performance claims without model, hardware, configuration, workload, raw-result, and Git-revision evidence.

## Plan

### Wave 0 - Resolve public-release prerequisites

**Requirement:** Establish the repository, model, deployment, cost, benchmark, and security constraints that later implementation depends on.

**Dependencies:** Approved InferenceMesh architecture.

**External prerequisites:** Public GitHub account or organization, candidate cloud accounts, GPU quota information, and model license terms.

**Actions**

- Create the separate public repository with Python packaging, license, code of conduct, security policy, issue templates, and branch protection.
- Record ADR-001 through ADR-010 from the architecture before introducing framework-specific code.
- Evaluate small text-generation candidates against public-hosting license, vLLM compatibility, GPU memory, tokenizer availability, tool/streaming needs, and expected recruiter-demo quality.
- Evaluate an embedding or reranking model against Triton backend compatibility, license, artifact size, and CPU/GPU requirements.
- Compare candidate deployment providers using GPU availability, Kubernetes support, scale-down behavior, cold-start duration, egress, managed dependencies, monthly minimum, and enforceable budget limits.
- Define the maximum monthly demo budget, alert threshold, GPU maximum, automatic shutdown, and manual emergency-stop procedure.
- Define the reference hardware and versioned workload distributions used for every published performance comparison.
- Produce a threat model covering public guest tokens, quota bypass, prompt retention, cache isolation, model abuse, supply chain, administrative access, and untrusted pull requests.
- Decide which batch operations remain authenticated-only and which sanitized live metrics are public.

**Measurable exit criteria**

- The repository is public and contains the ten approved ADRs with no unresolved contradiction between them.
- Selected model revisions and their license evidence are recorded; no implementation pulls an unreviewed floating model revision.
- The deployment decision includes a documented monthly-cost ceiling, GPU hard maximum, cold-start observation, and shutdown procedure.
- The benchmark specification fixes hardware, model revision, input/output token distributions, arrival patterns, warm-up, run duration, and raw-result format.
- The threat model identifies a control and verification activity for every high-risk public entry point.

### Wave 1 - Establish contracts and an executable local foundation

**Requirement:** Create a testable application skeleton and stable domain contracts before backend integration.

**Dependencies:** Wave 0 repository, model, and interface decisions.

**External prerequisites:** Supported Python and container runtimes.

**Actions**

- Create the planned `apps`, shared `src/inferencemesh`, `api`, `deploy`, `benchmarks`, `tests`, and `docs` layout without duplicating domain logic between entry points.
- Configure locked Python dependencies, formatting, linting, static typing, unit tests, coverage reporting, pre-commit checks, and deterministic test settings.
- Define domain contracts for logical models, model capabilities, normalized inference requests, streaming chunks, usage, route decisions, backend health, errors, and cancellation.
- Implement the supported OpenAI chat-completion and embedding request/response schemas with explicit unsupported-field behavior.
- Define versioned protobuf contracts for unary generation, server-streaming generation, embeddings, and health.
- Implement request IDs, trace-context propagation, structured error mapping, redaction primitives, and configuration validation.
- Create REST/SSE and gRPC application entry points with liveness, readiness, and dependency-injection boundaries.
- Create Docker Compose dependencies for PostgreSQL, Redis, Kafka-compatible broker, MLflow, object storage, OpenTelemetry collector, Prometheus, and Grafana.
- Add database migration tooling and initial schemas for tenants, key hashes, quotas, route-policy snapshots, rollout audit, batch jobs, usage aggregates, and an outbox.
- Add CI for format, lint, type, unit, contract, migration, secret, dependency, and CPU container checks.

**Measurable exit criteria**

- A clean checkout passes all CI checks and starts the CPU dependency profile with one documented command.
- REST and gRPC health endpoints pass integration tests.
- Generated OpenAPI and protobuf artifacts are reproducible and fail CI on an unreviewed compatibility change.
- Logs and test traces prove that authorization values and sample prompt bodies are redacted.
- Database migrations apply to an empty database and upgrade from the previous migration in CI.

### Wave 2 - Deliver the vLLM online inference path

**Requirement:** Provide compatible, bounded, observable unary and streaming text inference against vLLM.

**Dependencies:** Wave 1 contracts, transport entry points, telemetry primitives, and selected text model.

**External prerequisites:** GPU runtime for real-model verification; a contract-test stub remains available to CPU CI.

**Actions**

- Implement the backend adapter interface and a deterministic fake adapter for unit, fault, and CPU integration tests.
- Implement the vLLM adapter for model listing, unary generation, SSE streaming, deadlines, cancellation, usage normalization, health, and error classification.
- Implement request-size, input-token, output-token, model-capability, and deadline validation before backend admission.
- Implement bounded per-tenant concurrency, bounded per-backend concurrency, bounded queue wait, and explicit overload responses.
- Propagate client disconnects and cancellation to vLLM and release permits in every success, failure, timeout, and cancellation path.
- Implement pre-stream retry rules and prohibit backend switching after the first emitted token.
- Add OpenTelemetry spans and Prometheus metrics for validation, admission, queueing, backend connection, first token, token streaming, completion, cancellation, and errors.
- Add OpenAI SDK, curl, and direct HTTP contract tests for unary and streaming behavior.
- Measure the first direct-vLLM versus gateway baseline on the reference workload without caching or routing.

**Measurable exit criteria**

- A standard OpenAI client completes both unary and streaming requests through the gateway.
- Contract tests cover success, validation error, timeout, disconnect, cancellation, backend failure before streaming, and backend failure after streaming.
- Concurrent overload never exceeds configured queue or active-request bounds and returns the documented retryable error.
- Backend work stops within 2 seconds of tested client cancellation.
- The baseline report records raw direct and gateway results with Git SHA, images, hardware, model/tokenizer revisions, and all workload parameters.

### Wave 3 - Add Triton, routing, health, and fallback

**Requirement:** Route across distinct serving responsibilities using explainable policy and observable failure handling.

**Dependencies:** Wave 2 stable online path and selected Triton model.

**External prerequisites:** Triton-compatible model artifact and local or cloud model repository.

**Actions**

- Create a version-pinned Triton model repository for embeddings or reranking with readiness, batching, and metrics configuration.
- Implement the Triton gRPC adapter with health, deadlines, normalized outputs, error classification, and metrics correlation.
- Implement logical-model configuration and hard filters for tenant permission, task capability, context, feature support, token budget, rollout allocation, health, circuit state, and capacity.
- Implement bounded rolling signals and the explainable latency, queue, cost, quality, and error score with deterministic tie-breaking.
- Record the policy version, eligible candidates, selected candidate, and compact reason codes for every decision without storing prompt content.
- Implement closed, open, and half-open circuit-breaker states with isolated probe capacity and state-change audit events.
- Implement fallback only before response streaming and only when an eligible route and remaining deadline exist.
- Expose the shared router through both REST and gRPC transports.
- Add unit, property, integration, and fault tests for filtering, scoring, stable canary hashing, stale signals, circuit transitions, and fallback.

**Measurable exit criteria**

- Text and embedding requests reach vLLM and Triton respectively through their normalized adapters.
- For a fixed routing snapshot and signal set, tests produce deterministic selected targets and reason codes.
- Injected backend latency or qualifying failures open the circuit and remove the target from new selection; controlled half-open probes close it after recovery.
- No test switches a backend after the first streamed token.
- The routing decision is visible in traces and authenticated diagnostics without leaking private tenant or policy data to guest clients.

### Wave 4 - Add tenant security, quotas, and guarded caching

**Requirement:** Safely reduce repeat latency and cost without breaking tenant, model, or response correctness.

**Dependencies:** Wave 3 logical models, immutable model identity, routing policy versions, and Triton embeddings.

**External prerequisites:** Redis with required vector-search support for the semantic-cache stage.

**Actions**

- Implement salted API-key hashes, one-time key display, scoped tenant permissions, key revocation, and audit events.
- Implement short-lived guest-session tokens restricted by origin, endpoint, logical model, request rate, concurrency, and input/output tokens.
- Implement atomic distributed request and token quotas with documented behavior when Redis is unavailable.
- Implement exact-cache keys containing tenant namespace, immutable model version, messages, tools, relevant sampling parameters, locale, safety, and policy version.
- Implement cache bypass for unsupported or unsafe request classes, including tool calls, sensitive flags, explicit opt-out, and configured non-deterministic sampling.
- Build a labeled semantic-cache dataset containing paraphrases and hard negatives.
- Implement Triton embeddings and Redis vector lookup with hard tenant, locale, model-version, safety, and policy filters.
- Tune the similarity threshold against false-hit rate and record cache hit, miss, bypass, latency, and evaluated correctness metrics.
- Restrict the public demo cache to an approved synthetic corpus and make tenant semantic caching opt-in with TTL.
- Add concurrency, expiry, eviction, invalidation, Redis-outage, and cross-tenant isolation tests.

**Measurable exit criteria**

- Revoked keys and expired guest tokens fail immediately at the gateway.
- Concurrent quota tests cannot exceed configured request, concurrency, or token budgets beyond documented atomic-counter tolerance.
- Automated tests observe zero cross-tenant, cross-version, cross-locale, and incompatible-policy cache hits.
- Redis failure bypasses caching and rejects guest traffic when its distributed quota cannot be proven.
- The semantic threshold meets the documented false-hit release limit on the versioned labeled dataset before semantic caching is enabled.

### Wave 5 - Implement MLflow-driven evaluation and safe rollout

**Requirement:** Promote and roll back model versions from recorded evidence without coupling online requests to MLflow availability.

**Dependencies:** Wave 3 routing snapshots and Wave 4 cache version isolation.

**External prerequisites:** Database-backed MLflow registry and object storage.

**Actions**

- Integrate immutable MLflow model versions, tags, evaluation-run links, and `candidate` / `champion` aliases.
- Implement the rollout controller that validates registry state and writes immutable, versioned route snapshots to PostgreSQL.
- Implement gateway snapshot loading, validation, atomic replacement, version metrics, and last-known-valid fallback.
- Implement offline evaluation for task quality, safety cases, compatibility, latency, throughput, and resource signals.
- Implement shadow request sampling that never changes the client response and cannot consume unbounded backend capacity.
- Implement stable 1%, 5%, 25%, and 50% canary allocations with minimum sample and observation requirements.
- Implement evaluation gates comparing candidate and champion for quality, errors, timeouts, TTFT, end-to-end latency, throughput, queue pressure, and cache isolation.
- Implement promotion, automatic rollback, manual pause, immutable audit evidence, and idempotent state transitions.
- Create a compressed synthetic-load demo that produces enough controlled observations to show a failed canary and rollback safely.
- Add failure tests for unavailable MLflow, stale/invalid snapshots, duplicate events, controller restart, evaluation-worker failure, and partial rollout transitions.

**Measurable exit criteria**

- An MLflow candidate can pass offline evaluation, receive shadow traffic, enter canary, fail a configured gate, and return traffic to champion without a gateway deployment.
- Rollout allocation tests remain within 2 percentage points of configured allocation over the defined deterministic sample size.
- A confirmed gate violation restores the champion route within 60 seconds in the demonstration profile.
- Gateway service continues from the last valid snapshot during an MLflow outage while all rollout transitions pause.
- Every transition records actor, previous/new version, reason, evidence URI, policy version, and timestamp.

### Wave 6 - Deliver asynchronous Kafka batch inference

**Requirement:** Process durable, idempotent, tenant-isolated batch work without affecting the online latency path.

**Dependencies:** Wave 3 adapters and routing, Wave 4 authentication and quotas, Wave 5 immutable model versions.

**External prerequisites:** Kafka-compatible broker and S3-compatible object storage.

**Actions**

- Define versioned batch command, progress, terminal, and dead-letter event schemas.
- Implement bounded JSONL input validation, tenant ownership, model eligibility, object-storage references, and idempotent batch creation.
- Use a transactional outbox so a committed job is not lost between PostgreSQL and Kafka publication.
- Implement worker claims, heartbeats, bounded chunks, adapter calls, progress, result/error files, and terminal state updates.
- Implement bounded exponential retries, error classification, dead-letter publication, replay controls, and duplicate-event handling.
- Implement cooperative cancellation between chunks and make terminal states immutable.
- Isolate batch concurrency and capacity from online admission; expose consumer lag, oldest-job age, retries, throughput, and dead-letter metrics.
- Add integration tests for broker outage, worker crash, redelivery, duplicate create, malformed input, partial success, cancellation, and tenant isolation.

**Measurable exit criteria**

- Repeating a create request with the same tenant and idempotency key returns one logical job.
- A worker restart and message redelivery do not duplicate terminal outputs or corrupt job state.
- Broker unavailability does not degrade online inference; pending outbox work publishes after recovery.
- Exhausted retryable failures appear once in the dead-letter path with sufficient safe diagnostic context.
- An authenticated tenant can create, inspect, cancel, and retrieve only its own batch job and result.

### Wave 7 - Package observability and Kubernetes deployment

**Requirement:** Operate the complete system as a secure, cost-bounded, production-shaped deployment.

**Dependencies:** Waves 2 through 6 functional services, data ownership, metrics, and failure behavior.

**External prerequisites:** Selected Kubernetes/GPU provider, DNS or provider URL, TLS, container registry, secret store, and budget controls.

**Actions**

- Complete OpenTelemetry instrumentation and collector pipelines for traces, metrics, and redacted structured logs.
- Create Grafana dashboards and alerts for API health, TTFT, token throughput, queueing, backend circuits, GPU/Triton/vLLM metrics, cache behavior, rollout state, and Kafka lag.
- Create a Helm chart with local, benchmark, staging, and public values; pin images and declare CPU, memory, GPU, storage, and security settings.
- Configure readiness/liveness probes, startup behavior, resource limits, disruption budgets, topology, ingress, TLS, service accounts, and network policies.
- Configure NVIDIA drivers/device plugin through the selected provider and request GPUs as Kubernetes extended resources.
- Keep model servers, stores, MLflow, raw metrics, and administrative routes private.
- Configure secrets outside Git, image signing/provenance, SBOM generation, vulnerability scanning, and protected production workflows.
- Configure the GPU node hard maximum, scale-down or schedule, budget alerts, and verified emergency shutdown.
- Implement release deployment, smoke tests, public health verification, Helm rollback, backup/restore checks for durable state, and an operations runbook.

**Measurable exit criteria**

- A clean cluster deployment reaches ready state from the documented Helm procedure and serves a real restricted request over HTTPS.
- Network tests prove public clients cannot reach model servers, databases, broker, registry, raw metrics, or administration endpoints.
- Dashboards correlate a sample request across gateway, route, backend, and token timing without prompt content or credentials.
- A failed release rolls back to the previous tested Helm revision and passes the public smoke request.
- The configured GPU maximum, budget alert, scheduled/automatic scale-down, and emergency stop are each tested and documented.
- Backup restoration recreates required durable configuration in an isolated verification environment.

### Wave 8 - Validate performance, resilience, and security

**Requirement:** Replace architectural claims with reproducible evidence under load and controlled failure.

**Dependencies:** Wave 7 production-shaped deployment and all functional capabilities.

**External prerequisites:** Reserved reference-hardware test window and approved synthetic workloads.

**Actions**

- Automate environment capture, warm-up, workload execution, raw-result storage, statistical summaries, and report generation.
- Run direct-vLLM and gateway comparisons on identical model, hardware, request distributions, and concurrency.
- Run saturation tests to identify capacity, queue growth, rejection onset, TTFT, inter-token latency, throughput, and resource limits.
- Measure exact-cache and semantic-cache latency, hit behavior, threshold precision/recall, and false-hit rate.
- Inject backend latency, transport failure, readiness failure, client cancellation, Redis outage, MLflow outage, Kafka backlog, worker crash, and invalid route snapshots.
- Run candidate quality and latency regressions through shadow, canary, automatic rollback, and audit verification.
- Run authentication, quota, cross-tenant, CORS, input-limit, secret-leak, dependency, container, and public-endpoint abuse tests.
- Publish machine-readable raw results plus a concise report that separates targets, observations, limitations, and conclusions.

**Measurable exit criteria**

- Every required architecture experiment has a repeatable command, raw output, environment manifest, and generated report tied to a Git SHA.
- Gateway overhead, cancellation, success-rate, queue, canary-allocation, rollback, tenant-isolation, and public-demo acceptance thresholds pass or the release remains blocked with documented evidence.
- Failure tests match the degradation matrix and show no unbounded queue, retry storm, cross-tenant access, or hidden backend switch.
- Published charts can be regenerated from committed analysis code and released result artifacts.
- Resume-ready metrics cite a tagged release and report; any failing or hardware-dependent target is described accurately rather than omitted.

### Wave 9 - Publish the recruiter experience and portfolio case study

**Requirement:** Make the working system discoverable, understandable, safe to try, and credible from the existing portfolio.

**Dependencies:** Wave 8 passing release evidence and stable public deployment.

**External prerequisites:** Public deployment URL, GitHub release URL, approved portfolio domain configuration, and recorded demo assets.

**Actions**

- Build the demo UI around a five-minute guided flow: service status, guest session, streaming request, route/cache metadata, safe metrics, and isolated canary rollback scenario.
- Expose only allowlisted aggregated metrics through `/demo/metrics/summary`; keep Grafana and Prometheus private.
- Record a two-minute architecture and failure-recovery video that remains useful when the GPU is cold or the public budget is exhausted.
- Write the public README with live links, screenshot, problem, architecture, measured results, quickstart, API examples, deployment, limitations, and roadmap above or near the first screen.
- Publish Python, curl, and gRPC examples that use the restricted public contract or local profile.
- Add repository badges for release, CI, image, license, and live status without presenting a synthetic check as production availability.
- Update the portfolio project renderer to display the existing `demoUrl` field alongside `repositoryUrl`.
- Update the InferenceMesh front matter with repository and demo URLs and keep `status: in-progress` until all public-release acceptance criteria pass.
- Replace the generic case study with the real problem, architecture, routing and rollout decisions, benchmark methodology, measured outcomes, failure analysis, trade-offs, video, and limitations.
- Test the portfolio, repository, demo, API, report, and video links from an anonymous browser and mobile viewport.
- Tag the public release and only then change the portfolio status to `case-study` and copy measured outcomes into the resume.

**Measurable exit criteria**

- An anonymous recruiter can move from portfolio to live demo, source, benchmark report, and video without credentials or broken links.
- The guest flow enforces endpoint, model, request, concurrency, prompt-token, and output-token limits under concurrent testing.
- The portfolio renders both repository and demo links from validated front matter and passes its production build.
- The case study and README contain only measurements reproducible from the tagged release artifacts.
- The project status changes to `case-study` only after the anonymous-access, security, benchmark, rollback, and deployment checks pass.

## Verification Plan

| Verification activity | Pass condition |
| --- | --- |
| Python quality pipeline | Formatting, linting, static typing, unit tests, coverage threshold, and dependency checks pass on a clean checkout |
| API compatibility | Standard OpenAI client, curl, and generated gRPC clients pass supported unary, streaming, embeddings, error, and cancellation contracts |
| Migration verification | Empty install and sequential upgrade apply successfully in CI with no schema drift |
| Resource-bound test | Active work and queue depth never exceed configuration; overload returns documented retryable errors |
| Streaming cancellation | Backend generation and admission permit end within 2 seconds of the tested disconnect |
| Routing determinism | Fixed policy and signals produce the expected target, allocation, and reason codes across repeated runs |
| Circuit and fallback test | Qualifying failure opens the circuit; fallback occurs only before first token and respects the remaining deadline |
| Tenant-isolation suite | No key, quota, cache, batch, usage, trace, or result crosses tenant boundaries |
| Semantic-cache evaluation | False-hit rate remains below the recorded release threshold on the versioned hard-negative dataset |
| Rollout exercise | Candidate moves through evaluation and canary, fails a gate, and restores champion within 60 seconds with complete audit evidence |
| Batch resilience | Redelivery, crash, retry, cancellation, and broker recovery preserve idempotent job and output state |
| Dependency degradation | Redis, PostgreSQL, MLflow, Kafka, backend, and telemetry failures match the documented degradation matrix |
| Kubernetes security | Anonymous network probes cannot reach private model, data, registry, raw metrics, or administration services |
| Benchmark reproducibility | A clean runner regenerates charts and summaries from released raw results and environment metadata |
| Public abuse test | Guest sessions cannot exceed endpoint, model, rate, concurrency, input-token, or output-token limits |
| Anonymous recruiter walkthrough | Portfolio, repository, demo, status, benchmark, video, and sample request work without private credentials |
| Portfolio production build | Astro validation and production build pass with repository and demo links rendered |

## Risks and Controls

| Risk | Control |
| --- | --- |
| The project becomes a shallow collection of technologies | Give each component one distinct responsibility, defer Ray Serve, and block new integrations without a benchmarked use case and ADR |
| Public GPU cost exceeds the personal-project budget | Hard-cap GPU nodes, restrict tokens and concurrency, schedule or scale down, alert before the monthly ceiling, and maintain a tested emergency stop |
| Cold GPU start makes the live demo appear broken | Show explicit warming status, retain an always-available architecture/metrics page, and provide a short recorded live recovery demonstration |
| Public endpoint is abused | Short-lived guest tokens, coarse edge limits, strict application quotas, small output caps, allowed-model list, concurrency bounds, and revocation switch |
| Semantic cache returns an incorrect or cross-tenant answer | Exact cache first, hard metadata filters in the vector query, opt-in tenant namespaces, TTL, hard-negative evaluation, and a release threshold on false hits |
| Routing hides model changes from clients | Stable logical models, model-version headers, route audit, deterministic canary assignment, and no backend switch after streaming begins |
| MLflow or control-plane failure interrupts serving | Validated PostgreSQL snapshots, atomic in-memory replacement, last-known-valid fallback, and paused rollout mutations |
| Kafka failure affects online latency | Keep Kafka entirely off the online path and use a transactional outbox for batch publication |
| Benchmark numbers are misleading | Pin model and images, disclose hardware/workload/configuration, publish raw results, compare identical runs, and label targets separately from observations |
| Model license does not permit public hosting | Wave 0 license review on immutable model revisions and a deployment stop condition for missing evidence |
| Sensitive prompts or credentials enter telemetry | Default content-free telemetry, centralized redaction, safe attribute allowlist, leak tests, and no public raw observability consoles |
| Kubernetes complexity delays a working demo | Complete contracts and local profiles first, use Helm only after end-to-end behavior is stable, and avoid a custom operator |
| Public dashboard exposes infrastructure labels or controls | Serve a sanitized aggregation endpoint and keep Grafana, Prometheus, and admin routes private |
| Resume claims drift from the released system | Link every metric to a tagged report and update resume/portfolio only after the corresponding acceptance test passes |
| Existing portfolio changes are overwritten | Preserve the current dirty worktree, limit later edits to the InferenceMesh entry and demo-link renderer, and review the diff before build or commit |

## Stop Conditions

- Stop public model deployment if license evidence does not explicitly support the selected use.
- Stop cloud rollout if a GPU hard maximum, budget alert, and emergency shutdown cannot be enforced and tested.
- Stop semantic-cache enablement if the labeled evaluation misses the approved false-hit threshold or any isolation test fails.
- Stop canary progression when quality, safety, error, timeout, TTFT, throughput, queue, or resource gates fail or lack their minimum sample count.
- Stop automatic route-snapshot activation when schema, signature, model identity, capability, or policy validation fails; retain the last valid snapshot.
- Stop public launch if guest quota, token, CORS, network-isolation, secret-leak, or abuse tests fail.
- Stop benchmark publication if raw results, environment metadata, model revision, workload definition, or Git SHA are missing.
- Stop changing the portfolio status to `case-study` if the live demo, anonymous walkthrough, tagged release, benchmark report, rollback demonstration, or production build is incomplete.
- Stop resume metric publication if the value cannot be reproduced from a tagged public artifact.

## Recommended Next Steps

1. Create the separate `inference-mesh` GitHub repository and add the proposed repository skeleton without application features.
2. Complete ADR-001 through ADR-010, select the two public model revisions, and record their license evidence.
3. Establish the reference workload and compare GPU deployment options against the monthly budget and cold-start requirements.
4. Implement Wave 1 contracts, local dependencies, migrations, entry points, and CI before integrating vLLM.
5. Keep the existing portfolio entry marked `in-progress` during implementation and publish repository/demo links only when their anonymous paths are safe and working.
