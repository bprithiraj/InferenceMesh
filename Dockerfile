FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system inferencemesh \
    && useradd --system --gid inferencemesh --home-dir /app inferencemesh

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

USER inferencemesh
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]

CMD ["python", "-m", "inferencemesh.main"]
