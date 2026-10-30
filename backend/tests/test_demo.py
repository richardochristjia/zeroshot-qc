"""Demo bundle: seeding, keyless replay, fallback, samples route, drift guard.

Run: cd backend && .venv/bin/python -m pytest tests/test_demo.py -q
Everything runs against tmp_path; the repo's data/ is never touched.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.demo import DEMO_DIR, seed_demo
from app.main import app

client = TestClient(app)  # no `with`: startup hooks never seed the repo
MANIFEST = DEMO_DIR / "samples.json"
needs_bundle = pytest.mark.skipif(
    not MANIFEST.is_file(), reason="backend/demo not built (run scripts/build_demo.py)"
)


@pytest.fixture()
def keyless(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(settings, "data_dir", str(data))
    monkeypatch.setattr(settings, "meta_api_key", "")
    # Cache keys include the model ids the bundle was built with.
    monkeypatch.setattr(settings, "sam_model_id", "sam-3.1")
    monkeypatch.setattr(settings, "judge_model_id", "muse-spark-1.3")
    monkeypatch.setattr(settings, "use_fake_adapters", False)
    return data


def _inspect(sample_png: Path, profile_id: str, rules: str | None = None):
    data = {"profile_id": profile_id}
    if rules:
        data["rules"] = rules
    return client.post(
        "/api/inspect",
        files={"image": ("x.png", sample_png.read_bytes(), "image/png")},
        data=data,
    )


def test_seed_into_empty_dir(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "a").mkdir(parents=True)
    (src / "a" / "f.txt").write_bytes(b"one")
    (src / "g.txt").write_bytes(b"two")
    dst = tmp_path / "dst"
    assert seed_demo(src, dst) == 2
    assert (dst / "a" / "f.txt").read_bytes() == b"one"
    assert (dst / "g.txt").read_bytes() == b"two"


def test_seed_never_overwrites(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "f.txt").write_bytes(b"bundle")
    (dst / "f.txt").write_bytes(b"mine")
    assert seed_demo(src, dst) == 0
    assert (dst / "f.txt").read_bytes() == b"mine"


def test_seed_missing_src_is_noop(tmp_path: Path) -> None:
    assert seed_demo(tmp_path / "nope", tmp_path / "dst") == 0


def test_samples_without_manifest(keyless: Path) -> None:
    assert client.get("/api/samples").json() == []


@needs_bundle
def test_samples_route(keyless: Path) -> None:
    seed_demo(DEMO_DIR, keyless)
    body = client.get("/api/samples").json()
    assert body
    for entry in body:
        assert entry["image_url"].startswith("/files/samples/")
        assert client.get(entry["image_url"]).status_code == 200


@needs_bundle
def test_samples_replay_keyless(keyless: Path) -> None:
    """Drift guard: every sample replays from the bundled cache, key blank."""
    seed_demo(DEMO_DIR, keyless)
    for e in json.loads(MANIFEST.read_text()):
        res = _inspect(keyless / e["file"], e["profile_id"])
        assert res.status_code == 200, e["id"]
        body = res.json()
        assert body["demo"] is False, f"{e['id']} missed the cache: rerun build_demo.py"
        assert body["verdict"]["verdict"] == e["expect"]


@needs_bundle
def test_unknown_image_falls_back(keyless: Path) -> None:
    seed_demo(DEMO_DIR, keyless)
    before = {p.name for p in (keyless / "cache").glob("*.json")}
    e = json.loads(MANIFEST.read_text())[0]
    from PIL import Image

    other = keyless / "other.png"
    Image.new("RGB", (64, 64), (10, 200, 10)).save(other)
    res = _inspect(other, e["profile_id"])
    assert res.status_code == 200
    assert res.json()["demo"] is True
    # Fake ids only add entries keyed by fake-sam / fake-judge, never real ones:
    # replaying the samples afterwards must still be real.
    assert before <= {p.name for p in (keyless / "cache").glob("*.json")}
    assert _inspect(keyless / e["file"], e["profile_id"]).json()["demo"] is False


@needs_bundle
def test_rules_override_is_demo(keyless: Path) -> None:
    seed_demo(DEMO_DIR, keyless)
    e = json.loads(MANIFEST.read_text())[0]
    res = _inspect(keyless / e["file"], e["profile_id"], rules="FAIL everything.")
    assert res.status_code == 200
    assert res.json()["demo"] is True


def test_bundle_size() -> None:
    if not DEMO_DIR.is_dir():
        pytest.skip("backend/demo not built")
    total = sum(f.stat().st_size for f in DEMO_DIR.rglob("*") if f.is_file())
    assert total <= 40 * 1024 * 1024


ROOT = Path(__file__).resolve().parents[2]


def test_readme_is_docker_only() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for banned in ("uvicorn", "npm run dev", "venv", "docker run"):
        assert banned not in text
    assert "uvicorn" in (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")


def test_env_example_has_defaults_and_no_key() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "META_API_KEY=" in lines
    assert "SAM_MODEL_ID=sam-3.1" in lines
    assert "META_API_BASE_URL=https://api.meta.ai/v1" in lines
