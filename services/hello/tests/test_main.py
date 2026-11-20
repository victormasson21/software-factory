import pytest
from fastapi.testclient import TestClient

from hello.main import app

client = TestClient(app)


def test_healthz_returns_ok_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERSION", "abc123")

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "abc123"}


def test_healthz_defaults_version_to_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERSION", raising=False)

    response = client.get("/healthz")

    assert response.json() == {"status": "ok", "version": "dev"}
