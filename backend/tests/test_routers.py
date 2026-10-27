"""Router tests (M6 Routers phase): TestClient coverage for every route.

Run: cd backend && .venv/bin/python -m pytest -q
"""

import importlib.util
import io
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.main as main_module
import app.pipeline.inspect as inspect_mod
import app.routers.inspect as inspect_router
import app.routers.profiles as profiles_router
from app.adapters.fakes import FakeJudge, FakeSegmenter
from app.adapters.muse_spark import JudgeValidationError
from app.config import settings
from app.main import app
from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache
from app.pipeline.wiring import build_judge, build_segmenter
from app.schemas import InspectionResult, ProductProfile

client = TestClient(app)

IMG_W, IMG_H = 64, 48
REAL_PROFILES = Path(__file__).resolve().parent.parent / "profiles"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Point data + profiles at tmp dirs so no repo file is touched."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
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


def _png_bytes(color: tuple[int, int, int] = (150, 150, 150)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (IMG_W, IMG_H), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _use_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        inspect_router, "_get_segmenter", lambda cache=None: build_segmenter(True)
    )
    monkeypatch.setattr(
        inspect_router, "_get_judge", lambda cache=None: build_judge(True)
    )


def _post_inspect(
    raw: bytes, profile_id: str = "screw", rules: str | None = None
):
    data: dict[str, str] = {"profile_id": profile_id}
    if rules is not None:
        data["rules"] = rules
    return client.post(
        "/api/inspect",
        files={"image": ("part.png", raw, "image/png")},
        data=data,
    )


def test_inspect_happy_path_returns_result_with_fetchable_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_fakes(monkeypatch)
    resp = _post_inspect(_png_bytes())
    assert resp.status_code == 200
    result = InspectionResult.model_validate(resp.json())
    assert result.profile_id == "screw"
    assert result.verdict.verdict in ("PASS", "FAIL")
    assert set(result.timings_ms) == {"segment", "judge", "total"}
    overlay = client.get(result.overlay_url)
    assert overlay.status_code == 200
    assert overlay.headers["content-type"] == "image/png"


def test_inspect_same_image_new_rules_is_judge_only_cache_hit(
    monkeypatch: pytest.MonkeyPatch, isolated: dict
) -> None:
    """Second POST with edited rules must not re-run the segmenter."""
    cache = DiskCache(isolated["data"] / "cache")

    class CountingSegmenter:
        def __init__(self) -> None:
            self.calls = 0
            self._fake = FakeSegmenter()

        def segment(self, image: Image.Image, prompts: list[str]):  # type: ignore[no-untyped-def]
            self.calls += 1
            return self._fake.segment(image, prompts)

    inner = CountingSegmenter()
    segmenter = CachedSegmenter(inner, "fake-sam", cache)
    judge = CachedJudge(FakeJudge(), "fake-judge", cache)
    monkeypatch.setattr(inspect_router, "_get_segmenter", lambda cache=None: segmenter)
    monkeypatch.setattr(inspect_router, "_get_judge", lambda cache=None: judge)

    raw = _png_bytes()
    strict = _post_inspect(raw)
    assert strict.status_code == 200
    assert inner.calls == 1
    strict_verdict = strict.json()["verdict"]["verdict"]

    flipped = _post_inspect(raw, rules="lenient: pass everything for this check")
    assert flipped.status_code == 200
    assert inner.calls == 1  # segment cache hit; judge alone re-ran
    assert flipped.json()["verdict"]["verdict"] != strict_verdict


def test_inspect_double_judge_failure_is_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        inspect_router, "_get_segmenter", lambda cache=None: build_segmenter(True)
    )

    class BoomJudge:
        def judge(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise JudgeValidationError("judge output failed validation twice")

    monkeypatch.setattr(inspect_router, "_get_judge", lambda cache=None: BoomJudge())
    resp = _post_inspect(_png_bytes())
    assert resp.status_code == 422


def test_inspect_unknown_profile_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fakes(monkeypatch)
    assert _post_inspect(_png_bytes(), profile_id="no-such").status_code == 404


def test_profiles_list_get_put_roundtrip(isolated: dict) -> None:
    listed = client.get("/api/profiles")
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == ["screw"]

    one = client.get("/api/profiles/screw")
    assert one.status_code == 200
    assert ProductProfile.model_validate(one.json()).id == "screw"
    assert client.get("/api/profiles/no-such").status_code == 404

    before = (isolated["profiles"] / "screw.json").read_bytes()
    bad = client.put("/api/profiles/screw", json={"id": "screw"})
    assert bad.status_code == 422
    assert (isolated["profiles"] / "screw.json").read_bytes() == before

    mismatch = client.put(
        "/api/profiles/screw",
        json={**one.json(), "id": "other"},
    )
    assert mismatch.status_code == 422
    assert (isolated["profiles"] / "screw.json").read_bytes() == before

    updated = {**one.json(), "rules": "Edited rules for the round-trip."}
    put = client.put("/api/profiles/screw", json=updated)
    assert put.status_code == 200
    assert ProductProfile.model_validate(put.json()).rules.startswith("Edited rules")
    assert client.get("/api/profiles/screw").json()["rules"].startswith(
        "Edited rules"
    )


def test_from_sop_draft_saves_only_on_confirm(
    monkeypatch: pytest.MonkeyPatch, isolated: dict
) -> None:
    draft = {
        "id": "newgadget",
        "name": "newgadget",
        "defect_prompts": ["dent"],
        "rules": "FAIL a gadget with any dent; PASS otherwise.",
    }

    class StubSopJudge:
        def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
            return ProductProfile.model_validate(draft)

    monkeypatch.setattr(main_module, "_get_sop_judge", lambda: StubSopJudge())
    resp = client.post(
        "/api/profiles/from-sop",
        json={"sop_text": draft["rules"], "category_name": "newgadget"},
    )
    assert resp.status_code == 200
    assert ProductProfile.model_validate(resp.json()).id == "newgadget"
    assert not (isolated["profiles"] / "newgadget.json").exists()

    saved = client.put("/api/profiles/newgadget", json=resp.json())
    assert saved.status_code == 200
    assert (isolated["profiles"] / "newgadget.json").is_file()
    assert client.get("/api/profiles/newgadget").json()["id"] == "newgadget"


def _seed_run(data_dir: Path, run_id: str = "run1") -> Path:
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps({"run_id": run_id, "n": 2}), encoding="utf-8"
    )
    (run_dir / "results.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"image": "screw/good/000.png", "verdict": "PASS"}),
                json.dumps({"image": "/abs/evil.png", "verdict": "FAIL"}),
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "runs" / "stray").mkdir(parents=True)  # no summary.json: skipped
    return run_dir


def test_eval_list_skips_dirs_without_summary_and_detail_builds_urls(
    isolated: dict,
) -> None:
    _seed_run(isolated["data"])
    listed = client.get("/api/eval/runs")
    assert listed.status_code == 200
    assert [run["run_id"] for run in listed.json()] == ["run1"]

    detail = client.get("/api/eval/runs/run1")
    assert detail.status_code == 200
    body = detail.json()
    assert body["summary"]["source"] == "mvtec"  # defaulted for old summaries
    assert body["results"][0]["image_url"] == "/files/mvtec/screw/good/000.png"
    assert body["results"][1]["image_url"] is None  # absolute path: no URL


def test_eval_missing_run_is_404(isolated: dict) -> None:
    _seed_run(isolated["data"])
    assert client.get("/api/eval/runs/no-such-run").status_code == 404
    assert client.get("/api/eval/runs/%2E%2E").status_code == 404


def test_files_traversal_blocked(isolated: dict, tmp_path: Path) -> None:
    canary = tmp_path / "outside.txt"
    canary.write_text("SENTINEL-OUTSIDE-DATA-DIR", encoding="utf-8")
    for path in ("/files/../outside.txt", "/files/%2E%2E/outside.txt"):
        resp = client.get(path)
        assert resp.status_code == 404
        assert "SENTINEL-OUTSIDE-DATA-DIR" not in resp.text


def _load_cli():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[2] / "cli.py"
    spec = importlib.util.spec_from_file_location("cli_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_parity_identical_verdicts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same image + profile through the CLI and the route agree."""
    _use_fakes(monkeypatch)
    raw = _png_bytes()
    image_path = tmp_path / "part.png"
    image_path.write_bytes(raw)

    cli = _load_cli()
    assert cli.main(["inspect", str(image_path), "--profile", "screw", "--fake"]) == 0
    out = capsys.readouterr().out
    cli_verdict = re.search(r"^verdict: (PASS|FAIL)", out, re.M).group(1)
    cli_detections = re.findall(r"^d\d+ ", out, re.M)

    resp = _post_inspect(raw)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"]["verdict"] == cli_verdict
    assert len(body["detections"]) == len(cli_detections)


def _seed_synth(data_dir: Path) -> None:
    synth = data_dir / "synth"
    (synth / "bottle").mkdir(parents=True)
    (synth / "bottle" / "_reference.png").write_bytes(_png_bytes())
    dent = synth / "bottle" / "dent"
    dent.mkdir()
    (dent / "000.png").write_bytes(_png_bytes())
    (dent / "000_mask.png").write_bytes(_png_bytes())
    scratch = synth / "bottle" / "scratch"
    scratch.mkdir()
    (scratch / "000.png").write_bytes(_png_bytes())  # no mask sibling


def test_synth_gallery_grouping_reference_skip_and_missing_mask(
    isolated: dict,
) -> None:
    _seed_synth(isolated["data"])
    resp = client.get("/api/synth/gallery")
    assert resp.status_code == 200
    body = resp.json()
    assert body == [
        {
            "category": "bottle",
            "defect": "dent",
            "image_url": "/files/synth/bottle/dent/000.png",
            "mask_url": "/files/synth/bottle/dent/000_mask.png",
        },
        {
            "category": "bottle",
            "defect": "scratch",
            "image_url": "/files/synth/bottle/scratch/000.png",
            "mask_url": None,
        },
    ]
    assert all(entry["image_url"] != "/files/synth/bottle/_reference.png" for entry in body)
    # Mask-only files never appear as gallery images.
    assert all(not entry["image_url"].endswith("_mask.png") for entry in body)


def test_synth_gallery_empty_dir(isolated: dict) -> None:
    resp = client.get("/api/synth/gallery")
    assert resp.status_code == 200
    assert resp.json() == []
