"""Runner tests (M4): sampling, fixture runs, wiring, and cache behavior.

Run: cd backend && .venv/bin/python -m pytest -q
"""

import json
from pathlib import Path

import pytest

from app.eval.dataset import DatasetError, sample_dataset
from app.eval.fakes import ReferenceAwareJudge, ScriptedFixtureSegmenter
from app.eval.run import main, run_eval

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mvtec"


class CountingSegmenter(ScriptedFixtureSegmenter):
    def __init__(self) -> None:
        self.calls = 0

    def segment(self, image, prompts):
        self.calls += 1
        return super().segment(image, prompts)


class CountingJudge(ReferenceAwareJudge):
    def __init__(self) -> None:
        self.calls = 0

    def judge(self, image, overlay, reference, detections, profile):
        self.calls += 1
        return super().judge(image, overlay, reference, detections, profile)


def test_fixed_seed_gives_identical_samples() -> None:
    first = sample_dataset(FIXTURE_ROOT, seed=7)
    second = sample_dataset(FIXTURE_ROOT, seed=7)
    assert [
        (item.image_path, item.label) for sample in first for item in sample.items
    ] == [
        (item.image_path, item.label) for sample in second for item in sample.items
    ]


def test_sampler_yields_exact_counts() -> None:
    for sample in sample_dataset(FIXTURE_ROOT, seed=0):
        good = [i for i in sample.items if i.label == "good"]
        bad = [i for i in sample.items if i.label == "defective"]
        assert len(good) == 10
        assert len(bad) == 20
        assert sample.reference_path.is_file()


def test_empty_data_errors_cleanly(tmp_path: Path, capsys) -> None:
    empty = tmp_path / "mvtec"
    empty.mkdir()
    with pytest.raises(DatasetError):
        sample_dataset(empty)
    code = main(
        [
            "--mvtec-dir",
            str(empty),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--out-dir",
            str(tmp_path / "runs"),
            "--run-id",
            "empty",
        ]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "no MVTec categories" in captured.err


def _run_mode(tmp_path: Path, mode: str, run_id: str):
    return run_eval(
        root=FIXTURE_ROOT,
        mode=mode,
        seed=0,
        adapter="scripted",
        cache_dir=tmp_path / "cache",
        out_dir=tmp_path / "runs",
        run_id=run_id,
    )


def test_full_three_mode_run_writes_outputs(tmp_path: Path) -> None:
    summaries = {}
    for mode in ("sam_only", "sam_judge", "sam_judge_ref"):
        records, summary = _run_mode(tmp_path, mode, f"run-{mode}")
        summaries[mode] = summary
        run_dir = tmp_path / "runs" / f"run-{mode}"
        assert (run_dir / "results.jsonl").is_file()
        assert (run_dir / "summary.json").is_file()
        assert len(records) == 60  # 2 categories x (10 good + 20 defective)
        stored = json.loads((run_dir / "summary.json").read_text())
        assert set(stored["metrics"]["per_category"]) == {"widget", "gizmo"}
        assert "overall" in stored["metrics"]
    only = summaries["sam_only"]["metrics"]["overall"]["f1"]
    judged = summaries["sam_judge"]["metrics"]["overall"]["f1"]
    ref = summaries["sam_judge_ref"]["metrics"]["overall"]["f1"]
    assert only < judged < ref


def test_modes_differ_only_in_judge_wiring(tmp_path: Path) -> None:
    """sam_only skips the judge; judge modes call it through run_inspection."""
    segmenter = CountingSegmenter()
    judge = CountingJudge()
    records, _ = run_eval(
        root=FIXTURE_ROOT,
        mode="sam_only",
        seed=0,
        adapter="scripted",
        cache_dir=tmp_path / "cache",
        out_dir=tmp_path / "runs",
        run_id="wiring-only",
        segmenter_inner=segmenter,
        judge_inner=judge,
    )
    # Identical flat-good fixture images share one cache entry by design
    # (keys hash image bytes), so calls <= images; a rerun hits them all.
    assert 0 < segmenter.calls <= len(records)
    assert judge.calls == 0
    calls_before_rerun = segmenter.calls
    run_eval(
        root=FIXTURE_ROOT,
        mode="sam_only",
        seed=0,
        adapter="scripted",
        cache_dir=tmp_path / "cache",
        out_dir=tmp_path / "runs",
        run_id="wiring-only-rerun",
        segmenter_inner=segmenter,
        judge_inner=judge,
    )
    assert segmenter.calls == calls_before_rerun  # every rerun call was a hit
    assert judge.calls == 0
    judge.calls = 0
    run_eval(
        root=FIXTURE_ROOT,
        mode="sam_judge_ref",
        seed=0,
        adapter="scripted",
        cache_dir=tmp_path / "cache2",
        out_dir=tmp_path / "runs",
        run_id="wiring-ref",
        segmenter_inner=segmenter,
        judge_inner=judge,
    )
    assert judge.calls > 0


def test_changed_rules_cause_judge_cache_miss(tmp_path: Path) -> None:
    judge = CountingJudge()
    kwargs = dict(
        root=FIXTURE_ROOT,
        mode="sam_judge",
        seed=0,
        categories=["widget"],
        n_good=2,
        n_defective=2,
        adapter="scripted",
        cache_dir=tmp_path / "cache",
        out_dir=tmp_path / "runs",
        judge_inner=judge,
    )
    run_eval(run_id="rules-a", **kwargs)
    first_calls = judge.calls
    assert first_calls > 0
    run_eval(run_id="rules-b", **kwargs)  # same rules: judge served from cache
    assert judge.calls == first_calls
    run_eval(run_id="rules-c", rules="FAIL everything, always.", **kwargs)
    assert judge.calls > first_calls
