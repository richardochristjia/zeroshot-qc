"""Smoke tests: fake run, data-missing exit, overlay collisions,
verdict-validation exit, and mismatched-RLE overlay handling.

Run: cd backend && .venv/bin/python -m pytest tests/test_smoke.py
"""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.adapters.fakes import FakeSegmenter
from app.config import settings
from app.schemas import RawMask, Verdict


def _load_smoke():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke.py"
    spec = importlib.util.spec_from_file_location("smoke_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = _load_smoke()

IMAGE_W, IMAGE_H = 40, 30


@pytest.fixture
def smoke_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    mvtec_dir = tmp_path / "mvtec"
    data_dir.mkdir()
    mvtec_dir.mkdir()
    monkeypatch.setattr(settings, "data_dir", str(data_dir))
    monkeypatch.setattr(settings, "mvtec_dir", str(mvtec_dir))
    return data_dir, mvtec_dir


def _save_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (IMAGE_W, IMAGE_H), color=color).save(path, format="PNG")


def test_fake_smoke_placeholders_exit_zero(
    smoke_dirs, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir, _mvtec_dir = smoke_dirs
    assert smoke.main(["--fake"]) == 0
    captured = capsys.readouterr()
    count_lines = [
        line for line in captured.out.splitlines() if ": scratch=" in line
    ]
    assert len(count_lines) == 3
    overlays = sorted((data_dir / "runs" / "smoke").glob("*_overlay.png"))
    assert len(overlays) == 3
    verdict_lines = [
        line for line in captured.out.splitlines() if line.startswith("verdict: ")
    ]
    assert len(verdict_lines) == 1
    parsed = json.loads(verdict_lines[0].removeprefix("verdict: "))
    assert isinstance(Verdict.model_validate(parsed), Verdict)


def test_real_smoke_empty_dirs_data_missing_exits_one(
    smoke_dirs, capsys: pytest.CaptureFixture[str]
) -> None:
    assert smoke.main([]) == 1
    captured = capsys.readouterr()
    assert "data missing" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_smoke_same_stem_images_produce_three_overlays(
    smoke_dirs, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir, mvtec_dir = smoke_dirs
    _save_image(mvtec_dir / "cat1" / "000.png", (200, 30, 30))
    _save_image(mvtec_dir / "cat2" / "000.png", (30, 200, 30))
    _save_image(mvtec_dir / "cat3" / "000.png", (30, 30, 200))
    assert smoke.main(["--fake"]) == 0
    capsys.readouterr()
    overlays = sorted((data_dir / "runs" / "smoke").glob("*.png"))
    assert len(overlays) == 3
    assert len({p.name for p in overlays}) == 3


def test_make_overlay_skips_mismatched_rle_without_raising() -> None:
    image = Image.new("RGB", (IMAGE_W, IMAGE_H), color=(120, 120, 120))
    donor = FakeSegmenter().segment(
        Image.new("RGB", (200, 200), color=(120, 120, 120)), ["scratch"]
    )[0]
    mask = RawMask(label="scratch", score=0.9, mask_rle=donor.mask_rle)
    assert donor.mask_rle["size"] == [200, 200]
    overlay = smoke._make_overlay(image, [mask])
    assert overlay.size == (IMAGE_W, IMAGE_H)


class _StubResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


def test_smoke_judge_validation_failure_exits_one(
    smoke_dirs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _data_dir, mvtec_dir = smoke_dirs
    _save_image(mvtec_dir / "a.png", (200, 30, 30))
    _save_image(mvtec_dir / "b.png", (30, 200, 30))
    _save_image(mvtec_dir / "c.png", (30, 30, 200))
    monkeypatch.setattr(settings, "meta_api_key", "test-key")
    monkeypatch.setattr(settings, "meta_api_base_url", "https://example.test/meta")
    monkeypatch.setattr(settings, "sam_model_id", "sam-test")
    monkeypatch.setattr(settings, "judge_model_id", "judge-test")
    valid_masks = FakeSegmenter().segment(
        Image.new("RGB", (IMAGE_W, IMAGE_H), color=(120, 120, 120)),
        ["scratch", "crack", "dent"],
    )

    def _stub(*args, **kwargs):  # type: ignore[no-untyped-def]
        payload = kwargs.get("json") or {}
        if payload.get("model") == "sam-test":
            return _StubResponse(
                {
                    "masks": [
                        {
                            "label": m.label,
                            "score": m.score,
                            "mask_rle": m.mask_rle,
                        }
                        for m in valid_masks
                    ]
                }
            )
        return _StubResponse(
            {
                "verdict": "PASS",
                "confidence": 99,
                "rulings": [],
                "missed_defects": [],
                "summary": "bad confidence",
            }
        )

    monkeypatch.setattr(httpx, "post", _stub)
    assert smoke.main([]) == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
