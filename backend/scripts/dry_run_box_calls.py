"""Cache-only dry run of the grounded eval: counts the SAM box calls a live re-eval would make.

Both inner adapters raise on call, so nothing reaches the network. Judge misses must be 0
(the judge replays from cache); each SAM miss is one paid call.

Run: cd backend && python -m scripts.dry_run_box_calls [--categories ...]
"""

import argparse
import json
import tempfile
from pathlib import Path

from app.config import settings
from app.eval.run import format_table, run_eval

CATEGORIES = ["bottle", "cable", "capsule", "carpet", "grid", "screw", "metal_nut"]


class _NoLive:
    def __init__(self) -> None:
        self.box_calls = 0
        self.other_sam_misses = 0
        self.judge_misses = 0

    def segment(self, image, prompts):
        if prompts[0].startswith("<0f>"):
            self.box_calls += 1
        else:
            self.other_sam_misses += 1
        raise RuntimeError("cache miss (segment)")

    def judge(self, *args, **kwargs):
        self.judge_misses += 1
        raise RuntimeError("cache miss (judge)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", nargs="*", default=CATEGORIES)
    args = parser.parse_args()
    seg, judge = _NoLive(), _NoLive()
    try:
        with tempfile.TemporaryDirectory() as out:
            _, summary = run_eval(
                root=settings.mvtec_dir, categories=args.categories, mode="grounded",
                adapter="real", cache_dir=Path(settings.data_dir) / "cache", out_dir=out,
                run_id="dry", segmenter_inner=seg, judge_inner=judge,
            )
        print(format_table(summary))
    finally:
        print(json.dumps({"sam_box_calls": seg.box_calls, "other_sam_misses": seg.other_sam_misses,
                          "judge_misses": judge.judge_misses}))


if __name__ == "__main__":
    main()
