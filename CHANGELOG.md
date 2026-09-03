# Changelog

All notable changes to InferenceMesh are documented here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) while it is in its
pre-1.0 development phase.

## [0.1.0] - Unreleased

### Added

- OpenAI-compatible chat completions, SSE streaming, embeddings, and model
  discovery backed by a deterministic local adapter.
- Explainable eligibility-first routing, bounded global and per-tenant
  admission, optional API-key authentication, health endpoints, and Prometheus
  metrics.
- Docker, Compose, Kubernetes, Render, CI, gRPC-contract, benchmark-method,
  and local smoke-test assets.

### Fixed

- Reject unknown and task-incompatible public model IDs rather than silently
  routing them to the deterministic backend.

### Verification

- A tagged release requires Ruff, strict mypy, pytest, packaging/container
  checks, and local unary/streaming smoke-test evidence. It is not a GPU
  benchmark or a publicly exposed model-serving deployment.

## Release policy

Tags are created only after the complete verification suite passes. Each
release note must distinguish implemented behavior from roadmap work and link
to any benchmark environment and raw artifacts used for performance claims.
