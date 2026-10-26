# Tests review — feat/zeroshot-qc-m2

Sources: [context-pack.md](.plans/zeroshot-qc-m2/context-pack.md) (acceptance criteria, "Do not re-derive" rules) and [plan.md](.plans/zeroshot-qc-m2/plan.md) § Test Strategies + § Edge Cases & Gotchas.
Suite status: `cd backend && .venv/bin/python -m pytest -q` → **81 passed** (24 in test_measure/test_inspect/test_smoke). Green is not coverage: the gaps below all pass silently today.

Covered well (no action): min_score boundary equality kept (`test_min_score_boundary_equality_is_kept`, plan edge-case table ✓); below-min_score drop; merge joins labels + keeps higher score with union-RLE check (AC2 ✓); low-IoU split in score order; size-mismatch + undecodable skip-with-warning; cache-hit identity; degenerate empty mask zeroes; text/bytes RLE decode; smoke count/verdict shape (AC3 ✓).

## Must-fix (4)

- **M1 — Zero CLI tests: AC1 and every CLI error path unpinned.** `grep -rn "cmd_inspect|cli.py|_format_mm" tests/` → no hits. Context-pack AC1 (`inspect --profile bottle --no-judge` prints px+mm lines, saves overlay) and the CLI contract (exit 1 + `error:` on stderr, no traceback, for unknown profile / bad image / unconfigured adapter) exist only as manual Verification. Proved live: `cli.py inspect … --profile no-such` exits 1 with `error: unknown profile…`, but nothing fails if that regresses. Add: happy-path (lines + `overlay:` + file saved), unknown profile, bad image, empty-detection exit-0, no-`Traceback` on each error.
- **M2 — IoU boundary equality (IoU == 0.5) untested; strict-`>` rule unpinned.** Tests cover 0.81/0.6 → merge and 0.25 → split only (`test_inspect.py` has no exact-0.5 case). Context-pack pins merge as strict `IoU > 0.5` (`inspect.py:21`); a `>=` regression would pass the suite. Proved: crafted masks with `_mask_iou == 0.5` return `> 0.5 → False` (stays split) with no test asserting it. Add: IoU-exactly-0.5 pair asserts two detections.
- **M3 — `mm_per_px=None` through `run_inspection` untested; 4 of 5 profiles ship null.** `grep mm_per_px tests/test_inspect.py` → one hit: the fixture hardcodes `0.1`. Only `bottle.json` sets `0.1`; screw/metal_nut/hazelnut/carpet are null, so the majority profile shape never runs. CLI `-` rendering (`_format_mm`) likewise untested. Proved: `run_inspection` with `mm_per_px=None` yields `area_mm2=None, length_mm=None` — correct, but asserted nowhere. Add: None-profile inspection asserts None mm fields; CLI line shows `-`.
- **M4 — Empty-overlay contract untested at overlay and CLI layers.** Only `run_inspection([]) → []` is pinned. `make_overlay(image, [])` returning the unmarked image (`overlay.py:24`) and the CLI "zero detections, still save overlay, exit 0" path (plan edge cases) have no tests: `grep` for empty-overlay → no hits. Proved: empty overlay returns pixel-identical image, asserted nowhere. Add: empty-list overlay identity test; CLI no-detection run asserts `no detections` + overlay saved + exit 0.

## Consider (6)

- **C1 — Score-tie label tiebreak untested.** Id order is score-desc with label tiebreak (`inspect.py:79`); tests only pin distinct-score order. Proved: equal-score crack/scratch orders `[d1 crack, d2 scratch]`, asserted nowhere. Add a tie test.
- **C2 — Same-label duplicate merge untested.** Code dedups (`if mask.label not in target["labels"]`), but only cross-label merge is tested. Proved: two identical `scratch` masks merge to label `'scratch'` (not `'scratch+scratch'`), asserted nowhere. Add a same-label merge test.
- **C3 — Overlay undecodable-RLE skip and merged-label fallback tint untested.** The single overlay test covers size-mismatch only; warn-and-skip on undecodable RLE and the `(255,200,0)` fallback for `a+b` labels (`overlay.py:15`) have no tests. Add both.
- **C4 — `load_profile` malformed-JSON / schema-validation path untested.** Only unknown-name `ValueError` is pinned; a corrupt profile JSON raises an unpinned raw error (no `error:`-shaped CLI assertion). Add: bad-JSON profile asserts clean CLI exit-1 (or pin the exception type).
- **C5 — Smoke real-measurement replacement unpinned.** M2 replaced placeholder `bbox=(0,0,0,0)`/`area_px=0` with `_masks_to_detections`; test_smoke asserts only count lines + verdict shape, which would pass with placeholder zeros. Add: smoke detections carry nonzero measured sizes (or unit-test `_masks_to_detections`).
- **C6 — Non-RGB image conversion untested.** `run_inspection` converts non-RGB (`inspect.py:83`); all fixtures are RGB. Add: grayscale/LA input runs and measures correctly.

## Noted (5)

- **N1 — No test is assertion-free, but two assert dependency behavior, not the SUT:** `test_encode_requires_fortran_order` asserts pycocotools raises on C-order arrays; `test_fake_segmenter_scores_never_drop_below_default_min_score` asserts FakeSegmenter scores, never calling `run_inspection`. Both document real constraints (see context-pack); keep, but they are not SUT coverage.
- **N2 — `test_inspect_image_loads_image_and_profile_from_disk` mutates global `PROFILES_DIR` via try/finally instead of the `monkeypatch` fixture.** Correct but non-idiomatic; a `monkeypatch.setattr` would be safer under parallel/failed-setup runs.
- **N3 — Plan text stale where tests are right:** plan Test Strategies says "100 px length asserts `length_mm == 10.0`", but tests assert `9.9` — correct per the point-span rule (context-pack "Do not re-derive"). Fix the plan line, not the tests.
- **N4 — Three-way / transitive merge (A≈B, B≈C, A≉C) untested.** Greedy grouping order-dependence is an accepted design; only flagging because a future refactor could flip grouping silently.
- **N5 — AC4 (no secrets; JSON-safe RLE text) partially pinned:** `isinstance(counts, str)` asserted on merge; the grep guard for model IDs/keys remains manual Verification per plan — no change requested.
