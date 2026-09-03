# Benchmarks

`gateway_benchmark.py` is the initial contract-load runner. It reports latency and success under a fixed concurrency level. It is not yet a GPU benchmark.

Published GPU results must additionally capture Git SHA, image digests, model/tokenizer revisions, quantization, hardware, serving arguments, request-token distributions, arrival pattern, warm-up, duration, raw results, and a direct-backend control run.

```powershell
python benchmarks\gateway_benchmark.py --requests 100 --concurrency 10
```
