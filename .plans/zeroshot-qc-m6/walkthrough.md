# ZeroShot QC M6 — live walkthrough record

Date: 2026-10-27. Branch `feat/zeroshot-qc-m6`. FAKES ONLY — no real model calls.

## Servers (temporary, stopped after the run)

- Backend (fake adapters): `cd backend && PYTHONPATH=/tmp/m6walk:. .venv/bin/uvicorn fake_app:app --port 8000`
  (`/tmp/m6walk/fake_app.py` imported the real `app.main:app` but replaced
  `routers/inspect._get_segmenter/_get_judge` with `build_*(True)` fakes and
  `app.main._get_sop_judge` with `FakeJudge`, so no `META_API_KEY` or network
  was needed. Project runner for real use: `cd backend && .venv/bin/uvicorn app.main:app`.)
- Frontend: `cd frontend && npm run dev` → Vite on http://localhost:5173/
- Health: `GET http://localhost:8000/api/health` → `{"status":"ok","models":{"sam":"","judge":"","image":""}}`
- Vite proxy proved: `GET http://localhost:5173/api/health` → same `status ok` body.

## Page routes via Vite (all HTTP 200)

- http://localhost:5173/ (Inspect), http://localhost:5173/profiles,
  http://localhost:5173/eval, http://localhost:5173/synthetic — each returned
  200 with the Vite React shell. Open one in a browser to click through.

## 1. Upload → verdict → rule flip (Inspect)

Fixture: `backend/tests/fixtures/mvtec/widget/test/scratch/000.png` (159 bytes), profile `screw`.

- Step A — strict: `POST /api/inspect` multipart (`image`=fixture bytes,
  `profile_id=screw`, no `rules`) → 200, `verdict=FAIL`, 3 detections,
  `timings_ms={segment: 1, judge: 1, total: 21}`,
  `overlay_url=/files/runs/inspect/be3438da349f44f1b8ce1e0455b2c950_overlay.png`.
- Step B — rule flip, same bytes + `rules="lenient: pass everything for this check"`:
  → 200, `verdict=PASS` (flipped), 3 detections,
  `timings_ms={segment: 0, judge: 1, total: 8}`.
  Segment 1 ms → 0 ms on identical bytes = cache hit: judge-only rerun, total 21 ms → 8 ms.
- Overlay: `GET <overlay_url>` → 200 `image/png`, 1685 bytes.
- Negative: unknown `profile_id=nope` → 404.

## 2. Profiles round-trip

- `GET /api/profiles` → 200, 15 profiles (`bottle`, `cable`, `capsule`, `carpet`, `grid`, …).
- `GET /api/profiles/screw` → 200, `name=Screw`.
- `POST /api/profiles/from-sop` `{sop_text: "FAIL a widget with any scratch; PASS otherwise.", category_name: "walktmp"}`
  → 200 draft `{id: walktmp, rules: <sop text>, defect_prompts: []}`; nothing saved by the draft call.
- `PUT /api/profiles/walktmp` (draft body + prompts/rules) → 200; re-`GET` returned the edited rules. Temp file removed afterwards; `git status` clean.
- `PUT` with body id ≠ path id → 422.

## 3. Eval table / chart source / failures

- `GET /api/eval/runs` → 200, 6 runs:
  `m5verify-sam_judge`, `m5verify-sam_judge_ref`, `m5verify-sam_only`,
  `verify_sam_judge`, `verify_sam_judge_ref`, `verify_sam_only`.
  (Dirs without `summary.json`, e.g. `smoke/`, `cli/`, correctly skipped.)
- `GET /api/eval/runs/m5verify-sam_judge` → 200,
  summary keys `adapter, categories, metrics, mode, n_defective, n_good, rules, run_id, seed, source`,
  10 results. First row `image_url=/files/synth/bottle/scratch/002.png`.
- Failure image: `GET /files/synth/bottle/scratch/002.png` → 200 `image/png`, 245 bytes.
- All 10 rows in this run had non-null `image_url`; the null/missing-dataset
  empty state is covered by router tests, not by live data here.
- Traversal: `GET /api/eval/runs/..%2F..%2Fsecret` → 404; `GET /files/../backend/app/main.py` → 404.

## 4. Synthetic gallery grouping

- `GET /api/synth/gallery` → 200, 11 entries grouped
  `{('bottle','scratch'): 10, ('bottle','dent'): 1}`,
  entry keys `category, defect, image_url, mask_url`; some `mask_url` null (tolerated).
- `GET /files/synth/bottle/dent/000.png` → 200, 212 bytes.
- `_reference.png` correctly absent from entries.

## Notes for guards / record unit

- Repo untouched by the walkthrough: temp profile file deleted, inspect
  overlays/cache landed in gitignored `data/`; `git status` shows no tracked modifications.
- Temp servers stopped; `/tmp/m6walk` (fake launcher + probe) removed.
