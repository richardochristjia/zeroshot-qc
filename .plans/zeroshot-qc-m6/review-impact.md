# Blast radius: feat/zeroshot-qc-m6 vs main

## What it does
Four real FastAPI routers replace one-line stubs (`inspect`, `profiles`, `eval`, `synth`), plus a new `GET /files/{path}` in `backend/app/main.py:42-66` and a new `frontend/` tree whose only backend choke point is `frontend/src/api.ts`. Two structural moves: `POST /api/profiles/from-sop` relocated from `main.py` to `routers/profiles.py` (path kept), and a new atomic `save_profile` in `backend/app/pipeline/inspect.py:138-157`. One divergence: new read-only `GET /api/synth/gallery` (`backend/app/routers/synth.py:39-80`) because no list endpoint existed.

## The one fact it's safe because of
**The routers only call shared pipeline/synth code; they don't change it.** `git diff main...HEAD` touches nothing under `backend/app/pipeline/`, `eval/`, `synth/`, `adapters/`, `schemas.py`, CLI, or config — all behavior changes are new router/frontend files. So CLI parity, cache semantics, and schema contracts hold by construction, not by review.
Step reached: **(4) ran it** — full suite green plus a live probe (below).

Proof (this session):
- `cd backend && .venv/bin/python -m pytest -q` → **157 passed** (includes CLI-parity, judge-only cache-hit, 422/404, traversal, gallery-grouping tests in `backend/tests/test_routers.py`).
- Live TestClient probe: `GET /files/../x`, `/etc/passwd`, `..\x`, `.` → all 404; `GET /api/synth/gallery` → 200 list (11 items against dev `data/`). Files-guard + read-only gallery confirmed against the real app.

## Risks (kept)
1. **PUT overwrite vs page-side save-as-new confirm** (`routers/profiles.py:61-79`, `pipeline/inspect.py:138`). `save_profile` uses `os.replace` and overwrites silently; the "don't clobber" check lives only in `Profiles.tsx` (existence check before PUT). A direct `PUT /api/profiles/{existing}` with a new body destroys the old profile. Likelihood: low (only hand-crafted API calls bypass the page); cost: medium (profile JSON lost, no backup). Check: `curl -X PUT` twice with different bodies, diff the file.
2. **Frontend assumes overlay `bbox` is in original-image pixels** (context-pack item 69; `Inspect.tsx` scales to rendered size). If any future segmenter returns normalized boxes, overlays silently misplace with no error. Likelihood: low (current segmenters return pixels); cost: medium (visual only). Check: the CLI-parity test pins identical detections for identical image+profile.
3. **Eval `image_url` is `null` unless dataset files sit under `data/<source>/`** (`routers/eval.py:56-65`). Pre-M6 summaries default `source` to `"mvtec"`; failures render unclickable when the dataset is absent. Likelihood: medium on fresh checkouts; cost: low (degraded, not wrong). Check: open Eval on a machine without `data/mvtec/`.

## Cleared
- **CLI parity**: inspect router calls the same `run_inspection` with the same adapters/cache; synth reuses `generate_pairs`; both default to the same fake/real selection as the CLIs. Covered by parity tests, all passing.
- **`from-sop` relocation**: same path, same shape, never saves; M5 `test_sop.py` path-compat passes.
- **`/files` vs smoke outputs**: `runs/inspect/` overlays land under `data/` so `/files/runs/inspect/*` serves them; the explicit `..`/absolute/backslash guard plus resolve-containment backstop blocks escape (probed above). Eval list skips `runs/inspect/`, `smoke/`, `cli/` (no `summary.json`) so overlays never appear as runs.
- **Gallery vs synth layout**: gallery walks `data/synth/<category>/<defect>/*.png`, skips `_reference.png` and `*_mask.png`, pairs `<stem>_mask.png` or null. Matches `generate_pairs` output layout; grouping test passes.
- **Frontend shape assumptions**: `api.ts:279-498` parses `unknown`-in with defaults for pre-M6 summaries (missing `source`); typed 422/404 errors (`api.ts:536-559`); `image_url`/`mask_url` nullable everywhere rendered. Eval/synth detail endpoints return untyped `dict`s, so extra keys pass through harmlessly.
- **PUT validation**: FastAPI rejects invalid bodies with 422 before the handler runs; file untouched. Body-id≠path-id → 422; bad path id → 404 via `save_profile`'s name regex.

## Before you merge
Cheapest catch-all: `cd backend && .venv/bin/python -m pytest -q` (157 passed today) plus `cd frontend && npm run build` and the secrets grep. Real-bug repro for risk 1: PUT an existing id with a modified body and confirm the overwrite is intended.
