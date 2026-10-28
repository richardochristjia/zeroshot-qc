# ZeroShot QC — M2: Segmentation pipeline

Tier L (measured: 12 source files across 3 new pipeline modules, CLI, 5 profiles, tests; no sensitive paths, no auth). Loop and steps are in `tier.md` next to this file.

## Problem

M1 ends at raw `RawMask` lists plus throwaway smoke overlays with unlabeled tints. Nothing yet turns masks into measured, deduplicated, human-usable detections: no `area_px` / `length_px` / bbox (the schema fields the M3 judge will need), no cross-prompt duplicate merge, no overlay with the `d1, d2, ...` ids the judge prompt refers to, and no `inspect` command a user can run. Smoke's judge call still carries placeholder `bbox=(0, 0, 0, 0)`, `area_px=0` detections.

## Solution

Add three pipeline modules behind one orchestrator: `measure.py` decodes each RLE and derives `area_px`, `length_px` (longest side of `cv2.minAreaRect`), and bbox, plus mm conversion when `mm_per_px` is set; `pipeline/inspect.py` loads the image and `ProductProfile`, filters masks below `profile.min_score`, merges duplicates with IoU above 0.5 (keep the higher score, join labels), assigns stable `d1, d2, ...` ids, and measures each detection; `overlay.py` draws each mask semi-transparent with its id and label. Wire the orchestrator to repo-root `cli.py inspect` (`--no-judge` prints detections and saves the overlay; without it, M2 still stops after segmentation — the judge arrives in M3) and to `scripts/smoke.py`, whose tint code is replaced by `overlay.py` and whose placeholder detections become real measurements. Ship one JSON `ProductProfile` per ROADMAP risk-check category (`bottle`, `screw`, `metal_nut`, `hazelnut`, `carpet`) with placeholder rules and reference that M3/M5 refine.

## Phases

1. **Measure.** `measure.py`: RLE decode via pycocotools, `area_px` from the decoded mask, `length_px` as the longest side of `cv2.minAreaRect`, bbox as `(x, y, w, h)` ints, mm conversion (`area_mm2`, `length_mm`) only when `mm_per_px` is set, else `None`. Pure functions, no config or I/O.
2. **Inspect orchestrator.** `pipeline/inspect.py`: load image (RGB) + named profile, call `segmenter.segment(image, profile.defect_prompts)`, drop masks below `profile.min_score`, pairwise-IoU merge above 0.5, stable `d1...` ids in score order, `measure.py` per detection. Returns detections; no judge call in M2.
3. **Overlay.** `overlay.py`: one function mapping an image plus detections to a labeled overlay PNG (mask tint per prompt label reusing the smoke palette, id + label text). Smoke's local tint code is deleted and calls this instead; overlays gain ids/labels with no behavior change to caching or discovery.
4. **CLI + profiles.** Repo-root `cli.py` with `inspect <image> --profile NAME [--no-judge]` (root launch must work the way `scripts/smoke.py` already supports root launch via its `sys.path` bootstrap; `--no-judge` is accepted now and required to do anything judge-shaped later). Five profile JSONs in `backend/profiles/` loadable as `ProductProfile`; missing profile id is a clear error, exit non-zero, no traceback.
5. **Record.** Bootstrap `.agents/RECORD.md` (still missing — M1's write was correctly withheld on divergence) with the forge preamble verbatim plus the entries in Record Updates, verified against the built code.

## Acceptance Criteria

1. `python cli.py inspect <image> --profile bottle --no-judge` prints detections with px and mm sizes and saves the overlay. Check: CLI run in Verification.
2. Duplicate masks (IoU above 0.5 across prompts) merge into one detection with joined labels and the higher score. Check: `test_inspect.py`.
3. `pytest` is green and `scripts/smoke.py --fake` output keeps its shape (per-image count lines plus a verdict line; counts may shift with real measurement). Check: full suite plus smoke run.
4. No model ID, endpoint, or key appears anywhere in new source; RLE counts stay JSON-safe text through the cache path. Check: grep guard in Verification.
5. `manual:` run the CLI on 3 real MVTec images across the 5 categories and confirm sane boxes on visible defects. Human steps: download MVTec into `data/mvtec/`, set `.env` keys, run the CLI on one image per category.

## Dialectical Outcomes (Why)

- **Merge M1 first, branch M2 from main.** The user chose this over stacking M2 on the unreviewed M1 branch. M2 imports M1's adapters, cache, schemas, and smoke code directly, so a reviewed base beats a moving one; the cost was waiting for the M1 review, which is now merged.
- **CLI at repo root, not `backend/`.** The user chose HANDOFF-literal `python cli.py inspect ...` over M1's `cd backend` convention. Root launch already works (M1's smoke supports both), so the CLI reuses the same `sys.path` bootstrap rather than inventing a new one. Rejected: `backend/cli.py`, which would contradict the documented command every later doc and demo repeats.
- **`min_score` filtering in the orchestrator, not the adapters.** Adapters stay faithful to the protocol (return everything found); profile policy lives where the profile is loaded. This keeps fakes deterministic and the cache key honest.
- **Profiles with placeholder rules/reference.** M2 needs loadable profiles to run, but rules quality is M3's tuning loop and reference images need MVTec data. Shipping structural placeholders unblocks the CLI without pretending the content is final.
- **Smoke keeps its shape.** Replacing tint code with `overlay.py` changes pixels, not the contract (counts, overlays, one judge call). Rejected: rewriting smoke around the orchestrator in M2 — the orchestator returns detections, smoke needs masks plus a judge call, and forcing one shape would tangle both.

## Relevant Files (Where)

- `backend/app/pipeline/measure.py` — new; pure measurement functions.
- `backend/app/pipeline/inspect.py` — new; segmentation orchestrator.
- `backend/app/pipeline/overlay.py` — new; labeled overlay renderer.
- `cli.py` — new at repo root; `inspect` subcommand.
- `backend/profiles/bottle.json`, `screw.json`, `metal_nut.json`, `hazelnut.json`, `carpet.json` — new; one `ProductProfile` JSON each.
- `backend/scripts/smoke.py` — change: delete local tint code, call `overlay.py`; placeholder detections become `measure.py` output.
- `backend/tests/test_measure.py`, `backend/tests/test_inspect.py` — new; see Test Strategies.
- `.agents/RECORD.md` — new; bootstrap plus entries.

## Key Code Context (What)

M2 consumes M1's contracts unchanged. The adapter protocols in `backend/app/adapters/base.py` (`Segmenter.segment(image, prompts) -> list[RawMask]`, shared `require_configured` / `encode_image_b64` helpers after the M1 deslop), the cache wrappers in `backend/app/pipeline/cache.py` (`CachedSegmenter`, `CachedJudge`, `DiskCache` rooted at `Path(settings.data_dir) / "cache"`), the §6 schemas in `backend/app/schemas.py` (`RawMask` with COCO RLE dict; `Detection` with `id`, `label`, `score`, `bbox: tuple[int,int,int,int]`, `area_px`, `length_px`, optional mm fields; `ProductProfile` with `defect_prompts`, `rules`, `mm_per_px`, `min_score=0.3`), and smoke's wiring (`build_adapters(fake)`, `SMOKE_PROMPTS = ["scratch", "crack", "dent"]`, image discovery, `data/runs/smoke/` output). Fake RLE counts are JSON-safe text of COCO compressed RLE that pycocotools accepts (proven by the M1 blast-radius check); real-SAM RLE byte-vs-text form stays an open M1 risk.

## Implementation Algorithm (How)

1. **Measure one mask.** Decode RLE with pycocotools to a binary array; `area_px` is the pixel count; contours give `cv2.minAreaRect`, whose longer side is `length_px`; bbox is the bounding `(x, y, w, h)` as ints. If `mm_per_px` is set, `length_mm = length_px * mm_per_px` and `area_mm2 = area_px * mm_per_px^2`; else both stay `None`.
2. **Orchestrate.** Load image as RGB; load the named profile JSON and validate as `ProductProfile`. `segmenter.segment(image, profile.defect_prompts)`; drop masks with `score < profile.min_score`. Compute pairwise mask IoU (via decoded binary masks); greedily merge pairs above 0.5, keeping the higher score and joining distinct labels. Sort by score descending, assign `d1, d2, ...`, measure each.
3. **Render.** For each detection, decode its RLE, tint the region with the per-label palette color at partial alpha, and stamp `id` plus label text near the bbox origin. Return a PIL image; the caller saves it.
4. **CLI.** `argparse` with `inspect <image> --profile NAME [--no-judge]`; resolve the profile from `backend/profiles/` relative to the CLI file (CWD-independent); build fake-or-real cached adapters the way smoke does; run the orchestrator; print one line per detection (id, labels, score, px and mm sizes) plus the overlay path.
5. **Profiles.** Each JSON carries `id`, `name`, `defect_prompts` (category-sensible starting prompts), `rules` (placeholder text marked for M3), `mm_per_px` (present only where a scale is assumed — else null), `min_score` default, `reference_image` null until MVTec data lands.

## Anti-Goals (Out of Scope)

- The judge call, rule override, retry/consistency logic (M3). `cli.py` accepts `--no-judge` but performs no judging.
- Eval harness, metrics, ablations (M4). Synthetic generation and SOP import (M5) beyond the existing protocol stubs.
- FastAPI `POST /api/inspect` (M6 backend work); M2's orchestrator is importable by design but no router is added.
- Training or fine-tuning anything (forbidden by HANDOFF §2). Guessing Meta API details. Changing M1's adapter, cache, or schema contracts — M2 consumes them as-is.

## Edge Cases & Gotchas

- **Empty mask list.** No detections is a valid result: print zero detections, still save the (unmarked) overlay, exit 0.
- **RLE / image size mismatch.** A mask whose decoded shape differs from the image is skipped with a warning, not a crash (M1 security review proved an unchecked copy crashes the consumer).
- **Duplicate file stems.** Overlay filenames must stay one-per-image (M1 correctness finding); derive names that cannot collide for distinct inputs.
- **Root vs backend CWD.** Both `python cli.py ...` from root and `cd backend` runs must resolve profiles, `.env`, and data dirs identically (M1 made config CWD-independent; keep it so).
- **JSON-safe RLE.** Merged detections re-emit RLE through the cache path; counts must remain the text form pycocotools accepts (M1 impact check).
- **`min_score` boundary.** `score < min_score` drops; equality keeps. Deterministic id order: score descending, label as tiebreak.

## Navigation Anchors

- Entry point: `cli.py` `main()` (argparse, repo root).
- Orchestrator: `backend/app/pipeline/inspect.py` — the single segment → filter → merge → measure → return flow; M3's judge and M6's router both call here.
- Swap point: profile loading (name → `backend/profiles/<name>.json` → `ProductProfile`) — M5's SOP import and M6's profile editor target this mapping.
- Choke point: `measure.py` pure functions — every size number in every later surface comes from here.

## Dependency Mappings

- No new third-party dependencies: `numpy`, `opencv-python-headless`, `Pillow`, `pycocotools` are already pinned in `backend/requirements.txt`. `argparse` is stdlib.
- Internal: `inspect.py` depends on `adapters/base.py` (protocols), `pipeline/cache.py` (only via the caller's wired adapters — the orchestrator takes a `Segmenter`, never constructs one), `schemas.py`, `config.py` (settings for data-dir resolution in CLI/smoke, not in `measure.py`).

## Test Strategies

- `test_measure.py`: synthetic rectangle mask of known size asserts exact `area_px` / `length_px` / bbox; `mm_per_px=0.1` with 100 px length asserts `length_mm == 10.0` and scaled `area_mm2`; `mm_per_px=None` asserts both mm fields are `None`; degenerate (empty) mask asserts zero sizes without raising.
- `test_inspect.py`: two overlapping fake masks (IoU ~0.8, different labels) assert one merged detection with joined labels and the higher score; IoU ~0.2 pair asserts `d1`, `d2` in score order; below-`min_score` mask asserts absence; boundary equality asserts kept; empty mask list asserts zero detections and exit-0-shaped result; size-mismatched RLE asserts skip-with-warning, no exception; cache-hit rerun asserts identical detections with the inner adapter uncalled.
- CLI/smoke (Verification, not unit tests): `python cli.py inspect <img> --profile bottle --no-judge` prints detection lines plus overlay path; `scripts/smoke.py --fake` keeps its count/verdict line shape; grep guard rerun for secrets.
- Run command: `cd backend && .venv/bin/python -m pytest -q` (project venv, per M1 risks — never the host global interpreter).

## Record Updates

Bootstrap `.agents/RECORD.md` with the forge `record-preamble.md` copied verbatim as its body, followed by (includes the M1 entries whose corrected form was approved with this plan):

```markdown
- (pipeline) Inspection currently routes segment and judge model calls through a disk cache keyed by a hash of their inputs.
- (adapters) Model access currently goes through Segmenter, Judge, and ImageGenerator protocols with fake implementations for tests.
- (config) Model IDs are currently read from environment configuration and never hardcoded.
- (data) The data directory currently holds datasets, cache, and run outputs and is excluded from version control.
- (pipeline) Segmentation currently filters detections by profile min_score and merges duplicates with IoU above 0.5.
- (pipeline) Detection sizes are currently measured in pixels and converted to millimetres when the profile sets mm_per_px.
```
