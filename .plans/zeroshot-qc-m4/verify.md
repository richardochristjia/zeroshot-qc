# ZeroShot QC — M4 Verification (2026-10-27, branch `feat/zeroshot-qc-m4`)

## 1. pytest
`cd backend && .venv/bin/python -m pytest -q` → **129 passed**, 2 warnings (pre-existing RLE-size UserWarnings in `test_smoke.py`). Exit 0.

## 2. Three ablation modes on the fixture (`--mvtec-dir tests/fixtures/mvtec`)
| mode | overall P | overall R | overall F1 | AUROC | IoU |
|---|---|---|---|---|---|
| sam_only | 0.667 | 1.000 | 0.800 | 0.500 | 0.858 |
| sam_judge | 1.000 | 0.800 | 0.889 | 0.900 | 0.858 |
| sam_judge_ref | 1.000 | 1.000 | 1.000 | 1.000 | 0.858 |

Ordering holds: F1 0.800 → 0.889 → 1.000 (judge adds precision, reference restores recall).
Per-category rows (gizmo/widget, n=30 each) identical in shape; IoU ~0.86 both categories.

## 3. summary.json
`data/runs/verify_<mode>/results.jsonl` + `summary.json` written for all three.
Keys: `run_id, mode, adapter, seed, categories, n_good, n_defective, rules, metrics`
with `metrics = {per_category: {gizmo, widget}, overall: {precision, recall, f1, accuracy, auroc, n, tp, tn, fp, fn, iou}}`. Per-category + overall confirmed.

## 4. Empty-data run
`--mvtec-dir /tmp/zeroshot-empty-mvtec` → exit **2**, one-line guidance
("no MVTec categories found … download MVTec AD …"), no traceback. Clean.

## 5. data/ gitignored
`git check-ignore data/runs/verify_sam_only/summary.json` → ignored.
`git status` shows no tracked modifications and no `data/` entries
(only pre-existing untracked `.lavish/` and old `.plans/` notes).

## 6. Secrets grep
`grep -rniE "sk-ant|sk-|api[-_]?key|bearer |aws_secret|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY"`
over `backend/app/eval/`, `backend/tests/test_eval_*.py`, `backend/profiles/` → **no hits**.

## 7. Record entries
`.agents/RECORD.md` already holds the 3 approved eval entries
(10+20 sampling/metrics; ablation judge wiring; results.jsonl/summary.json persistence).

## Verdict
PASS on all M4 acceptance criteria 1–3. No fixes needed → no `fix(m4)` commit.
Criterion 4 (real MVTec rerun) remains a manual step. Verify run dirs
`data/runs/verify_*/` are gitignored scratch and were left in place.
