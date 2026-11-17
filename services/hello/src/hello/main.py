"""Hello-world service: the factory's test subject."""

import os

from fastapi import FastAPI

DEFAULT_VERSION = "dev"

app = FastAPI(title="hello")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Report liveness and the deployed version."""
    return {"status": "ok", "version": os.environ.get("VERSION", DEFAULT_VERSION)}


@app.get("/")
def root() -> dict[str, str]:
    """Return the greeting."""
    return {"message": "hello"}
