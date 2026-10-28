# ZeroShot QC — M4: Eval harness

Tier M (8 files, no sensitive paths, no auth). Loop and steps are in `tier.md` next to this file.

## Problem

The pipeline inspects one image at a time, but nobody knows if it is any good: no sampled dataset loading, no precision/recall/F1/AUROC/IoU numbers, and no ablation proving SAM, the judge, and the reference image each earn their place. Without the harness, later prompt and profile tuning would be blind. `data/mvtec/` is empty, so automated proof runs on a committed fixture plus fakes; real MVTec is a manual rerun.

## Solution

- `eval/dataset.py`: generic MVTec-layout loader (reference is one train-good image; test items carry good/defective labels plus defect masks) and a fixed-seed sampler (10 good + 20 defective per category, flag-configurable); empty data gives guidance, never a traceback.
- `eval/metrics.py`: image-level precision/recall/F1/accuracy, AUROC over the fail score (`confidence` if FAIL else `1 - confidence`), pixel IoU of the kept-detection union vs ground truth on defective images — per category and overall.
- `eval/run.py`: CLI (`--mode sam_only|sam_judge|sam_judge_ref --categories ... --seed ...`) running each sampled image through the real `run_inspection` plus cache; modes differ only in judge wiring (`sam_only` = no judge, FAIL on any detection). Writes `data/runs/{run_id}/results.jsonl` and `summary.json`, prints the metrics table.
- Committed fixture (`backend/tests/fixtures/mvtec/`, 2 tiny synthetic categories with painted defects and exact masks) plus scripted fakes so the three modes differ measurably by construction.
- Ten preliminary profiles for the remaining MVTec categories, same JSON shape as the existing five.
- `docs/EVAL_NOTES.md`: fixture failure patterns and the profile/prompt changes made; real-data patterns are appended in the manual rerun.

## Files

- `backend/app/eval/__init__.py`, `dataset.py` — new; MVTec loader plus fixed-seed sampler.
- `backend/app/eval/metrics.py` — new; pure metric functions, no I/O.
- `backend/app/eval/run.py` — new; ablation CLI, run output, printed table.
- `backend/tests/fixtures/mvtec/` — new; 2 synthetic categories with images and exact masks.
- `backend/tests/test_eval_metrics.py`, `test_eval_run.py` — new; metric correctness plus end-to-end fixture runs.
- `backend/profiles/*.json` (10 new) — same `ProductProfile` shape, preliminary prompts.
- `docs/EVAL_NOTES.md` — new; failure patterns and changes made.

## Acceptance criteria

1. All three `--mode` runs complete on the fixture; `summary.json` holds per-category and overall metrics. Check: fixture runs in Verification.
2. Ablation ordering holds on the fixture: judge plus reference move F1 measurably vs `sam_only`. Check: `test_eval_run.py` plus printed table.
3. `pytest` is green; `data/` outputs stay gitignored; empty `data/mvtec/` gives guidance, not a traceback. Check: full suite plus empty-data run.
4. `manual:` the same three modes on 5 real MVTec categories, then all 15, with `EVAL_NOTES.md` updated from real failure patterns. Human steps: download MVTec, set `.env` keys, run the CLI per mode.

## Risks

- The fixture proves the harness, not real-world accuracy; fixture-tuned prompts may not transfer to MVTec. Flagged in `EVAL_NOTES.md`, settled by the manual rerun.
- Real MVTec archive layout may differ from the documented layout the loader assumes; mismatch surfaces as the guidance error and is fixed when data lands.
- Scripted fakes that separate the modes by construction could mask a real wiring bug; the runner test asserts each mode calls (or skips) the judge through `run_inspection`, not just that numbers differ.

## Test plan

- `test_eval_metrics.py`: perfect predictions score 1.0; all-PASS on defectives gives recall 0; perfect ranker AUROC 1.0; identical-mask IoU 1.0; good images excluded from IoU.
- `test_eval_run.py`: fixed seed gives identical samples; exact 10/20 counts; empty data errors cleanly; full 3-mode fixture run writes `results.jsonl` plus `summary.json`; changed rules cause a judge cache miss.
- Fixture image generation is deterministic (seeded); no large binaries committed — tiny PNGs only.
- Run command: `cd backend && .venv/bin/python -m pytest -q` (project venv, never the host global interpreter).
