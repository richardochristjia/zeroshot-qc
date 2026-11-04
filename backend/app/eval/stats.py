"""Bootstrap confidence intervals and McNemar tests from a run's ``results.jsonl``.

No model calls: everything is recomputed from the per-image records with the existing
metric functions.

Run: cd backend && .venv/bin/python -m app.eval.stats RUN_DIR [--vs RUN_DIR]
"""

from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path

import numpy as np

from app.eval.metrics import image_metrics

METRICS = ("f1", "auroc")


def load(run_dir: str | Path) -> list[dict]:
    with (Path(run_dir) / "results.jsonl").open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _point(records: list[dict]) -> dict[str, float]:
    return image_metrics(
        [r["label"] == "defective" for r in records],
        [r["verdict"] == "FAIL" for r in records],
        [float(r["fail_score"]) for r in records],
    )


def bootstrap(records: list[dict], B: int = 2000, seed: int = 0) -> dict[str, dict]:
    """Per-category and overall ``{metric: (point, lo, hi)}``, resampling images within category."""
    rng = np.random.default_rng(seed)
    groups = {c: [r for r in records if r["category"] == c] for c in sorted({r["category"] for r in records})}
    draws: dict[str, dict[str, list[float]]] = {
        name: {m: [] for m in METRICS} for name in (*groups, "overall")
    }
    for _ in range(B):
        pooled: list[dict] = []
        for name, group in groups.items():
            sample = [group[i] for i in rng.integers(0, len(group), len(group))]
            pooled += sample
            result = _point(sample)
            for m in METRICS:
                draws[name][m].append(result[m])
        result = _point(pooled)
        for m in METRICS:
            draws["overall"][m].append(result[m])
    points = {**{c: _point(g) for c, g in groups.items()}, "overall": _point(records)}
    return {
        name: {
            m: (points[name][m], *(float(v) for v in np.percentile(draws[name][m], [2.5, 97.5])))
            for m in METRICS
        }
        for name in draws
    }


def mcnemar(a: list[dict], b: list[dict]) -> dict:
    """Exact two-sided McNemar on per-image correctness (FAIL for defective), matched by image."""
    right_b = {r["image"]: (r["verdict"] == "FAIL") == (r["label"] == "defective") for r in b}
    b01 = b10 = 0  # b01: only B correct, b10: only A correct
    for r in a:
        if r["image"] not in right_b:
            continue
        right_a = (r["verdict"] == "FAIL") == (r["label"] == "defective")
        b10 += right_a and not right_b[r["image"]]
        b01 += right_b[r["image"]] and not right_a
    n = b01 + b10
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, k) for k in range(min(b01, b10) + 1)) / 2**n)
    return {"b01": b01, "b10": b10, "p": p}


def format_table(cis: dict[str, dict]) -> str:
    lines = ["| scope | F1 (95% CI) | AUROC (95% CI) |", "|---|---|---|"]
    for name, row in cis.items():
        cells = [f"{v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]" for v in (row["f1"], row["auroc"])]
        lines.append(f"| {name} | {cells[0]} | {cells[1]} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap CIs and McNemar from run results.")
    parser.add_argument("run_dir")
    parser.add_argument("--vs", default=None, help="second run for a McNemar test")
    parser.add_argument("--boots", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    records = load(args.run_dir)
    print(format_table(bootstrap(records, args.boots, args.seed)))
    if args.vs:
        print(f"McNemar {args.run_dir} vs {args.vs}: {mcnemar(records, load(args.vs))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
