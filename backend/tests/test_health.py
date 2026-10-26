"""Health endpoint tests: shape, model IDs, and no secret leakage.

Run: cd backend && .venv/bin/python -m pytest tests/test_health.py
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch: pytest.MonkeyPatch):
    # Ensure each test starts from a known empty baseline; individual
    # tests override via monkeypatch again where needed.
    for field in ("sam_model_id", "judge_model_id", "image_model_id"):
        monkeypatch.setattr(settings, field, "")
    yield


def test_health_empty_settings() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "models": {"sam": "", "judge": "", "image": ""},
    }


def test_health_configured_model_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sam_model_id", "sam-test-id")
    monkeypatch.setattr(settings, "judge_model_id", "judge-test-id")
    monkeypatch.setattr(settings, "image_model_id", "image-test-id")
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "status": "ok",
        "models": {
            "sam": "sam-test-id",
            "judge": "judge-test-id",
            "image": "image-test-id",
        },
    }
    # exact shape, no extra keys
    assert set(body.keys()) == {"status", "models"}
    assert set(body["models"].keys()) == {"sam", "judge", "image"}


def test_health_never_leaks_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel_key = "SENTINEL-API-KEY-HEALTH-0123456789"
    sentinel_url = "https://sentinel-base-url.example.com"
    monkeypatch.setattr(settings, "meta_api_key", sentinel_key)
    monkeypatch.setattr(settings, "meta_api_base_url", sentinel_url)
    monkeypatch.setattr(settings, "sam_model_id", "sam-x")
    resp = client.get("/api/health")
    assert resp.status_code == 200
    text = resp.text
    assert sentinel_key not in text
    assert sentinel_url not in text
    body = resp.json()
    # No secret-like field names anywhere in the payload.
    flattened = json.dumps(body).lower()
    assert "api_key" not in flattened
    assert "base_url" not in flattened
    assert "meta_api_key" not in flattened
