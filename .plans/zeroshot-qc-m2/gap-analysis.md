# Gap analysis — M2: Segmentation pipeline (`feat/zeroshot-qc-m2`)

Branch diff vs `main`: measure/inspect/overlay/wiring modules, repo-root `cli.py`,
5 profiles, smoke rewire, `test_measure.py`/`test_inspect.py`/`test_cli.py`,
smoke-test updates, `.agents/RECORD.md` bootstrap. Suite: 95 passed after the
one fix below (was 94).

## Acceptance-criteria table

| ID | Criterion | Met? | Evidence |
|---|---|---|---|
| AC1 | `python cli.py inspect <image> --profile bottle --no-judge` prints detections with px and mm sizes and saves the overlay | Yes | Live run: `d1 chip on bottle score=0.88 area_px=243 … area_mm2=2.43 length_mm=2.60` + `overlay: …/data/runs/cli/probe_overlay.png`, exit 0; also from `/tmp` CWD (CWD-independent). `test_cli.py::test_inspect_fake_happy_path_prints_lines_and_saves_overlay` |
| AC2 | Duplicates (IoU > 0.5) merge: joined labels, higher score | Yes | `inspect.py:105` strict `> 0.5`, `inspect.py:112-114` join-labels/max-score; `test_merge_overlapping_masks_joins_labels_and_keeps_higher_score`, `test_merged_detection_carries_union_mask_rle`, `test_iou_exactly_half_pair_stays_split` |
| AC3 | `pytest` green; `smoke.py --fake` keeps shape (count lines + verdict) | Yes | `cd backend && .venv/bin/python -m pytest -q` → 95 passed; live smoke → exactly 3 `{stem}: scratch=N, crack=N, dent=N` lines + 1 `verdict:` line |
| AC4 | No model ID/endpoint/key in new source; RLE counts stay JSON-safe text through cache | Yes | Grep guards: (a) only `config.py:29` CORS default; (b)(c) no hits; (d) only `test_inspect.py` `MODEL_ID = "sam-model-under-test"` — M1-precedent fake cache label (`test_cache.py:19`), not a real ID. Cache spot-check: 23 JSON files, zero non-string `counts`; `inspect.py:56-63` text re-encode |
| AC5 | Manual: CLI on 3 real MVTec images, sane boxes | Can't tell | Needs MVTec download + `.env` keys + human eyes; `tasks.md` manual item still unchecked. Settles with the human run. |
| F1 | Smoke fallback discovery ignores generated run outputs | Fixed (was Partly) | Pre-fix live run consumed `data/runs/cli/m2_probe_overlay.png` as input and wrote stacked `probe_overlay_overlay.png`. Fix: `smoke.py` excludes `runs/cli/` + `test_fallback_discovery_ignores_cli_overlays` (fails pre-fix, passes now) |
| F2 | CLI overlay naming one-per-image for distinct same-stem inputs | Partly | `cli.py:69` `{stem}_overlay.png` overwrites across runs for same-stem distinct images; smoke has `seen_stems`, CLI has none. Minor (single-shot runs); naming scheme is a product call → Needs-call, not fixed |

Edge-case spot-checks (all hold): empty masks → `no detections` + unmarked overlay, exit 0
(`test_inspect_empty_detections_exits_zero_with_unmarked_overlay`); size-mismatched /
undecodable RLE → warn-and-skip, never decode giants (`decode_rle_for_image`,
4 spy/skip tests); `min_score` equality kept (`inspect.py:97`); score-desc + label
tiebreak ids (`inspect.py:99,116`); profiles load via module-anchored `PROFILES_DIR`
with traversal allowlist; `--no-judge` absent → identical output + one stderr note.

## Record reconciliation

`.agents/RECORD.md`: forge preamble verified byte-identical to
`record-preamble.md` (diff clean); all 6 plan entries present verbatim
(`RECORD.md:44-49` vs `plan.md:100-105`, diff clean). Each holds against the code:
cache routing (`wiring.py`, `CachedSegmenter`), protocols+fakes (`adapters/`),
env-only model IDs (AC4 greps), `data/` gitignored (`.gitignore:2`,
`git check-ignore` confirms), min_score filter + IoU>0.5 merge (`inspect.py:97,105`),
px sizes + conditional mm (`measure.py:109-114`). No divergence, no stale entries.
No new entry proposed: the CLI entry point is single-file discoverable (`cli.py`),
and nothing else established a new high-level fact.

## Gaps

- F1 (fixed): M2's new `data/runs/cli/` outputs fed back into smoke fallback
  discovery, stacking overlays. Fixed by excluding `runs/cli/` in
  `discover_image_paths` with a discriminating regression test.
- F2 (Needs-call): CLI same-stem overlay overwrite across runs; needs a naming
  decision (hash suffix? `seen_stems`-style counter?); existing test pins the
  current name, so not changed unilaterally.

## Next

1. Human: AC5 manual MVTec run (3 images, `.env` keys).
2. Human: rule on F2 CLI overlay naming (or accept overwrite).
3. Merge after AC5; carry the falsify leave-open (`inspect_image`/CLI path
   unification when M3/M6 lands a second consumer) as known debt.
