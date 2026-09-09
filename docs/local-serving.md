# Run real inference locally

v0.2 accepts OpenAI-compatible chat/embedding engines through a configurable HTTP
adapter. The development machine needs only a local CPU model for the Ollama path.
No paid API key, cloud account or GPU provisioning is required.

## Install the gateway

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Ollama on a CPU

Install Ollama using its official installer, start its local server, then download a
small model deliberately. Model files use disk space and RAM. For example:

```powershell
ollama pull qwen2.5:0.5b
ollama show qwen2.5:0.5b
$env:INFERENCEMESH_BACKEND_MODE = 'http'
$env:INFERENCEMESH_BACKENDS = '[{"name":"ollama","public_model":"local-chat","upstream_model":"qwen2.5:0.5b","base_url":"http://127.0.0.1:11434/v1","tasks":["chat"],"capacity":2,"timeout_seconds":180}]'
$env:INFERENCEMESH_MAX_OUTPUT_TOKENS = '128'
$env:INFERENCEMESH_MAX_CONCURRENT_REQUESTS = '2'
$env:INFERENCEMESH_MAX_CONCURRENT_PER_TENANT = '2'
uvicorn inferencemesh.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. The public model name is `local-chat`.
The adapter forwards `qwen2.5:0.5b` to Ollama. Readiness checks the upstream model
listing, so an unloaded/unavailable model alias does not silently become a fake model.

```powershell
$body = '{"model":"local-chat","messages":[{"role":"user","content":"Explain bounded queues in one sentence."}],"max_tokens":32,"stream":true,"stream_options":{"include_usage":true}}'
curl.exe -N http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" --data-raw $body
```

Ollama's API compatibility is partial; this gateway supports a deliberately bounded
chat subset. It does not implement tools, vision, multimodal input or the Responses API.

## vLLM on existing GPU hardware

Run a model you are authorized to use in your own vLLM installation and expose its
OpenAI-compatible server locally. Configure `base_url` to that server's `/v1`,
`upstream_model` to its served model ID, and a stable `public_model` alias.
The same adapter is used; no separate engine is bundled or silently downloaded.

```json
[{"name":"vllm-local","public_model":"local-chat","upstream_model":"your-served-model","base_url":"http://127.0.0.1:8001/v1","tasks":["chat"],"capacity":4}]
```

This configuration example is not evidence that GPU execution was tested.

## Embeddings and redundant routes

A separate HTTP backend may declare `tasks:["embedding"]` for its embedding model.
Only declare capabilities the selected model actually serves. Each backend name must
be unique. To test failover, configure two independently served compatible backends
with the same public model alias. Do not duplicate one server URL and call it redundancy.

The gateway periodically probes model availability on the request/readiness path.
It tracks recent latency/error rate and active capacity. Repeated errors open a
circuit. After the cooldown one serving request probes recovery. An alternate backend
is attempted at most once per request, only before unary success or streamed output.
After streaming begins, a failure emits a sanitized SSE error without a false
`[DONE]`; it never splices text from another model.

## Access and budgets

Local development defaults to explicit `INFERENCEMESH_BACKEND_MODE=demo` when no
real profile is set. That deterministic backend is for tests and API demonstrations.
Bind development to loopback.

For any externally accessible deployment set:

- `INFERENCEMESH_ENVIRONMENT=public-demo`
- `INFERENCEMESH_REQUIRE_API_KEY=true`
- `INFERENCEMESH_API_KEY` to a unique secret, supplied outside source control
- `INFERENCEMESH_METRICS_API_KEY` to a different secret if metrics are needed

Without a metrics key, `/metrics` returns 404. With one, its bearer key is required.
The sanitized `/demo/metrics/summary` remains anonymous and does not expose prompts.

Requests and requested maximum output tokens are conservatively reserved in a
60-second window. Failed or cancelled requests are not refunded. Budgets and
admission state are in memory, per process, and reset on restart. Run one gateway
worker for this demo. Distributed quotas, independent customer API keys and durable
accounting remain future work; this is not a production billing boundary.

## References

- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/)
- [HTTPX asynchronous streaming and cleanup](https://www.python-httpx.org/async/)
