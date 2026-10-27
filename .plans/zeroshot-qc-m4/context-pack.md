# Context pack

BASE: main
CHANGED: 124 files, +1377/-0 (20 text files; 104 committed fixture PNGs; no deletions)

## What this change does
M4 adds an MVTec eval harness: a fixed-seed dataset sampler (10 good + 20 defective per category), pure image/AUROC/IoU metric functions, and a CLI runner with three ablation modes (`sam_only`/`sam_judge`/`sam_judge_ref`) that differ only in judge wiring. Proof runs on a committed 2-category synthetic fixture plus scripted fakes; real MVTec is a manual rerun.

## Files
- `backend/app/eval/__init__.py` — new package marker; owns nothing behavioral
- `backend/app/eval/dataset.py:1` — MVTec-layout loader; reference = first sorted `train/good` image; `DatasetError` with guidance on empty data, never a traceback
- `backend/app/eval/metrics.py:1` — pure metrics; defective is the positive class; good images contribute `None` IoU and are excluded from the mean
- `backend/app/eval/fakes.py:1` — eval-only scripted adapters; separate the three modes by construction through the real `run_inspection` + cache
- `backend/app/eval/run.py:1` — ablation CLI; writes `data/runs/{run_id}/results.jsonl` + `summary.json`; prints the metrics table
- `backend/tests/fixtures/mvtec/fixture.py:54` — deterministic generator (`generate()`); 2 categories × (2 train-good, 10 test-good, 20 scratch defects: 16 large + 4 tiny 2x2)
- `backend/tests/fixtures/mvtec/{widget,gizmo}/...` — 104 committed tiny PNGs (48x48 flat-gray, pure-red defects, exact masks); defects keep a 4px margin clear of the scripted 2x2 false-positive box at (0,0)
- `backend/tests/test_eval_metrics.py:31` — metric correctness (perfect=1.0, all-PASS recall 0, AUROC 1.0, identical-mask IoU 1.0, good-image exclusion)
- `backend/tests/test_eval_run.py:36` — sampler determinism/counts, empty-data error, full 3-mode run, per-mode judge-wiring assertion, rules-change cache miss
- `backend/profiles/{cable,capsule,grid,leather,pill,tile,toothbrush,transistor,wood,zipper}.json` — 10 preliminary profiles, same `ProductProfile` shape, placeholder rules, `mm_per_px: null` pending M5
- `docs/EVAL_NOTES.md:1` — fixture failure patterns + measured fixture numbers (F1 0.800/0.889/1.000, AUROC 0.500/0.900/1.000); real-data section stub for the manual rerun
- `.agents/RECORD.md:53` — 3 eval entries appended (sampling/metrics, ablation modes, data/runs persistence)

## API contracts
- CLI: `cd backend && .venv/bin/python -m app.eval.run --mode {sam_only|sam_judge|sam_judge_ref} [--categories ...] [--seed 0] [--adapter scripted|fake|real]` → exit 0 + printed table; exit 2 with `error: ...` on `DatasetError`; declared in `backend/app/eval/run.py:199`
- `run_eval(...) -> tuple[list[dict], dict]` at `backend/app/eval/run.py:107` — record dicts carry `category/image/label/defect_type/verdict/confidence/fail_score/n_detections/iou`; summary carries `run_id/mode/adapter/seed/categories/n_good/n_defective/rules/metrics`
- `summarize(records) -> {per_category, overall}` at `backend/app/eval/metrics.py:140` — overall image metrics pool all images; overall IoU pools defective images with non-None IoU
- `fail_score(verdict, confidence)` at `backend/app/eval/metrics.py:15` — `confidence` on FAIL, `1 - confidence` on PASS (AUROC input)
- `sample_dataset(root, categories, n_good=10, n_defective=20, seed=0)` at `backend/app/eval/dataset.py:134` — RNG seeded per `(seed, category)` so samples are stable when categories are added/removed
- No HTTP endpoints cross this change; output schemas are the JSONL/summary shapes above.

## Test entry points
- `backend/tests/test_eval_metrics.py` — `cd backend && .venv/bin/python -m pytest tests/test_eval_metrics.py -q`
- `backend/tests/test_eval_run.py` — `cd backend && .venv/bin/python -m pytest tests/test_eval_run.py -q`
- Full suite: `cd backend && .venv/bin/python -m pytest -q` (project venv, never host global)

## Acceptance criteria
1. All three `--mode` runs complete on the fixture; `summary.json` holds per-category and overall metrics. Check: fixture runs in Verification.
2. Ablation ordering holds on the fixture: judge plus reference move F1 measurably vs `sam_only`. Check: `test_eval_run.py` plus printed table.
3. `pytest` is green; `data/` outputs stay gitignored; empty `data/mvtec/` gives guidance, not a traceback. Check: full suite plus empty-data run.
4. manual: the same three modes on 5 real MVTec categories, then all 15, with `EVAL_NOTES.md` updated from real failure patterns. Human steps: download MVTec, set `.env` keys, run the CLI per mode.

## Do not re-derive
- Reference selection is first-sorted `train/good` image (`backend/app/eval/dataset.py:77`); `reference_image` on the eval profile is always unset (`backend/app/eval/run.py:48`) so `sam_judge` can never pick one up from disk.
- `sam_only` has no judge: FAIL on any detection above `min_score`, confidence pinned to 1.0 (`backend/app/eval/run.py:45`); its fixture precision == prevalence by construction.
- IoU is identical across modes (~0.86) because segmentation is shared — IoU measures the segmenter, F1 measures the judge wiring.
- Fixture-tuned behavior may not transfer to MVTec; the scripted fakes separate modes by construction, so the wiring test asserts per-mode judge invocation (`CountingJudge` in `backend/tests/test_eval_run.py:27`), not just differing numbers.
- `data/mvtec/` is empty in-repo; automated proof uses the committed fixture only. `data/` outputs stay gitignored.

## Diff
Full text diff is over budget (54KB), split by group — reproduce exactly with:
- `git diff main...HEAD -- . ':!*.png' ':!backend/profiles/'` — Group A: all eval source, tests, fixture generator, notes, RECORD (the review core)
- `git diff main...HEAD -- backend/profiles/` — Group B: 10 boilerplate profiles (all `reference_image: null`, `mm_per_px: null`, placeholder rules)
- `git diff main...HEAD --stat -- '*.png'` — Group C: 104 fixture PNGs, all new tiny files (129–162B test/train, 91–100B masks), generated by `fixture.py`
```diff
diff --git a/.agents/RECORD.md b/.agents/RECORD.md
index a7a79ab..a88cfd4 100644
--- a/.agents/RECORD.md
+++ b/.agents/RECORD.md
@@ -50,3 +50,6 @@
 - (pipeline) A FAIL verdict is currently forced in code when any ruling cites a violated rule or any missed defect exists.
+- (eval) Eval currently samples 10 good plus 20 defective images per category with a fixed seed and scores precision, recall, F1, accuracy, AUROC over the fail score, and pixel IoU on defectives.
+- (eval) Ablation modes currently differ only in judge wiring: any-detection FAIL without a judge, judge without a reference image, and judge with the category reference image.
+- (eval) Eval runs currently persist per-image results.jsonl plus a summary.json of per-category and overall metrics under data/runs/{run_id}.
 diff --git a/backend/app/eval/__init__.py b/backend/app/eval/__init__.py
 new file mode 100644
index 0000000..4b9fed2
--- /dev/null
+++ b/backend/app/eval/__init__.py
@@ -0,0 +1 @@
+"""Eval package (M4): dataset loading, metrics, and the ablation runner."""
```
Remainder of Group A per the command above: `dataset.py` (+179), `fakes.py` (+162), `metrics.py` (+173), `run.py` (+273), `fixture.py` (+107), `test_eval_metrics.py` (+116), `test_eval_run.py` (+176), `EVAL_NOTES.md` (+66). No file bodies in this pack — open the file at its anchor.
