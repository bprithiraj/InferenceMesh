# API behavior

v0.2 implements a deliberate subset of the OpenAI Chat Completions and Embeddings
contracts. Unsupported request fields fail validation.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | /health/live | Process liveness and version |
| GET | /health/ready | At least one healthy eligible route; capacity saturation is not failure |
| GET | /v1/models | Configured logical model IDs |
| POST | /v1/chat/completions | Unary or SSE chat |
| POST | /v1/embeddings | Embeddings through a configured capability |
| GET | /metrics | Separate metrics key required; disabled if no key configured |
| GET | /demo/metrics/summary | Anonymous sanitized capacity summary |

Chat fields: `model`, `messages`, `stream`, `temperature`, `max_tokens`,
and `stream_options.include_usage`. Message roles: system, user, assistant.

The demo IDs are `inferencemesh-local` for chat and
`inferencemesh-embedding-local` for embeddings. HTTP mode advertises only configured
public aliases. Unknown or incompatible model IDs return 404.

Successful streams emit OpenAI-shaped chunks with stable completion IDs, the public
model alias, upstream text/finish reason, optional usage and a final `data: [DONE]`.
Without `include_usage`, usage fields are omitted while content and finish choices
remain. A post-output upstream failure emits a sanitized SSE error and no `[DONE]`.
An already-started stream is never retried on another backend.

Unary responses preserve upstream prompt/completion usage and finish reason.
Deterministic mode uses documented word-count-based synthetic usage; real mode
does not estimate token counts from words.

## Errors and access

- 422: schema validation failed.
- 400: configured input/output size limit exceeded.
- 401: invalid model API key or metrics key.
- 404: unsupported model/capability, or disabled metrics endpoint.
- 429 with Retry-After: bounded admission rejected or request/token budget exhausted.
- 503: no healthy, nonfailed, unsaturated route remains before response output.

API keys use Bearer authorization or X-API-Key. The metrics key is independent.
Upstream error bodies, credentials and prompt content are not returned in errors.
The anonymous status endpoint contains only counts/status/policy version.

The 60-second budgets reserve requested max_tokens rather than actual generated
tokens. Reservations are not refunded after errors/cancellation. All gateway state
is process-local; see [local serving limits](local-serving.md).
