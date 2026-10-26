# Context pack

BASE: main
CHANGED: 14 files, +828/-51

## What this change does

M2 turns raw `RawMask` lists into measured, deduplicated `Detection`s: pure RLE
measurement, a segment → filter → merge → measure orchestrator, a labeled overlay
renderer, a repo-root `inspect` CLI, and five loadable `ProductProfile` JSONs.
Smoke's local tint code and placeholder `bbox=(0,0,0,0)` detections are replaced
by the new modules; no judge call is added (M3).

## Files

- `backend/app/pipeline/measure.py` — pure measurement; `decode_rle`/`measure_mask` (`measure.py:12`, `measure.py:24`).
- `backend/app/pipeline/inspect.py` — orchestrator; `load_profile`/`run_inspection`/`inspect_image` (`inspect.py:26`, `inspect.py:79`, `inspect.py:127`).
- `backend/app/pipeline/overlay.py` — labeled overlay; `make_overlay` (`overlay.py:24`), palette (`overlay.py:15`).
- `cli.py` — repo-root CLI; `inspect` subcommand via `cmd_inspect` (`cli.py:52`).
- `backend/profiles/bottle.json` — profile data; only profile with `mm_per_px=0.1`.
- `backend/profiles/screw.json` — profile data; `mm_per_px` null.
- `backend/profiles/metal_nut.json` — profile data; `mm_per_px` null.
- `backend/profiles/hazelnut.json` — profile data; `mm_per_px` null.
- `backend/profiles/carpet.json` — profile data; `mm_per_px` null.
- `backend/scripts/smoke.py` — changed: deleted local tint/`_decode_mask`, added `_masks_to_detections` (`smoke.py:104`), calls `make_overlay`.
- `backend/tests/test_measure.py` — new; 7 tests for `measure_mask`/`decode_rle`.
- `backend/tests/test_inspect.py` — new; 12 tests for merge/order/filter/skips/cache.
- `backend/tests/test_smoke.py` — changed: overlay test repointed at `make_overlay` with `Detection` input.
- `.agents/RECORD.md` — new; forge preamble plus 6 approved entries (M1+M2).

## API contracts

No HTTP endpoints in M2. Internal contracts only:

- CLI: `python cli.py inspect <image> --profile NAME [--no-judge] [--fake]` → stdout detection lines + `overlay: <path>`; exit 1 with `error:` on stderr (no traceback) for unknown profile, bad image, missing keys. Declared in `cli.py:52`.
- `Segmenter.segment(image, prompts) -> list[RawMask]` — unchanged M1 protocol, declared in `backend/app/adapters/base.py:37`.
- `run_inspection(image, profile, segmenter) -> list[Detection]` — score-ordered `d1...` detections. Declared in `backend/app/pipeline/inspect.py:79`.
- `measure_mask(mask_rle, mm_per_px) -> {area_px, length_px, bbox, area_mm2, length_mm}` — bbox `(x, y, w, h)` ints. Declared in `backend/app/pipeline/measure.py:24`.
- `make_overlay(image, detections) -> Image` — caller saves; empty list returns unmarked image. Declared in `backend/app/pipeline/overlay.py:24`.
- `load_profile(name)` reads `backend/profiles/<name>.json`, raises `ValueError` on unknown name. Declared in `backend/app/pipeline/inspect.py:26`.
- Shapes: `RawMask` in `backend/app/schemas.py:8`; `Detection` in `backend/app/schemas.py:14`; `ProductProfile` (`min_score=0.3` default) in `backend/app/schemas.py:26`.

## Test entry points

- `backend/tests/test_measure.py` — `cd backend && .venv/bin/python -m pytest tests/test_measure.py -q`
- `backend/tests/test_inspect.py` — `cd backend && .venv/bin/python -m pytest tests/test_inspect.py -q`
- `backend/tests/test_smoke.py` — `cd backend && .venv/bin/python -m pytest tests/test_smoke.py -q`
- Full suite + smoke shape: `cd backend && .venv/bin/python -m pytest -q` and `backend/.venv/bin/python backend/scripts/smoke.py --fake` (from root; expect 3 count lines + 1 `verdict:` line + 3 overlays)

## Acceptance criteria

1. `python cli.py inspect <image> --profile bottle --no-judge` prints detections with px and mm sizes and saves the overlay. Check: CLI run in Verification.
2. Duplicate masks (IoU above 0.5 across prompts) merge into one detection with joined labels and the higher score. Check: `test_inspect.py`.
3. `pytest` is green and `scripts/smoke.py --fake` output keeps its shape (per-image count lines plus a verdict line; counts may shift with real measurement). Check: full suite plus smoke run.
4. No model ID, endpoint, or key appears anywhere in new source; RLE counts stay JSON-safe text through the cache path. Check: grep guard in Verification.
5. manual: run the CLI on 3 real MVTec images across the 5 categories and confirm sane boxes on visible defects. Human steps: download MVTec into `data/mvtec/`, set `.env` keys, run the CLI on one image per category.

## Do not re-derive

- Merge rule is strict `IoU > 0.5` (`inspect.py:21`); `score >= min_score` keeps, equality included (`inspect.py:79`).
- `length_px` is the longer side of `cv2.minAreaRect` — a point-span measure, so a filled 100x50 rect gives `99.0`, and `length_mm` `9.9` at `mm_per_px=0.1`, not `10.0` (`measure.py:24`).
- mm fields are `None` unless `mm_per_px` is set; only `bottle.json` sets it (`0.1`), the other four profiles yield `-` in CLI output (`measure.py:24`, `cli.py:39`).
- Merged labels join with `+` (`scratch+crack`) and hit the `(255, 200, 0)` fallback tint because lookup is on the full label string (`overlay.py:15`, `overlay.py:24`).
- RLE `counts` stay JSON-safe text; both text and bytes decode (`measure.py:12`); re-encode requires Fortran-order arrays, C-order raises `ValueError` (`inspect.py:48`).
- Size-mismatched or undecodable RLE is warn-and-skip (`warnings.warn`), never a crash, in both orchestrator and overlay (`inspect.py:58`, `overlay.py:24`).
- Id order is score descending with label tiebreak (`inspect.py:79`); empty masks → zero detections, overlay still saved, exit 0 (`cli.py:52`).
- Smoke keeps its contract: per-image `{stem}: scratch=N, crack=N, dent=N` count lines, one `verdict:` line, `seen_stems` naming, cache/discovery untouched (`smoke.py:134`).
- Tests use a `StubSegmenter`, not `FakeSegmenter`, because fake scores (0.55–0.95) never drop below default `min_score` 0.3 (`test_inspect.py`, drop-path rationale test included).
- M1 contracts consumed unchanged: adapter protocols, `CachedSegmenter`/`DiskCache`, §6 schemas; the M1 open risk on real-SAM RLE byte-vs-text form carries over.

## Diff

Full diff (+828/-51) exceeds the pack budget, so it is split by file group —
run `git diff main...HEAD -- <group>` from the repo root for each:

```sh
# Group 1 — pipeline source (measure/inspect/overlay), the core change
git diff main...HEAD -- backend/app/pipeline/
# Group 2 — CLI + smoke rewrite
git diff main...HEAD -- cli.py backend/scripts/smoke.py
# Group 3 — profiles (5 single-line JSONs) + record bootstrap
git diff main...HEAD -- backend/profiles/ .agents/RECORD.md
# Group 4 — tests (test_measure/test_inspect new, test_smoke repointed)
git diff main...HEAD -- backend/tests/
```
