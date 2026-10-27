# ZeroShot QC — M6: Web app

Tier L (12 files, user-visible flow, server API). Loop and steps are in `tier.md` next to this file.

## Problem

Everything works, but only from a terminal: inspecting a part means a CLI command, rules are edited as flags, profiles as JSON, and eval numbers as printed tables. The hackathon judges must see the headline moment in a browser — upload a photo, get PASS/FAIL with outlined defects and written reasons, edit a rule in plain English, watch the verdict flip instantly with no retraining. No page exists yet, and no router serves anything the pages will need.

## Solution

Scaffold `frontend/` with Vite + React + TypeScript + Tailwind (the HANDOFF stack) and implement four pages against real backend routers built to HANDOFF §8: Inspect (upload, hoverable overlay, verdict card, debounced judge-only rule editing served by the existing segment cache — no server sessions), Profiles (list, edit, SOP import via the M5 draft endpoint with save-as-new confirmation), Eval (read-only run list, metrics table, ablation chart, clickable failures), Synthetic (gallery grouped by category and defect type). Images are served from `data/` under `/files/...` with traversal blocked. Dev runs as Vite (proxy) + uvicorn; deploy stays M7.

## Phases

1. **Backend routers.** Implement the four one-line stub routers to HANDOFF §8: `POST /api/inspect` (multipart image + profile_id + optional rules → `InspectionResult`, 422 on double judge failure), profiles GET list / GET one / PUT (validated, atomic write), synth generation endpoint, eval run list/detail, `/files/...` static serving from `data/` (which stays gitignored).
2. **Frontend scaffold.** `frontend/` with Vite + React + TS + Tailwind, a typed API client matching the §8 shapes, four routes, and a dev proxy to the backend. Visual style obeys the bundled taste rules (no AI-slop tells); no webcam code anywhere.
3. **Inspect page.** Profile picker, file upload, overlay with hoverable detections (id + label + size), verdict card with per-ruling reasons, rules textarea that re-posts image + rules debounced so only the judge re-runs.
4. **Profiles + Eval + Synthetic pages.** Profiles list/edit/SOP-import round-trip; Eval table + bar chart + failure links (read-only, never launches runs); Synthetic gallery from `data/synth/`.
5. **Record.** Append the M6 entries from Record Updates after verifying them against the build.

## Acceptance Criteria

1. End-to-end inspect works in the browser: upload → overlay with hoverable detections → verdict card with reasons. Check: walkthrough in Verification.
2. Editing rules flips the verdict without re-uploading (judge-only rerun, visibly fast). Check: walkthrough with timings.
3. Profiles list/edit/SOP-import round-trips; Eval shows table + chart + clickable failures; Synthetic gallery groups correctly. Check: walkthrough per page.
4. `pytest` green (TestClient router tests); frontend `tsc` + `vite build` clean; no secrets in frontend code. Check: suite + build + grep.
5. `manual:` full walkthrough on a second device against the dev servers (upload, rule flip, SOP import, gallery). Human steps: run backend + `npm run dev` on the host, open the Vite URL from another device on the LAN.

## Dialectical Outcomes (Why)

- **Merge M5 first, branch from main.** The user chose this over stacking: the Profiles page imports from M5's `from-sop` endpoint, so it builds on reviewed code. Cost was waiting for the M5 review, which is merged.
- **Upload only, no webcam.** The user applied the roadmap cut-list (webcam is cut #2): upload covers the demo and every acceptance flow with far less browser-permission code. Webcam can ride with M7 polish if time appears.
- **Eval read-only.** The user chose the HANDOFF-literal viewer over launch-from-UI: run launching needs job tracking and a state machine the milestone doesn't need, and with no MVTec data there is nothing real to launch.
- **No server sessions for live editing.** The segment cache already keys on image + prompts, so re-posting image + edited rules is a judge-only rerun by construction. Rejected: a session/upload-id scheme, which would add state for zero benefit.
- **Routers call CLI-grade functions.** Both surfaces share `run_inspection`, profile load/save, and eval readers, so CLI and UI can never disagree. Router tests assert identical verdicts for identical inputs.

## Relevant Files (Where)

- `backend/app/routers/inspect.py` — implement `POST /api/inspect` (currently a one-line stub).
- `backend/app/routers/profiles.py` — implement GET list / GET one / PUT (stub); from-sop already exists from M5.
- `backend/app/routers/eval.py` — implement run list + run detail (stub).
- `backend/app/routers/synth.py` — implement generation endpoint (stub).
- `backend/app/main.py` — mount the four routers, add `/files/...` static serving from `data/`, keep `/api/health`.
- `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` — new scaffold.
- `frontend/src/api.ts` — new typed client for the §8 shapes.
- `frontend/src/pages/Inspect.tsx`, `Profiles.tsx`, `Eval.tsx`, `Synthetic.tsx` — new pages.
- `backend/tests/test_routers.py` — new; TestClient coverage for every route above.

## Key Code Context (What)

The routers consume M1–M5 contracts unchanged: `run_inspection(image, profile, segmenter, judge, rules, reference)` returns detections or `(detections, verdict)` (`backend/app/pipeline/inspect.py:117`); `load_profile(name)` reads `backend/profiles/<name>.json` (`inspect.py:31`); `JudgeValidationError` marks double judge failure (maps to 422); `POST /api/profiles/from-sop` already returns unsaved drafts (M5); eval `results.jsonl` + `summary.json` live under `data/runs/{run_id}` (M4); `data/synth/{profile}/{defect}/` pairs carry image + mask PNGs (M5). The `InspectionResult` schema (`schemas.py:51`) already has `id`, `profile_id`, `detections`, `verdict`, `overlay_url`, `timings_ms` — the inspect route fills it directly.

## Implementation Algorithm (How)

1. **Inspect route.** Parse multipart (`image` bytes, `profile_id`, optional `rules`); load profile (404 on unknown); build fake-or-real cached adapters via the existing wiring; time segment vs judge separately into `timings_ms`; save the overlay PNG under `data/runs/inspect/` and return its `/files/...` URL inside `InspectionResult`. Catch `JudgeValidationError` as 422 with a clean body.
2. **Rules edit.** The page posts the same image bytes with edited rules; the segment cache hits (same image + prompts) and only the judge runs. Debounce ~500ms; abort in-flight requests on new keystrokes.
3. **Profiles.** GET returns all profiles; PUT validates the body as `ProductProfile` and writes atomically (temp + rename), 422 on invalid with the file untouched. SOP import posts `{sop_text, category_name}` to `from-sop`, shows the draft, and saves only on explicit confirm (as a new id, never overwriting without confirm).
4. **Eval + Synthetic.** Eval pages read `summary.json` files for the table/chart and `results.jsonl` rows for failure links (overlay + verdict per row). Synthetic gallery lists `data/synth/` directory pairs as image URLs via `/files/...`.
5. **Static files.** Mount `/files` on the `data/` directory with path-traversal rejection (no `..` escape); uploads from Inspect go to gitignored `data/uploads/`.

## Divergence notes

- New `GET /api/synth/gallery` in `routers/synth.py` (beyond HANDOFF §8, which assumed a listing that didn't exist): read-only enumeration of `data/synth/` as grouped `{category, defect, image_url, mask_url|null}` pairs via `/files/...`, skipping `_reference.png` and tolerating missing masks. Minimal means to the approved Synthetic gallery; `Synthetic.tsx` consumes it via `listSyntheticGallery` in `frontend/src/api.ts`.

## Anti-Goals (Out of Scope)

- Webcam capture (cut by user decision). Eval-run launching (read-only by decision). Conveyor video (M7 stretch). Deploy, public URL, Vercel/Modal config (M7). Authentication or multi-user support (never in HANDOFF). Changing M1–M5 pipeline, adapter, cache, schema, or CLI contracts — the routers consume them as-is.

## Edge Cases & Gotchas

- **Double judge failure → 422**, never a 500 or traceback (M3 established the typed error; the router maps it).
- **Unknown profile / missing run / bad PUT body → 404/404/422** with clean bodies and untouched files.
- **`..` in `/files/` paths must not escape `data/`** (dedicated test case).
- **In-flight rule edits**: abort stale judge requests so a slow first verdict can't overwrite a newer one.
- **Empty states**: no runs, no synth images, and zero detections each render a designed empty state, not a blank page or crash.
- **Frontend carries no secrets**: API base URL only; model IDs and keys never leave the backend (grep guard covers `frontend/src`).
- **Binary discipline**: uploads, overlays, and generated images stay in gitignored `data/`; the repo ships code + fixture only.

## Navigation Anchors

- Entry point: `frontend/src/pages/Inspect.tsx` (the demo path); API choke point: `frontend/src/api.ts` (every backend call flows through it).
- Backend choke point: `backend/app/routers/inspect.py` — the only new caller of `run_inspection` besides CLI/smoke; M7 deploy wraps this same app.
- Swap point: profile load/save functions shared by CLI and routers — the Profiles page edits through them, never direct file writes from the route.

## Dependency Mappings

- Backend: no new third-party deps — FastAPI multipart needs `python-multipart` (already pinned in M1). Frontend: `react`, `react-dom`, `react-router-dom`, `vite`, `typescript`, `tailwindcss` (versions resolved at scaffold; record the lockfile).
- Internal: routers depend on `pipeline/inspect.py`, `adapters` wiring, `schemas.py`, `config.py` — all M1–M5 code, unchanged.

## Test Strategies

- `test_routers.py` (TestClient): inspect happy path returns a valid `InspectionResult` with a fetchable overlay URL; same-image + new-rules leaves the segment adapter uncalled; double judge failure is 422; unknown profile 404; invalid PUT is 422 with file untouched; from-sop save flow creates a file only on confirm; missing run id 404; `/files/../` blocked.
- CLI parity: identical image + profile through CLI and route assert identical verdicts.
- Frontend: `tsc --noEmit` + `vite build` clean (no jsdom suite in M6 — page behavior is proven by the walkthrough, not unit tests).
- Walkthrough (Verification): dev servers up, upload → verdict → rule flip with timings, profiles round-trip, eval table/chart/failures, gallery grouping; exact URLs and steps recorded.
- Commands: `cd backend && .venv/bin/python -m pytest -q`; `cd frontend && npm run build`.

## Record Updates

Entries only (Record exists). Append after verifying against the build:

```markdown
- (api) Inspection requests are currently served by FastAPI routers with images served from data/ under /files/.
- (frontend) The web app currently offers Inspect, Profiles, Eval, and Synthetic pages against the backend API.
- (frontend) The Inspect page currently re-runs only the judge when rules change, reusing cached segmentation.
- (frontend) The Eval page currently displays existing runs and never launches new ones.
- (frontend) Image upload is currently file-based without webcam capture.
```
