# Getting started

## Requirements

- Python 3.12+
- Git
- Docker is optional for the container workflow

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Start

```powershell
uvicorn inferencemesh.main:app --reload --host 127.0.0.1 --port 8000
```

The default deterministic backend is local and does not download a model.

## Configuration

Copy `.env.example` to `.env`. Every setting uses the `INFERENCEMESH_` prefix.

| Setting | Default | Purpose |
| --- | ---: | --- |
| `REQUIRE_API_KEY` | `false` | Require bearer or `x-api-key` authentication |
| `API_KEY` | `local-dev-key` | Local key when authentication is enabled |
| `MAX_CONCURRENT_REQUESTS` | `32` | Global active inference bound |
| `MAX_CONCURRENT_PER_TENANT` | `4` | Active bound for one tenant |
| `MAX_QUEUE_DEPTH` | `64` | Maximum number of requests allowed to wait |
| `QUEUE_WAIT_MS` | `250` | Maximum admission wait before `429` |
| `MAX_INPUT_CHARS` | `20000` | Aggregate input-character limit |
| `MAX_OUTPUT_TOKENS` | `512` | Maximum requested output-token limit |
| `FAKE_TOKEN_DELAY_MS` | `5` | Local streaming delay used for demonstrations |

The single configured API key is an initial deployment feature, not the final tenant-key store. The production milestone replaces it with salted key hashes and explicit tenant records.

## Authentication

When enabled, either header is accepted:

```text
Authorization: Bearer local-dev-key
x-api-key: local-dev-key
```

Never commit a real key. Supply it through the deployment secret store.

## Test

```powershell
ruff check .
ruff format --check .
mypy src
pytest
```
