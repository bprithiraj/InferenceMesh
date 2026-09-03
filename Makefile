.PHONY: install dev check test run smoke

install:
	python -m pip install -e ".[dev]"

dev:
	uvicorn inferencemesh.main:app --reload --host 127.0.0.1 --port 8000

check:
	ruff check .
	ruff format --check .
	mypy src
	pytest

test:
	pytest

run:
	uvicorn inferencemesh.main:app --host 0.0.0.0 --port 8000

smoke:
	python scripts/smoke_test.py
