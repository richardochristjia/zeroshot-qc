"""Env-gated fake adapters (M7): USE_FAKE_ADAPTERS for container probes.

Monkeypatching cannot reach a running container, so the inspect router
reads ``settings.use_fake_adapters`` (env ``USE_FAKE_ADAPTERS``) instead.
Default (unset/false) must preserve the real construction path.

Run: cd backend && .venv/bin/python -m pytest tests/test_fake_flag.py -q
"""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.pipeline.inspect as inspect_mod
import app.routers.inspect as inspect_router
import app.routers.profiles as profiles_router
from app.adapters.fakes import FakeJudge, FakeSegmenter
from app.config import settings
from app.main import app

client = TestClient(app)
REAL_PROFILES = Path(__file__).resolve().parent.parent / "profiles"


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ref = data_dir / "mvtec" / "screw" / "train" / "good" / "000.png"
    ref.parent.mkdir(parents=True)  # committed profile points here
    Image.new("RGB", (8, 8)).save(ref)
    monkeypatch.setattr(settings, "data_dir", str(data_dir))
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "screw.json").write_text(
        (REAL_PROFILES / "screw.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(inspect_mod, "PROFILES_DIR", prof_dir)
    monkeypatch.setattr(profiles_router, "PROFILES_DIR", prof_dir)
    return {"data": data_dir, "profiles": prof_dir}


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color=(150, 150, 150)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_flag_off_default_is_real_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default/unset flag preserves the real adapter path."""
    monkeypatch.setattr(settings, "use_fake_adapters", False)
    cache_dir = tmp_path / "cache"
    from app.pipeline.cache import DiskCache

    segmenter = inspect_router._get_segmenter(DiskCache(cache_dir))
    judge = inspect_router._get_judge(DiskCache(cache_dir))
    assert not isinstance(segmenter._inner, FakeSegmenter)
    assert not isinstance(judge._inner, FakeJudge)
    assert segmenter._model_id != "fake-sam"
    assert judge._model_id != "fake-judge"


def test_env_var_binds_to_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """USE_FAKE_ADAPTERS env var drives Settings (the container probe path)."""
    from app.config import Settings

    monkeypatch.delenv("USE_FAKE_ADAPTERS", raising=False)
    assert Settings().use_fake_adapters is False
    monkeypatch.setenv("USE_FAKE_ADAPTERS", "true")
    assert Settings().use_fake_adapters is True
    monkeypatch.setenv("USE_FAKE_ADAPTERS", "false")
    assert Settings().use_fake_adapters is False


def test_flag_on_serves_fake_inspect(
    monkeypatch: pytest.MonkeyPatch, isolated: dict
) -> None:
    """Flag on: POST /api/inspect serves deterministic fake verdicts."""
    monkeypatch.setattr(settings, "use_fake_adapters", True)
    resp = client.post(
        "/api/inspect",
        files={"image": ("part.png", _png_bytes(), "image/png")},
        data={"profile_id": "screw"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"]["verdict"] in ("PASS", "FAIL")
    assert body["verdict"]["summary"].startswith("Fake judge:")
    overlay = client.get(body["overlay_url"])
    assert overlay.status_code == 200
