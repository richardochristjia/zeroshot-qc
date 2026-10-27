"""Ablation runner (M4): run the sampled images through the real pipeline.

Modes differ only in judge wiring (HANDOFF §9), everything else —
sampling, ``run_inspection``, cache — is shared::

    sam_only       no judge; FAIL on any detection above min_score
    sam_judge      judge without a reference image
    sam_judge_ref  judge with the category reference image (full system)

Writes ``<out-dir>/<run-id>/results.jsonl`` (one line per image) plus
``summary.json`` (per-category and overall metrics) and prints the
metrics table. ``--adapter scripted`` uses the eval-only scripted
fakes so the modes differ measurably by construction on the committed
fixture; ``fake`` uses the stock deterministic fakes; ``real`` calls
the configured models.

Run: cd backend && .venv/bin/python -m app.eval.run --mode sam_only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import settings
from app.eval.dataset import DatasetError, sample_dataset, sample_synth_dataset
from app.eval.fakes import ReferenceAwareJudge, ScriptedFixtureSegmenter
from app.eval.metrics import fail_score, pixel_iou, summarize
from app.pipeline.cache import CachedJudge, CachedSegmenter, DiskCache
from app.pipeline.inspect import run_inspection
from app.pipeline.wiring import build_judge, build_segmenter
from app.schemas import ProductProfile

MODES = ("sam_only", "sam_judge", "sam_judge_ref")
ADAPTER_CHOICES = ("real", "fake", "scripted")
DATA_CHOICES = ("mvtec", "synth")

EVAL_RULES = "FAIL any visible scratch, stain, or surface damage; PASS otherwise."

SAM_ONLY_CONFIDENCE = 1.0


def build_eval_profile(category: str, rules: str = EVAL_RULES) -> ProductProfile:
    """In-memory eval profile: fixture/real categories stay out of profiles/.

    ``reference_image`` is always unset — the reference is passed
    explicitly per mode, so ``sam_judge`` can never pick one up from
    disk and the modes differ only in judge wiring.
    """
    return ProductProfile(
        id=category,
        name=category,
        defect_prompts=["scratch", "stain", "damage"],
        rules=rules,
        mm_per_px=None,
        min_score=0.3,
        reference_image=None,
    )


def _load_mask(mask_path: Path | None) -> np.ndarray | None:
    if mask_path is None or not mask_path.is_file():
        return None
    with Image.open(mask_path) as raw:
        return (np.asarray(raw.convert("L")) > 128).astype(bool)


def _resolve_adapters(adapter: str, cache: DiskCache, inner_segmenter, inner_judge):
    """Shared cached adapters; ``fake``/``real`` go through wiring as-is."""
    if adapter == "fake" and inner_segmenter is None and inner_judge is None:
        return build_segmenter(True, cache), build_judge(True, cache)
    if adapter == "real" and inner_segmenter is None and inner_judge is None:
        return build_segmenter(False, cache), build_judge(False, cache)
    segmenter_inner = inner_segmenter
    if segmenter_inner is None:
        segmenter_inner = (
            ScriptedFixtureSegmenter() if adapter == "scripted" else None
        )
        if segmenter_inner is None:  # pragma: no cover - defensive
            raise ValueError(
                f"adapter {adapter!r} needs explicit inner adapters "
                "or wiring support"
            )
    judge_inner = inner_judge
    if judge_inner is None and adapter == "scripted":
        judge_inner = ReferenceAwareJudge()
    segmenter_id = {
        "scripted": "scripted-sam",
        "fake": "fake-sam",
        "real": settings.sam_model_id,
    }[adapter]
    judge_id = {
        "scripted": "scripted-judge",
        "fake": "fake-judge",
        "real": settings.judge_model_id,
    }[adapter]
    segmenter = CachedSegmenter(segmenter_inner, segmenter_id, cache)
    judge = (
        CachedJudge(judge_inner, judge_id, cache) if judge_inner is not None else None
    )
    return segmenter, judge


def run_eval(
    *,
    root: str | Path,
    categories: list[str] | None = None,
    mode: str = "sam_judge_ref",
    source: str = "mvtec",
    seed: int = 0,
    n_good: int = 10,
    n_defective: int = 20,
    adapter: str = "scripted",
    rules: str = EVAL_RULES,
    cache_dir: str | Path,
    out_dir: str | Path,
    run_id: str,
    segmenter_inner=None,
    judge_inner=None,
) -> tuple[list[dict], dict]:
    """Run one ablation mode; write ``results.jsonl`` + ``summary.json``."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}: expected one of {MODES}")
    if source not in DATA_CHOICES:
        raise ValueError(f"unknown source {source!r}: expected one of {DATA_CHOICES}")
    root = Path(root)
    if source == "synth":
        samples = sample_synth_dataset(root, categories, n_good, n_defective, seed)
    else:
        samples = sample_dataset(root, categories, n_good, n_defective, seed)
    cache = DiskCache(cache_dir)
    segmenter, judge = _resolve_adapters(
        adapter, cache, segmenter_inner, judge_inner
    )
    if mode != "sam_only" and judge is None:
        raise ValueError(f"mode {mode!r} needs a judge adapter")

    records: list[dict] = []
    for sample in samples:
        profile = build_eval_profile(sample.category, rules)
        reference = None
        if mode == "sam_judge_ref":
            with Image.open(sample.reference_path) as raw:
                reference = raw.convert("RGB").copy()
        for item in sample.items:
            with Image.open(item.image_path) as raw:
                image = raw.convert("RGB").copy()
            if mode == "sam_only":
                detections = run_inspection(image, profile, segmenter)
                verdict_word = "FAIL" if detections else "PASS"
                confidence = SAM_ONLY_CONFIDENCE
            else:
                detections, verdict = run_inspection(
                    image, profile, segmenter, judge=judge, reference=reference
                )
                verdict_word = verdict.verdict
                confidence = verdict.confidence
            truth = _load_mask(item.mask_path)
            iou = (
                pixel_iou(
                    [d.model_dump()["mask_rle"] for d in detections],
                    truth,
                    image.size[0],
                    image.size[1],
                )
                if truth is not None
                else None
            )
            try:
                shown = str(item.image_path.relative_to(root))
            except ValueError:
                shown = str(item.image_path)
            records.append(
                {
                    "category": item.category,
                    "image": shown,
                    "label": item.label,
                    "defect_type": item.defect_type,
                    "verdict": verdict_word,
                    "confidence": confidence,
                    "fail_score": fail_score(verdict_word, confidence),
                    "n_detections": len(detections),
                    "iou": iou,
                }
            )

    summary = {
        "run_id": run_id,
        "mode": mode,
        "source": source,
        "adapter": adapter,
        "seed": seed,
        "categories": [sample.category for sample in samples],
        "n_good": n_good,
        "n_defective": n_defective,
        "rules": rules,
        "metrics": summarize(records),
    }
    run_dir = Path(out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    return records, summary


def format_table(summary: dict) -> str:
    """Render the per-category plus overall metrics table."""
    metrics = summary["metrics"]
    header = f"{'category':<12}{'n':>4}{'P':>7}{'R':>7}{'F1':>7}{'AUROC':>7}{'IoU':>7}"
    lines = [
        f"run {summary['run_id']} mode={summary['mode']} "
        f"adapter={summary['adapter']} seed={summary['seed']}",
        header,
    ]
    rows = dict(metrics["per_category"])
    rows["overall"] = metrics["overall"]
    for name, row in rows.items():
        iou = "-" if row["iou"] is None else f"{row['iou']:.3f}"
        lines.append(
            f"{name:<12}{row['n']:>4.0f}{row['precision']:>7.3f}"
            f"{row['recall']:>7.3f}{row['f1']:>7.3f}"
            f"{row['auroc']:>7.3f}{iou:>7}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m app.eval.run --mode sam_judge_ref [--categories ...]``."""
    parser = argparse.ArgumentParser(description="Run the M4 eval ablation.")
    parser.add_argument("--mode", choices=MODES, default="sam_judge_ref")
    parser.add_argument("--categories", nargs="*", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--n-good", type=int, default=10)
    parser.add_argument("--n-defective", type=int, default=20)
    parser.add_argument("--adapter", choices=ADAPTER_CHOICES, default="scripted")
    parser.add_argument("--data", choices=DATA_CHOICES, default="mvtec")
    parser.add_argument("--rules", default=EVAL_RULES)
    parser.add_argument("--mvtec-dir", default=settings.mvtec_dir)
    parser.add_argument(
        "--synth-dir", default=str(Path(settings.data_dir) / "synth")
    )
    parser.add_argument(
        "--cache-dir", default=str(Path(settings.data_dir) / "cache")
    )
    parser.add_argument(
        "--out-dir", default=str(Path(settings.data_dir) / "runs")
    )
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    run_id = args.run_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.mode}"
    )
    try:
        _, summary = run_eval(
            root=args.synth_dir if args.data == "synth" else args.mvtec_dir,
            categories=args.categories,
            mode=args.mode,
            source=args.data,
            seed=args.seed,
            n_good=args.n_good,
            n_defective=args.n_defective,
            adapter=args.adapter,
            rules=args.rules,
            cache_dir=args.cache_dir,
            out_dir=args.out_dir,
            run_id=run_id,
        )
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_table(summary))
    print(f"wrote {args.out_dir}/{run_id}/results.jsonl and summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
