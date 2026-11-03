"""Tune loop + router tests: fakes only, no network."""

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.tune.run as tune_run
from app.adapters.fakes import FakeImageGenerator, FakeRuleReviser
from app.config import settings
from app.eval.fakes import ScriptedFixtureSegmenter
from app.main import app
from app.schemas import DefectRuling, RuleRevision, Verdict
from app.tune.run import build_tune_set, run_tune

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mvtec"
BIG = 0.8  # score of real scripted components (false-positive box is lower)


class RulesJudge:
    """Verdict depends on the rules text: 'partial' FAILs big defects, 'always' FAILs all."""

    def __init__(self, threshold: int) -> None:
        self.threshold = threshold

    def judge(self, image, overlay, reference, detections, profile):
        area = sum(d.area_px for d in detections if d.score > BIG)
        if "always" in profile.rules:
            fail = True
        elif "partial" in profile.rules:
            fail = area >= self.threshold
        else:
            fail = False
        rulings = [
            DefectRuling(
                detection_id=d.id, is_real_defect=True, rule_violated="r", reason="x"
            )
            for d in detections[:1]
        ]
        return Verdict(
            verdict="FAIL" if fail else "PASS",
            confidence=0.9,
            rulings=rulings if fail else [],
            missed_defects=[],
            part_matches=True,
            summary="scripted",
        )


def _red(path: Path) -> int:
    px = np.asarray(Image.open(path).convert("RGB")).astype(int)
    return int(((px[:, :, 0] > 200) & (px[:, :, 1] < 100) & (px[:, :, 2] < 100)).sum())


def _kwargs(tmp_path: Path, reviser, **extra) -> dict:
    tune = dict(root=FIXTURE_ROOT, category="widget", n_good=1, n_synth=6, seed=0)
    areas = sorted(
        _red(p)
        for p, label in build_tune_set(
            FIXTURE_ROOT, "widget",
            sorted((FIXTURE_ROOT / "widget/train/good").glob("*.png"))[0],
            tmp_path / "probe", FakeImageGenerator(), 1, 6, 0,
        )
        if label == "defective"
    )
    return dict(
        tune,
        reviser=reviser,
        generator=FakeImageGenerator(),
        cache_dir=tmp_path / "cache",
        out_dir=tmp_path / "out",
        run_id="r1",
        segmenter_inner=ScriptedFixtureSegmenter(),
        judge_inner=RulesJudge(areas[len(areas) // 2]),
        **extra,
    )


def test_keeps_only_strict_improvements(tmp_path: Path) -> None:
    reviser = FakeRuleReviser(
        [
            RuleRevision(rules="partial rules", rationale="one"),
            RuleRevision(rules="partial again", rationale="two"),
        ]
    )
    record = run_tune(**_kwargs(tmp_path, reviser, adapter="scripted"))
    assert record["final_rules"] == "partial rules"
    assert [r["accepted"] for r in record["rounds"]] == [True, False]
    assert record["rounds"][0]["metrics"]["f1"] > 0
    assert set(record["heldout"]) == {"before", "after"}
    assert json.loads((tmp_path / "out/r1/tune.json").read_text()) == record


def test_stops_at_round_limit_and_without_errors(tmp_path: Path) -> None:
    reviser = FakeRuleReviser([RuleRevision(rules="always fail", rationale="x")])
    record = run_tune(**_kwargs(tmp_path, reviser, rounds=1))
    assert len(record["rounds"]) == 1 and len(reviser.calls) == 1


def test_no_errors_stops_at_round_zero(tmp_path: Path) -> None:
    reviser = FakeRuleReviser()
    # Only defective images, all FAIL under 'always': zero errors.
    kw = _kwargs(tmp_path, reviser, rules="always fail", n_good=0)
    record = run_tune(**kw)
    assert record["rounds"] == [] and reviser.calls == []
    assert record["final_rules"] == "always fail"


def test_heldout_untouched_before_loop_ends(tmp_path: Path, monkeypatch) -> None:
    seen: list[Path] = []
    real = tune_run._load
    monkeypatch.setattr(tune_run, "_load", lambda p: (seen.append(p), real(p))[1])
    reviser = FakeRuleReviser([RuleRevision(rules="partial rules", rationale="x")])
    kw = _kwargs(tmp_path, reviser)
    seen.clear()
    run_tune(**kw)
    test_dir = FIXTURE_ROOT / "widget" / "test"
    held = [i for i, p in enumerate(seen) if test_dir in p.parents]
    tune = [i for i, p in enumerate(seen) if test_dir not in p.parents]
    # Every held-out read comes after the last tune-set read.
    assert held and tune and min(held) > max(tune)
    # Tune set never reads test/ and never the reference as a tune item.
    ref = sorted((FIXTURE_ROOT / "widget/train/good").glob("*.png"))[0]
    items = build_tune_set(
        FIXTURE_ROOT, "widget", ref, tmp_path / "s", FakeImageGenerator(), 5, 2, 0
    )
    assert ref not in [p for p, _ in items]


def _write_run(root: Path, run_id: str, **over) -> None:
    record = {
        "run_id": run_id, "category": "widget", "adapter": "scripted", "seed": 0,
        "counts": {}, "initial_rules": "a", "final_rules": "b",
        "rounds": [{"round": 1, "rules": "b", "rationale": "r", "metrics": {"f1": 0.5}, "accepted": True}],
        "heldout": {"before": {"f1": 0.4}, "after": {"f1": 0.6}},
    }
    record.update(over)
    d = root / "tune" / run_id
    d.mkdir(parents=True)
    (d / "tune.json").write_text(json.dumps(record))


def test_router_list_detail_and_guards(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    _write_run(tmp_path, "run-a")
    (tmp_path / "tune" / "bad").mkdir()
    (tmp_path / "tune" / "bad" / "tune.json").write_text("{nope")
    client = TestClient(app)
    listed = client.get("/api/tune/runs").json()
    assert listed == [
        {"run_id": "run-a", "category": "widget", "adapter": "scripted",
         "before_f1": 0.4, "after_f1": 0.6, "rounds_accepted": 1}
    ]
    assert client.get("/api/tune/runs/run-a").json()["final_rules"] == "b"
    assert client.get("/api/tune/runs/missing").status_code == 404
    assert client.get("/api/tune/runs/bad").status_code == 404
    assert client.get("/api/tune/runs/%2E%2E").status_code == 404
    # Readable on disk but id outside [A-Za-z0-9_-]+: only the regex can reject it.
    (tmp_path / "tune" / "v1.0").mkdir()
    (tmp_path / "tune" / "v1.0" / "tune.json").write_text((tmp_path / "tune" / "run-a" / "tune.json").read_text())
    assert client.get("/api/tune/runs/v1.0").status_code == 404


@pytest.mark.parametrize("run_id", ["v1.0", "../escaped"])
def test_cli_rejects_run_id_the_router_cannot_serve(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(SystemExit):
        tune_run.main(["--category", "x", "--run-id", run_id, "--out-dir", str(tmp_path)])
    assert not any(tmp_path.iterdir())


def test_reviser_retries_once_then_raises(monkeypatch) -> None:
    import app.adapters.muse_spark as ms

    monkeypatch.setattr(settings, "judge_model_id", "m")
    monkeypatch.setattr(settings, "meta_api_key", "k")
    texts = iter(["not json", json.dumps({"rules": "ok rules", "rationale": "r"})])

    class Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"output": [{"content": [{"text": next(texts)}]}]}

    monkeypatch.setattr(ms.httpx, "post", lambda *a, **k: Resp())
    prompt = ms.render_tune_prompt("old", [{"label": "good"}], "widget")
    assert "old" in prompt and "widget" in prompt and '"label": "good"' in prompt
    assert ms.MuseSparkRuleReviser().revise("old", [], "widget").rules == "ok rules"
    texts = iter(["x", "y"])
    monkeypatch.setattr(ms.httpx, "post", lambda *a, **k: Resp())
    with pytest.raises(ms.JudgeValidationError):
        ms.MuseSparkRuleReviser().revise("old", [], "widget")


def test_tune_set_skips_failed_synth(tmp_path: Path) -> None:
    import httpx

    class FlakyGenerator(FakeImageGenerator):
        calls = 0

        def add_defect(self, image, defect, mask):  # type: ignore[no-untyped-def]
            FlakyGenerator.calls += 1
            if FlakyGenerator.calls == 2:
                raise httpx.HTTPStatusError("400", request=None, response=None)  # type: ignore[arg-type]
            return super().add_defect(image, defect, mask)

    ref = sorted((FIXTURE_ROOT / "widget/train/good").glob("*.png"))[0]
    items = build_tune_set(FIXTURE_ROOT, "widget", ref, tmp_path, FlakyGenerator(), 1, 3, 0)
    assert [label for _, label in items] == ["good", "defective", "defective"]
