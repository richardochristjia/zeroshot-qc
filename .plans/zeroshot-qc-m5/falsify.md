# Falsify — feat/zeroshot-qc-m5 (correctness review must-fixes)

Method: each finding reproduced with a real run against branch code (`backend/`, python3.11). Read-only; no code edited.

## Rulings (worst harm first)

fix: empty-diff rerun leaves a stale mask the synth loader then attaches (reviewer). why: reproduced — `PaintOnly` then `Identity` into the same out_root: second call returns `None` yet `000_mask.png` stays on disk and `load_synth_category` attaches it; a wrong mask scored against a new image.
fix: exact-mask branch stores all-black masks instead of omitting them (reviewer). why: reproduced — stub `add_defect_with_mask` returning `Image.new("L", size, 0)` is saved (0 non-zero pixels) and returned as the pair mask; downstream `pixel_iou` returns `None` on empty truth so the image silently drops from mean IoU while claiming a mask.
fix: `summary.json` sample counts false for `--data synth` (reviewer). why: reproduced — 2 defect types × 3 images with `n_good=10, n_defective=3` samples 6 all-`defective` records while `run_eval` echoes the requested `n_good`/`n_defective` into the summary; any summary consumer reads wrong metadata (records themselves are right).

## Detail

1. **Stale mask (generate.py:125-127 × dataset.py:197-204).** Who hits it: anyone regenerating into the same `--synth-dir` when a later run yields an empty diff (different seed/generator, or the real image model returning a near-identical image) — the normal rerun workflow. Harm: wrong state — a prior run's mask is scored against a different image's pixels, corrupting IoU. Cheapest: `unlink` stale `mask_path` (missing-ok) on the empty-diff path. Test: paint-then-identity rerun → mask file gone and loader `mask_path is None` (fails now, passes with fix). Not a defensive check: reproduced with harm worse than a recoverable message.
2. **All-black exact mask (generate.py:115-120).** Who hits it: any `add_defect_with_mask` generator returning an empty mask — plausible from the real Muse Image adapter (no visible defect). Harm: wrong state — phantom mask plus silent metric dropout. Cheapest: apply the existing `mask.any()` gate to the verbatim path (omit + unlink, log), reusing the sibling rule — no new rule or setting. Test: black-mask stub → no file written, pair mask `None` (fails now, passes with fix).
3. **False summary counts (run.py:200-201 × dataset.py:231-235, 252).** Who hits it: every `--data synth` eval consumer reading `summary.json` (the runner reuses the sampler/metrics contract across sources). Harm: wrong message the caller can recover from (count `results.jsonl` labels instead) — mildest of the three, but the fix is a two-line actual-count write, cheaper than documenting around it. Test: synth eval with `n_good=10, n_defective=3` over 2 defect types → summary counts equal label counts in records (fails now, passes with fix). The deeper per-type-vs-total `n_defective` semantic split stays with the author (review's Consider item) — out of falsify scope.

## For the fixer

- fix: unlink stale mask on the empty-diff path (`generate.py`).
- fix: gate the exact-mask path with the same `mask.any()` rule (`generate.py`).
- fix: write actual label counts into `summary.json` for `source == "synth"` (`run.py`).

## For the user

- None. No ruling needs a new rule, branch, or setting.

## For the PR's open findings

- None. All three must-fixes earned their fix; nothing deferred.

## Fix outcome

- All three fixed, no new rules/settings/flags; nothing held back as needs-call.
- `generate.py`: empty-diff path unlinks the stale `mask_path` (missing-ok); exact-mask path gated by the same `mask.any()` rule (omit + unlink + log).
- `run.py`: `source == "synth"` writes actual record label counts into `summary.json`.
- Each fix has a test that fails without it (verified via stash) and passes with it: `test_rerun_empty_diff_removes_stale_mask`, `test_all_black_exact_mask_omitted_and_unlinked` (`test_synth.py`), `test_synth_summary_counts_match_record_labels` (`test_eval_run.py`).
- Full suite: 145 passed.

## Dismissed

- None. All three reproduced and traced to real callers.
