# Correctness review — M4 (branch `feat/zeroshot-qc-m4`)

Scope: correctness only, per `.plans/zeroshot-qc-m4/context-pack.md` and `plan.md`
acceptance criteria 1–3 (criterion 4 is the manual real-MVTec rerun, out of scope
for automated review). Every claim below was verified by a real run in this
session (full suite: 129 passed; eval files: 16 passed) or by a probe script
whose output is quoted.

Method: read `backend/app/eval/{dataset,metrics,run,fakes}.py`,
`backend/app/pipeline/{inspect,cache}.py`, both eval test files,
`backend/tests/fixtures/mvtec/fixture.py`, `docs/EVAL_NOTES.md`; ran the full
suite plus probes for AUROC edges, IoU union semantics, sampler stability,
fixture mask exactness, 3-mode schema/numbers, and empty-data exits.

## must-fix

None. Every correctness clause checked out against a real run (details in
"noted" with proof). No failing-now test is filed because there is nothing
that fails now and would pass with a fix.

## consider

1. `summarize([])` returns `auroc: 0.5` with `n: 0.0` rather than `None` —
   a neutral score for "no ranking measurable" is consistent with the
   single-class convention (`metrics.py:66`), but a zero-row summary could
   mislead. Unreachable via the CLI (`sample_dataset` raises `DatasetError`
   first; verified exit 2 below), so cosmetic only. No change required.
2. `_decode_union` (`metrics.py:99`) silently skips undecodable/misshapen
   RLEs, and `confusion` zips without a length check. Both are documented
   ("skipped, never raised on") and callers always pass aligned inputs;
   flagging only so M5 keeps the leniency deliberate.
3. `find_mask` (`dataset.py:69`) falls back to same-stem `<stem>.png`.
   Harmless on MVTec layout (masks are `<stem>_mask.png`), but a stray
   same-stem non-mask file would be read as a mask. Consider logging when
   the fallback hits.

## noted (verified, no action)

1. Sampler counts + seed determinism — OK. `sample_dataset(FIXTURE_ROOT,
   seed=0)` yields exactly 10 good + 20 defective per category (test
   `test_sampler_yields_exact_counts` passes); repeat calls with seed 7 are
   identical; probe: per-category sample is stable whether sampling all
   categories or `["gizmo"]` alone (`per-category stable: True 30`), and
   seed 7 vs 99 differ. RNG is per `(seed, category)` (`dataset.py:142`),
   so adding/removing categories cannot shift other categories.
2. Metric math — OK. Probe: `auroc` perfect 1.0 / inverted 0.0 / all-tied
   0.5 / single-class 0.5; `pixel_iou` union-of-halves 1.0 vs half-only 0.5
   (true union-vs-ground-truth, not best-match); `fail_score`
   FAIL→confidence / PASS→1−confidence (`metrics.py:15`); good images yield
   `iou None` and are excluded from the mean (probe: `good-ious-none: True`
   in all three modes; `mean_iou([1.0, None, 0.5]) == 0.75` in tests).
3. Mode wiring — OK. `sam_only` verdicts on post-`min_score` detections
   (`inspect.py:141` keeps `score >= profile.min_score`; scripted scores
   0.9/0.55 both pass, so the always-present 2×2 FP box forces FAIL —
   matches "FAIL on any detection above min_score"); judge modes share
   sampling/segmentation/cache and differ only in `reference`
   (`run.py:140-143`: `None` vs loaded image; `build_eval_profile` always
   sets `reference_image=None` so `sam_judge` cannot pick one up from disk).
   Wiring test asserts `judge.calls == 0` for `sam_only` and `> 0` for
   `sam_judge_ref` — passes, so the ordering is not numbers-only.
4. Ablation ordering + IoU sharing — OK, matches `EVAL_NOTES.md`. Real run
   (seed 0, scripted, 60 images): F1 0.800 / 0.889 / 1.000, AUROC
   0.500 / 0.900 / 1.000, IoU 0.858 identical across modes. IoU is shared
   because `run_inspection` returns the same `detections` list in judge
   modes (the judge only adds a verdict; `inspect.py:190`) — the code and
   the measured numbers agree.
5. `results.jsonl` / `summary.json` schema — OK. Record keys
   `category/image/label/defect_type/verdict/confidence/fail_score/
   n_detections/iou` (9 keys, all three modes); summary keys
   `run_id/mode/adapter/seed/categories/n_good/n_defective/rules/metrics`
   with `per_category{widget,gizmo}+overall`; 60 JSONL lines, all parse.
6. Empty-data behavior — OK. Missing root and unknown category both exit 2
   with `error: ...` guidance on stderr and no traceback (probe confirmed;
   `test_empty_data_errors_cleanly` passes). `data/runs` is gitignored;
   `git status --porcelain -- data/` is clean.
7. Fixture mask exactness — OK. Probe over all 40 scratch images: painted
   red pixels == mask pixels exactly (`mask exact: True`), all defects keep
   ≥4px margin (`margin>=4: True`), no mask touches the (0,0,2,2) FP box
   (`fp-disjoint: True`). Reference is first-sorted `train/good`
   (`000.png` both categories). Tiny-defect mechanism confirmed by design
   (4× 2×2 per category) and by the measured recall gap (0.8→1.0).

## dismissed

- "Scripted fakes separate modes by construction, could mask a real wiring
  bug" (plan.md risk): already mitigated in-repo — the wiring test counts
  per-mode judge invocations through the real `run_inspection` + cache,
  not just metric deltas. Verified passing; no further action.
- "`sam_only` always FAILs on the fixture, so its AUROC 0.5 is vacuous":
  expected — all fail_scores tie (confidence pinned 1.0), and the
  single-class/tied convention returns 0.5. Documents the no-judge floor
  correctly; not a bug.
