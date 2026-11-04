"""Live timing and cost of the grounded inspection. PAID: every call goes to the Meta API.

Picks 20 MVTec test images that are not in the seed-0 eval sample (5 categories x 2 good +
2 defective), inspects each through a FRESH temp cache so every call is live, counts calls and
Spark tokens per part, and times one SOP-to-profile draft. Writes data/runs/timing-<ts>.json.

    python -m scripts.time_inspect --dry     # list the images and the call budget, no API
    python -m scripts.time_inspect           # the paid run (about 81 calls)
"""

import argparse
import json
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

import app.adapters.muse_spark as muse_spark_mod
import app.adapters.sam as sam_mod
from app.config import settings
from app.eval.dataset import sample_dataset
from app.eval.run import build_eval_profile
from app.pipeline.cache import DiskCache
from app.pipeline.inspect import run_inspection
from app.pipeline.wiring import build_judge, build_segmenter

CATEGORIES = ["bottle", "cable", "capsule", "carpet", "grid"]
# Prices from https://dev.meta.ai/docs/pricing-rate-limits, opened 2026-11-04.
SAM_USD_PER_IMAGE = 2.50 / 1000
SPARK_USD_PER_M_IN = 1.25  # uncached input; cached input is $0.15, so this is an upper bound
SPARK_USD_PER_M_OUT = 4.25
SOP_TEXT = (
    "Glass bottle, top view. Reject a bottle with a crack, a chip on the rim, or a visible "
    "stain or contamination inside. Small surface marks that do not affect the glass are fine."
)


def select_images(root, categories, per_label=2, seed=7, exclude_seed=0, n_good=10, n_defective=20):
    """per_label good + per_label defective per category, none in the seed-0 eval sample."""
    taken = {
        item.image_path
        for sample in sample_dataset(root, categories, n_good, n_defective, exclude_seed)
        for item in sample.items
    }
    picks = []
    for sample in sample_dataset(root, categories, 10, 20, seed):
        for label in ("good", "defective"):
            chosen = [i for i in sample.items if i.label == label and i.image_path not in taken]
            picks += [(sample, item) for item in chosen[:per_label]]
    return picks


class _Counter:
    def __init__(self) -> None:
        self.calls = {"sam": 0, "sam_box": 0, "spark": 0}
        self.tokens = {"in": 0, "out": 0}

    def wrap(self, kind, real_post):
        def post(url, **kwargs):
            self.calls[kind] += 1
            if kind == "sam":
                texts = [c.get("text", "") for m in kwargs["json"]["input"] for c in m["content"]]
                if any(t.startswith("<0f>") for t in texts):
                    self.calls["sam_box"] += 1
            response = real_post(url, **kwargs)
            if kind == "spark":
                usage = (response.json() or {}).get("usage") or {}
                self.tokens["in"] += int(usage.get("input_tokens") or 0)
                self.tokens["out"] += int(usage.get("output_tokens") or 0)
            return response

        return post

    def snapshot(self):
        return {"calls": dict(self.calls), "tokens": dict(self.tokens)}


def _usd(calls, tokens):
    return (
        calls["sam"] * SAM_USD_PER_IMAGE
        + tokens["in"] * SPARK_USD_PER_M_IN / 1e6
        + tokens["out"] * SPARK_USD_PER_M_OUT / 1e6
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="list images and the call budget; no API")
    args = parser.parse_args()
    picks = select_images(settings.mvtec_dir, CATEGORIES)
    if args.dry:
        for sample, item in picks:
            print(item.label, item.image_path)
        # per image: part + defect SAM, judge, optional box SAM; plus one reference part lookup per category
        print(f"{len(picks)} images; up to {len(picks) * 4 + len(CATEGORIES) + 1} calls incl. 1 SOP draft")
        return

    counter = _Counter()
    sam_mod.post_with_retry = counter.wrap("sam", sam_mod.post_with_retry)
    muse_spark_mod.post_with_retry = counter.wrap("spark", muse_spark_mod.post_with_retry)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        cache = DiskCache(Path(tmp))
        segmenter, judge = build_segmenter(False, cache), build_judge(False, cache)
        for sample, item in picks:
            profile = build_eval_profile(sample.category)
            with Image.open(sample.reference_path) as r:
                reference = r.convert("RGB").copy()
            with Image.open(item.image_path) as r:
                image = r.convert("RGB").copy()
            before = counter.snapshot()
            start = time.perf_counter()
            _, verdict = run_inspection(
                image, profile, segmenter, judge=judge, reference=reference, part_crop=True
            )
            seconds = time.perf_counter() - start
            after = counter.snapshot()
            calls = {k: after["calls"][k] - before["calls"][k] for k in after["calls"]}
            tokens = {k: after["tokens"][k] - before["tokens"][k] for k in after["tokens"]}
            rows.append({"category": sample.category, "label": item.label, "verdict": verdict.verdict,
                         "seconds": round(seconds, 2), "calls": calls, "tokens": tokens,
                         "usd": round(_usd(calls, tokens), 5)})
            print(json.dumps(rows[-1]), flush=True)
        before = counter.snapshot()
        start = time.perf_counter()
        judge_adapter = muse_spark_mod.MuseSparkJudge()
        judge_adapter.sop_to_profile(SOP_TEXT, "bottle")
        sop_seconds = time.perf_counter() - start
        after = counter.snapshot()
    secs = sorted(r["seconds"] for r in rows)
    out = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "n_images": len(rows),
        "seconds_median": statistics.median(secs),
        "seconds_p90": secs[min(len(secs) - 1, int(0.9 * len(secs)))],
        "calls_per_part": {k: sum(r["calls"][k] for r in rows) / len(rows) for k in counter.calls},
        "usd_per_part_mean": sum(r["usd"] for r in rows) / len(rows),
        "sop_draft_seconds": round(sop_seconds, 2),
        "sop_draft_calls": after["calls"]["spark"] - before["calls"]["spark"],
        "prices": {"sam_per_image": SAM_USD_PER_IMAGE, "spark_in_per_m": SPARK_USD_PER_M_IN,
                   "spark_out_per_m": SPARK_USD_PER_M_OUT, "source": "dev.meta.ai/docs/pricing-rate-limits, 2026-11-04"},
        "rows": rows,
    }
    path = Path(settings.data_dir) / "runs" / f"timing-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
