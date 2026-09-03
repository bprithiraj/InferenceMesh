# Contributing to InferenceMesh

Thanks for improving InferenceMesh. It is a deliberately scoped personal
project, so small, well-tested changes that strengthen the gateway contract,
operational safety, or reproducibility are especially useful.

## Local setup

InferenceMesh requires Python 3.12 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Run the full local gate before opening a pull request:

```powershell
ruff check .
ruff format --check .
mypy src
pytest
```

## Change expectations

- Keep public API behavior explicit and add a contract test for any change.
- Preserve bounded-resource behavior; avoid unbounded queues, retries, or
  logging of prompt content.
- Keep backend-specific shapes behind the adapter protocol.
- Do not present simulated, deterministic, or CPU-only results as GPU-serving
  performance evidence.
- Update the README, API reference, and changelog when user-visible behavior
  changes.

## Reporting security issues

Do not include credentials, private prompts, customer data, or vulnerability
details in a public issue. Follow the repository's [security policy](SECURITY.md).
