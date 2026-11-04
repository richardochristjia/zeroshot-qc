import json
from pathlib import Path

from app.eval.stats import bootstrap, load, mcnemar


def _records() -> list[dict]:
    out = []
    for cat in ("a", "b"):
        for i in range(12):
            defective = i % 2 == 0
            fail = defective if i % 6 else not defective  # a few errors
            out.append({"category": cat, "image": f"{cat}/{i}", "label": "defective" if defective else "good",
                        "verdict": "FAIL" if fail else "PASS", "fail_score": 0.9 if fail else 0.1, "iou": None})
    return out


def test_bootstrap_deterministic_and_brackets_point() -> None:
    recs = _records()
    first = bootstrap(recs, B=200, seed=3)
    assert first == bootstrap(recs, B=200, seed=3)
    for row in first.values():
        point, lo, hi = row["f1"]
        assert lo <= point <= hi


def test_point_f1_matches_summary(tmp_path: Path) -> None:
    from app.eval.metrics import summarize

    recs = _records()
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
    assert bootstrap(load(tmp_path), B=10)["overall"]["f1"][0] == summarize(recs)["overall"]["f1"]


def test_mcnemar_identical_runs_p_is_one() -> None:
    recs = _records()
    assert mcnemar(recs, recs) == {"b01": 0, "b10": 0, "p": 1.0}


def test_mcnemar_exact_p() -> None:
    a, b = _records(), _records()
    for r in b[:5]:  # flip 5 verdicts: only A correct on those
        r["verdict"] = "PASS" if r["verdict"] == "FAIL" else "FAIL"
    res = mcnemar(a, b)
    assert res["b01"] + res["b10"] == 5 and 0 < res["p"] <= 1
    assert mcnemar(a, [dict(r, verdict="PASS") for r in a])["p"] < 0.05
