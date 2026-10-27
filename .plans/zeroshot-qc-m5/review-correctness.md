# Correctness review — feat/zeroshot-qc-m5

Scope: `.plans/zeroshot-qc-m5/context-pack.md` (cited below as CP) plus
`plan.md` acceptance criteria 1–4 (criterion 5 is manual/real-model, out of scope).
Method: full suite (`142 passed`, green) plus live probes against the branch code.
Every must-fix below was observed in a real run, not read from the diff.

## Must-fix

1. **Empty-diff rerun leaves a stale mask file that the synth loader then attaches.**
   `generate_pairs` sets `mask_path = None` on an empty diff but never deletes a
   `*_mask.png` already on disk (`backend/app/synth/generate.py:125-127`), while
   `load_synth_category` attaches any `*_mask.png` that `is_file`
   (`backend/app/eval/dataset.py:197-204`). Probe: `PaintOnly` generator then
   `Identity` generator into the same `out_root` → second call returns `None`
   but `bottle/scratch/000_mask.png` is still on disk, so eval scores a mask the
   generator run says does not exist. CP §"Do not re-derive" promises "omits the
   mask"; the return value omits it but the directory does not. Fix: `unlink`
   the stale `mask_path` (missing-ok) on the empty-diff path.
2. **`summary.json` reports sample counts that are false for `--data synth`.**
   `run_eval` echoes the requested `n_good`/`n_defective` into the summary
   (`backend/app/eval/run.py:200-201`), but the synth sampler ignores `n_good`
   and caps `n_defective` *per defect type* (`backend/app/eval/dataset.py:231-235`).
   Probe (2 defect types, `n_good=10, n_defective=3`): summary says `n_good: 10,
   n_defective: 3` while the 6 records are all `defective`. Any consumer reusing
   the existing sampler/metrics contract reads wrong metadata. Fix: write actual
   counts (e.g. count labels in `records`) when `source == "synth"`, or make the
   per-type cap match the MVTec total-cap semantics and document it.
3. **Exact-mask branch stores all-black (empty) masks instead of omitting them.**
   The `hasattr(generator, "add_defect_with_mask")` path
   (`backend/app/synth/generate.py:115-120`) saves whatever mask is returned with
   no emptiness check, while the diff path omits empty masks. Probe: stub generator
   returning `Image.new("L", size, 0)` → `*_mask.png` written with 0 non-zero
   pixels and returned as the pair's mask. Downstream `pixel_iou` returns `None`
   on empty truth, so the image silently drops out of mean IoU while claiming to
   have a mask. Fix: apply the same `mask.any()` gate to verbatim masks (omit +
   unlink, log), so both paths share one empty-mask rule.

## Consider

- **Whitespace-only `sop_text`/`category_name` passes request validation.**
  `SopDraftRequest` uses `Field(min_length=1)` with no stripping
  (`backend/app/main.py:14-16`); probe shows `"   "` validates, so a blank SOP
  reaches the model instead of 422. Consider `strip_whitespace=True` (or
  `min_length` on the stripped value). Not must-fix: no contract pins it, and the
  model round-trip still validates the draft.
- **`_validate_profile` clobbers a valid `name` when backfilling an empty `id`.**
  `backend/app/adapters/muse_spark.py:106-115` replaces both `id` and `name`
  with the slug/category when only `id` is empty, discarding a model-supplied
  name that already satisfied the template ("name must be the category verbatim"
  is unenforced by the schema). Consider filling only the empty field. Not
  must-fix: schemas allow it and the prompt already asks for verbatim names.
- **Synth `n_defective` is per defect type, MVTec's is a total.**
  Same code as must-fix 2 (`dataset.py:231-235` vs `sample_category`); even after
  the summary counts are fixed, `--n-defective 20` on 3 defect types samples up
  to 60 images where MVTec samples 20. Either reconcile or document in
  `docs/EVAL_NOTES.md`. Left to the author since the per-type choice may be
  deliberate.
- **`load_synth_category` loads `_`-prefixed defect dirs that
  `list_synth_categories` never lists** (`dataset.py:159` skips `_`-names;
  `dataset.py:191-193` does not). A `_quarantine/` folder is invisible to
  discovery but scored when its parent profile is named explicitly. Consider
  skipping non-file children consistently, or `_reference.png` explicitly.

## Noted (verified, no action)

- **Fake determinism + mask exactness: proven.** 30/30 sampled
  `add_defect_with_mask` outputs have verbatim mask pixels exactly equal to
  `diff_mask` pixels, and the suite's byte-identical-rerun test passes
  (acceptance criterion 1 holds in fake mode).
- **Diff fallback (threshold 25.0, non-empty painted shape) and empty-diff
  return-`None` + log: proven** by suite tests plus probes; only the on-disk
  staleness (must-fix 1) escapes the tested contract.
- **Eval `--data synth` reuses sampler/metrics/ablations end to end:**
  `sam_only`, `sam_judge`, `sam_judge_ref` all complete with `summary.json`
  (4 records, AUROC 0.5 single-class as CP states, IoU ≈ 0.96 on fake shapes).
- **`from-sop` 422 path, retry-once, draft-unsaved: covered by suite**
  (`test_sop.py`, 7 tests) and all pass. Unconfigured adapter surfacing as HTTP
  500 (`AdapterNotConfiguredError` uncaught in `profiles_from_sop`) is *not* a
  finding: no contract pins it, no sibling endpoint maps it differently, and 500
  for server misconfiguration is correct.
- **Relative `reference_image` resolution is consistent, not a bug:**
  `generate.py:65` resolves against `BACKEND_DIR.parent`, which equals
  `REPO_ROOT` in `config.py:13` — the same root `settings.data_dir` resolves
  against. (All current profiles set `reference_image: null`, so the fixture
  fallback is the live path.)
- **No `--threshold` CLI flag** for the diff threshold: deliberately out of
  scope (plan logs the threshold per image instead); the inability to tune it
  without code is a documented tradeoff, not a correctness defect.
- **Out of scope per CP/plan:** real-model quality (criterion 5, human steps),
  `muse_image.py` (unchanged by design), secrets/`data/` gitignore (suite green,
  `data/` untracked per `git status`).
