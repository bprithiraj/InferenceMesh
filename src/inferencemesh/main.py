"""ASGI entry point."""

import os

import uvicorn

from inferencemesh.api import create_app

app = create_app()


def run() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("inferencemesh.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
