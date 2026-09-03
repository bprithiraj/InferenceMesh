# API behavior

InferenceMesh v0.1 implements a deliberate subset of the OpenAI Chat Completions and Embeddings contracts. Unsupported fields fail validation instead of being silently ignored.

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/health/live` | Process liveness and version |
| `GET` | `/health/ready` | Serving-route readiness |
| `GET` | `/v1/models` | Available logical model identifiers |
| `POST` | `/v1/chat/completions` | Unary or SSE chat completion |
| `POST` | `/v1/embeddings` | Deterministic local embeddings |
| `GET` | `/metrics` | Prometheus scrape endpoint |
| `GET` | `/demo/metrics/summary` | Low-cardinality public-safe status |

## Chat fields

Supported request fields are `model`, `messages`, `stream`, `temperature`, and `max_tokens`. Message roles are `system`, `user`, and `assistant`.

Streaming responses use `text/event-stream`, emit OpenAI-shaped `chat.completion.chunk` objects, and terminate with `data: [DONE]`.

## Error behavior

- Schema errors return `422`.
- Configured input or output limit violations return `400`.
- Missing or invalid credentials return `401`.
- Full or timed-out admission returns `429` with `Retry-After`.
- No eligible backend returns `503`.

## Compatibility policy

Generated OpenAPI is treated as a public artifact. Breaking a supported request or response field requires a versioned decision and release note. Future backend adapters cannot leak vLLM- or Triton-specific response shapes through these endpoints.
