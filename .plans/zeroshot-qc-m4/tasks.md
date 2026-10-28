# ZeroShot QC — M4 Tasks

Spec: `plan.md` in this folder. Tier: `tier.md` in this folder. Base: `main` (M3 PR #3 merged).

Durable-test rule: `test_eval_metrics.py` and `test_eval_run.py` are deliverables in the repo's pytest layout — keep the smallest focused tests with the project, prove each fix with a failing-first test, and run the full suite once at the end (not after every edit).

## Dataset + metrics
- [x] Implement `eval/dataset.py` (generic MVTec loader, reference selection, fixed-seed 10/20 sampler, clean empty-data error)
- [x] Implement pure `eval/metrics.py` (precision/recall/F1/accuracy, AUROC over fail score, pixel IoU on defectives)
- [x] Create `test_eval_metrics.py` (perfect scores, all-PASS recall 0, AUROC 1.0, IoU identity, good-image exclusion)

## Runner + fixture
- [x] Create the 2-category committed fixture with exact masks under `backend/tests/fixtures/mvtec/`
- [x] Implement `eval/run.py` (3 ablation modes through `run_inspection` + cache, `results.jsonl`/`summary.json`, printed table)
- [x] Create `test_eval_run.py` (seed determinism, exact counts, empty-data error, full 3-mode run, rules-change cache miss)

## Profiles + notes
- [x] Ship 10 preliminary profiles for the remaining MVTec categories (same JSON shape as existing 5)
- [x] Write `docs/EVAL_NOTES.md` (fixture failure patterns, changes made, real-data section stub for the manual rerun)

## Verification
- [x] All three modes run on the fixture; `summary.json` has per-category and overall metrics; ablation ordering holds
- [x] `pytest` green; `data/` outputs gitignored; empty-data run errors cleanly
- [x] Record Updates: append the 3 eval entries from the approved plan — first (1) review the complete implementation; (2a) if it matches, write those exact entries into `.agents/RECORD.md`; (2b) if it diverged, write nothing and surface the divergence in the final summary instead. (Note: Tier M spec format has no Record section by rule — the entries live in the approved chat plan: the eval sampling/metrics entry, the ablation-modes entry, the data/runs persistence entry.)

## Manual checks
- [ ] manual: with MVTec downloaded and keys set, run all three modes on 5 real categories, then all 15; update `EVAL_NOTES.md` from real failure patterns
