# Falsify rulings — M2 (`feat/zeroshot-qc-m2`)

Scope: all 10 must-fix findings in `review-correctness.md` (1), `review-security.md` (2),
`review-structure.md` (3), `review-tests.md` (4). `review-impact.md` lists no must-fix
findings (risks only), so nothing to rule there. All probes: `/tmp/falsify_m2_probe.py`
run with `backend/.venv/bin/python`, plus `grep` over `backend/tests/` and the diff.
Read-only: no source was changed.

## Rulings (worst harm first)

- fix: unbounded RLE decode allows memory-exhaustion DoS (review-security M2). Reproduced: `decode_rle({'size':[8000,8000],...})` decoded a 64 MB array with no complaint, scales linearly to OOM-kill; both call sites (`inspect.py:58`, `overlay.py:24`) know image dims yet check shape only after decoding. Hits CLI/smoke/any future server via real-SAM response, cache file, or crafted `mask_rle`.
- fix: `load_profile` path traversal reads arbitrary local JSON (review-security M1). Reproduced: `load_profile('/tmp/evil333')` and `load_profile('../../../../../../../tmp/evil333')` both LOADED an outside file. Hits any caller passing an untrusted `--profile` (M6 profile editor targets this mapping per plan anchors); plausible attacker path, trivial allowlist fix.
- fix: zero-area masks emitted as `(0,0,0,0)` detections (review-correctness MF1). Reproduced: one all-zero mask → `d1 bbox=(0,0,0,0) area=0`; `IoU(empty,real)=0.0` so it never merges away. Hits any run where SAM returns an all-zero mask (adapter validates shape, not area); reintroduces the placeholder the plan says M2 eliminates, stamps a bogus label at the origin, pollutes M3 judge input.
- fix: `cli.build_segmenter` duplicates smoke's segmenter wiring (review-structure 1). Proven by code read (`cli.py:31-36` vs `smoke.py:39-52`): same cache root, same `"fake-sam"` id, docstring admits "Mirror". Zero current harm (impact review verified shared-not-forked), but a one-sided M3 edit silently splits/poisons the disk cache (wrong state, worst harm class); fix is a behavior-preserving move with the full suite as tripwire, and M3 touches this exact seam next.
- fix: zero CLI tests, AC1 and error contract unpinned (review-tests M1). Proven: `grep cmd_inspect|cli.py tests/` → no hits; live `--profile no-such` exits 1 correctly but nothing fails if it regresses — and the merge checklist (pytest + smoke) never runs the CLI, so no tripwire exists anywhere. Plan said "Verification, not unit tests", but that was scope convenience, not a debated rejection, and AC1 is the top user-facing contract.
- fix: `mm_per_px=None` through `run_inspection` untested, 4 of 5 profiles ship null (review-tests M3). Proven: only `mm_per_px` hit in `test_inspect.py` is the `0.1` fixture; live `None` run yields `None` mm fields, asserted nowhere. A `None`-arithmetic regression breaks the majority profile shape; one test pins it.
- fix: IoU-exactly-0.5 split untested, strict-`>` rule unpinned (review-tests M2). Proven: tests cover 0.81/0.6/0.25 only; live 0.5-IoU pair stays split (2 detections), asserted nowhere. A `>=` regression silently changes merge behavior pinned by the context pack; one test pins it.
- fix: empty-overlay contract untested at overlay layer (review-tests M4). Proven: only `run_inspection([])` pinned; `make_overlay(image, [])` returns a pixel-identical image (verified), asserted nowhere. One identity test pins the context-pack contract (CLI half folds into the M1 CLI tests above).
- leave open: `inspect_image` dead in production, CLI hand-rolls the same path (review-structure 3). Proven: repo-wide grep shows the only caller is `test_inspect.py:255`. Real duplication, but zero current harm and both fixes force a semantic choice (canonical error semantics vs deleting the entry M6's router would import); cheapest to resolve when the second consumer lands.
- dismiss: smoke `_masks_to_detections` bypasses `run_inspection` (review-structure 2). Divergence reproduced (two 0.05/0.04 identical masks: smoke keeps both, `run_inspection` → `[]`), but the demanded fix was explicitly debated and rejected in the user-approved plan ("Rejected: rewriting smoke around the orchestrator in M2", Dialectical Outcomes), no production consumer reads smoke detections (`FakeJudge` is order-insensitive), and M3's judge consumes the orchestrator path, not smoke.

Diff-guard audit: every guard in the M2 diff (warn-and-skip on undecodable/size-mismatched RLE in orchestrator, overlay, smoke) has a reproduction in the suite or a probe run — no unearned defensive checks, so no `cut` findings of my own.

## For the fixer

- fix: skip zero-area masks with `warnings.warn` in `_decode_valid_masks` (+ same in smoke); proves via new `test_zero_area_mask_is_skipped` (fails now with the extra `d1 (0,0,0,0)`, passes with fix).
- fix: allowlist profile names (`[A-Za-z0-9_]+`) or `resolve()` + `is_relative_to` guard in `load_profile`; proves via new test asserting `load_profile('../x')` and absolute paths raise.
- fix: pre-validate RLE `size` against known image dims before `mask_api.decode` at both call sites (and/or pixel cap in `decode_rle`); proves via new test with mismatched-giant `size` asserting skip without a large allocation.
- fix: one shared segmenter builder used by `cli.py` and `smoke.py`; no new test — proves via unchanged suite (81 passed) + smoke shape + shared `"fake-sam"` entries.
- fix: CLI tests — happy path (lines + `overlay:` + file saved), unknown profile, bad image, empty-detection exit-0, no-`Traceback` on each error; the tests are the fix (each fails if its path regresses).
- fix: `mm_per_px=None` inspection test asserting `None` mm fields (CLI `-` rendering covered by CLI tests above).
- fix: IoU-exactly-0.5 pair test asserting two detections.
- fix: empty-list overlay identity test asserting pixel-identical output.

## For the user

None — no finding needs a new rule or special case.

## For the PR's open findings

- `inspect_image` duplicates the CLI's disk-loading path with no production caller; unify (route CLI through it or delete it) when M3/M6 lands the second consumer.

## Dismissed

- Smoke bypassing `run_inspection`: user already rejected this exact fix in the approved plan; no production consumer hits smoke detections.

## Fix outcome

All 8 fix items implemented, no new rules/settings/flags; leave-open and
dismissed items untouched.

- Zero-area skip: `_decode_valid_masks` and smoke `_masks_to_detections`
  warn-and-skip empty masks (`test_zero_area_mask_is_skipped`,
  `test_masks_to_detections_skips_zero_area_mask`).
- `load_profile` allowlist `[A-Za-z0-9_-]+` (hyphen included so names like
  `no-such-profile` keep the existing unknown-profile path);
  `test_load_profile_rejects_traversal_and_absolute_paths` loads a real
  outside file pre-fix.
- RLE pre-validation: declared `size` checked against image dims in
  `_decode_valid_masks` and `make_overlay` (warn text keeps the `skipping
  RLE` prefix), plus a 100 MP `MAX_RLE_PIXELS` cap in `decode_rle` as the
  dims-unknown backstop; 3 spy tests assert decode is never reached.
- Shared `app/pipeline/wiring.py::build_segmenter` used by `cli.py` and
  `smoke.build_adapters` (shared cache instance preserved); `fake-sam`
  now has one home. No new test per ruling.
- `backend/tests/test_cli.py` (4 tests): screw happy path incl. `-` mm
  rendering, unknown profile, bad image, empty-detection exit-0, no
  `Traceback` on every path.
- `test_none_mm_per_px_yields_none_mm_fields`,
  `test_iou_exactly_half_pair_stays_split` (premise `_mask_iou == 0.5`
  asserted), `test_make_overlay_empty_list_returns_unmarked_image`.
- Discrimination check: the 6 guard tests fail on pre-fix sources, the 7
  pinning tests pass either way. Suite: 94 passed. Smoke `--fake` shape
  (3 count lines + verdict) and a real CLI `--fake` run verified.
