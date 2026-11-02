"""Rule-tuning loop: revise the judge's rules from its mistakes on a tune set.

The tune set is good images from ``train/good`` plus Muse Image synthetic
defects on other train/good images, so no real defect and no ``test/``
image is seen while tuning. A revision is kept only on a strict F1 gain;
the first non-improvement (or zero errors) stops the loop. Held-out real
images from ``test/`` are scored once, after the loop, with the initial
and final rules. Writes ``<out-dir>/<run_id>/tune.json``.

Run: cd backend && .venv/bin/python -m app.tune.run --category bottle --adapter scripted
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from app.adapters.fakes import FakeImageGenerator, FakeRuleReviser
from app.config import settings
from app.eval.dataset import DatasetError, _iter_images, load_category, sample_dataset
from app.eval.metrics import confusion, precision_recall_f1
from app.eval.run import ADAPTER_CHOICES, EVAL_RULES, _resolve_adapters, build_eval_profile
from app.pipeline.cache import DiskCache
from app.pipeline.inspect import run_inspection
from app.synth.generate import diff_mask

SYNTH_DEFECTS = ["scratch", "crack", "contamination", "chip"]


def _load(path: Path) -> Image.Image:
    with Image.open(path) as raw:
        return raw.convert("RGB").copy()


def _make_scorer(category, segmenter, judge, reference):
    def score(rules: str, items: list[tuple[Path, str]]) -> dict:
        labels, predictions, errors = [], [], []
        for path, label in items:
            _, verdict = run_inspection(
                _load(path), build_eval_profile(category, rules), segmenter,
                judge=judge, reference=reference, part_crop=True, rules=rules,
            )
            predicted = verdict.verdict == "FAIL"
            labels.append(label == "defective")
            predictions.append(predicted)
            if predicted != (label == "defective"):
                errors.append(
                    {
                        "label": label,
                        "verdict": verdict.verdict,
                        "summary": verdict.summary,
                        "missed": [m.description for m in verdict.missed_defects],
                    }
                )
        metrics = precision_recall_f1(confusion(labels, predictions))
        return {"metrics": metrics, "errors": errors}

    return score


def build_tune_set(root, category, reference_path, run_dir, generator, n_good, n_synth, seed):
    """Seeded (path, label) items from train/good; synth images go under run_dir."""
    pool = [
        p for p in _iter_images(Path(root) / category / "train" / "good")
        if p != reference_path
    ]
    random.Random(f"{seed}/{category}/tune").shuffle(pool)
    good = pool[:n_good]
    bases = pool[n_good:] or pool  # shortcut: tiny pools reuse good images as synth bases
    items = [(p, "good") for p in good]
    synth_dir = run_dir / "synth"
    synth_dir.mkdir(parents=True, exist_ok=True)
    for index in range(n_synth if bases else 0):
        base = _load(bases[index % len(bases)])
        defect = SYNTH_DEFECTS[index % len(SYNTH_DEFECTS)]
        image = generator.add_defect(base, defect, None)
        if not np.any(diff_mask(base, image)):
            print(f"synth {index} ({defect}): empty diff, keeping as defective")
        path = synth_dir / f"{index:03d}.png"
        image.save(path)
        items.append((path, "defective"))
    return items


def run_tune(
    *, root, category, reviser, generator=None, adapter="scripted", rounds=3,
    seed=0, n_good=10, n_synth=10, heldout_good=10, heldout_defective=20,
    rules=EVAL_RULES, cache_dir, out_dir, run_id,
    segmenter_inner=None, judge_inner=None,
) -> dict:
    root = Path(root)
    generator = generator or FakeImageGenerator()
    segmenter, judge = _resolve_adapters(
        adapter, DiskCache(cache_dir), segmenter_inner, judge_inner
    )
    if judge is None:
        raise ValueError("tune needs a judge adapter")
    reference_path, _ = load_category(root, category)
    reference = _load(reference_path)
    run_dir = Path(out_dir) / run_id
    items = build_tune_set(
        root, category, reference_path, run_dir, generator, n_good, n_synth, seed
    )
    score = _make_scorer(category, segmenter, judge, reference)

    initial_rules = best_rules = rules
    best = score(rules, items)
    log = []
    for number in range(1, rounds + 1):
        if not best["errors"]:
            break
        revision = reviser.revise(best_rules, best["errors"], category)
        cand = score(revision.rules, items)
        accepted = cand["metrics"]["f1"] > best["metrics"]["f1"]
        log.append(
            {
                "round": number,
                "rules": revision.rules,
                "rationale": revision.rationale,
                "metrics": cand["metrics"],
                "accepted": accepted,
            }
        )
        if not accepted:
            break
        best, best_rules = cand, revision.rules

    # Held-out real test images are touched only here, after the loop.
    held = [
        (item.image_path, item.label)
        for sample in sample_dataset(root, [category], heldout_good, heldout_defective, seed)
        for item in sample.items
    ]
    record = {
        "run_id": run_id,
        "category": category,
        "adapter": adapter,
        "seed": seed,
        "counts": {
            "n_good": sum(1 for _, l in items if l == "good"),
            "n_synth": sum(1 for _, l in items if l == "defective"),
            "heldout_good": sum(1 for _, l in held if l == "good"),
            "heldout_defective": sum(1 for _, l in held if l == "defective"),
        },
        "initial_rules": initial_rules,
        "final_rules": best_rules,
        "rounds": log,
        "heldout": {
            "before": score(initial_rules, held)["metrics"],
            "after": score(best_rules, held)["metrics"],
        },
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "tune.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tune judge rules on a category.")
    parser.add_argument("--category", required=True)
    parser.add_argument("--adapter", choices=ADAPTER_CHOICES, default="scripted")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--n-good", type=int, default=10)
    parser.add_argument("--n-synth", type=int, default=10)
    parser.add_argument("--heldout-good", type=int, default=10)
    parser.add_argument("--heldout-defective", type=int, default=20)
    parser.add_argument("--root", default=settings.mvtec_dir)
    parser.add_argument("--rules", default=EVAL_RULES)
    parser.add_argument("--cache-dir", default=str(Path(settings.data_dir) / "cache"))
    parser.add_argument("--out-dir", default=str(Path(settings.data_dir) / "tune"))
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    run_id = args.run_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.category}"
    )
    if args.adapter == "real":
        from app.adapters.muse_image import MuseImageGenerator
        from app.adapters.muse_spark import MuseSparkRuleReviser

        generator, reviser = MuseImageGenerator(), MuseSparkRuleReviser()
    else:
        generator, reviser = FakeImageGenerator(), FakeRuleReviser()
    try:
        record = run_tune(
            root=args.root, category=args.category, reviser=reviser,
            generator=generator, adapter=args.adapter, rounds=args.rounds,
            seed=args.seed, n_good=args.n_good, n_synth=args.n_synth,
            heldout_good=args.heldout_good, heldout_defective=args.heldout_defective,
            rules=args.rules, cache_dir=args.cache_dir, out_dir=args.out_dir,
            run_id=run_id,
        )
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    before, after = record["heldout"]["before"], record["heldout"]["after"]
    print(f"run {run_id}: held-out F1 {before['f1']:.3f} -> {after['f1']:.3f}")
    print(f"wrote {args.out_dir}/{run_id}/tune.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
