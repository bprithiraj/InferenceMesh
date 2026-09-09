# Reproducible streaming comparison

The runner saves raw request rows in CSV and a JSON report containing source SHA,
dirty-worktree status, Python/platform information, model revision, workload,
success/error/rejection counts, successful latency p50/p95/p99, TTFT and throughput.
It never describes the deterministic demo as an LLM performance result.

Start the real gateway using [local serving](../docs/local-serving.md), then run:

```powershell
python benchmarks/gateway_benchmark.py --direct-url http://127.0.0.1:11434/v1 --gateway-url http://127.0.0.1:8000/v1 --model local-chat --direct-model qwen2.5:0.5b --requests 10 --concurrency 1 --max-tokens 32 --hardware "CPU; replace with actual processor and RAM" --model-revision "replace with ollama show/tags digest" --output benchmarks/results/local-cpu
```

For authenticated servers use environment variables
`INFERENCEMESH_BENCHMARK_GATEWAY_KEY` and
`INFERENCEMESH_BENCHMARK_DIRECT_KEY`; keys are never written into artifacts.
Keep URLs free of credentials and query parameters. Use synthetic prompts only.

Runs execute direct first, gateway second, with warmup for each. They use one prompt,
a closed-loop workload, and the same requested output limit. This is a comparison
probe, not a complete serving benchmark. Model loading, CPU power/temperature,
other machine activity, prefix caches and sampling can affect results.
p99 from ten samples is not a useful tail-latency claim.

Raise request/token budgets explicitly for intentional local load tests; warmups
consume those budgets. Separate overload runs from latency runs. The report includes
rejections rather than silently dropping them. Missing token usage remains missing,
never estimated from words.

For publishable GPU results additionally pin container digests, tokenizer/model
revisions, quantization, server arguments, context-length and output distributions,
arrival patterns, warmup, test duration and repeated trials. A CPU Ollama run validates
the OpenAI-compatible path; it does not validate vLLM GPU throughput or Triton.
