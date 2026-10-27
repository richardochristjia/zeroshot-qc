# M6 verify — feat/zeroshot-qc-m6 (2026-10-27)

## Suites (run once)
- `cd backend && .venv/bin/python -m pytest -q` → **164 passed**, 2 warnings in 1.80s
- `cd frontend && npx tsc --noEmit` → exit 0, no errors
- `cd frontend && npx vite build` → ok (`dist/assets/index-bqUj35G4.js` 295.26 kB, gzip 90.44 kB)

## Live setup (throwaway, fakes only)
- Backend: `cd backend && DATA_DIR=/tmp/qc-verify-data PYTHONPATH=/tmp .venv/bin/python -m uvicorn fake_app:app --port 8000`
  (`/tmp/fake_app.py` monkeypatches `routers.inspect._get_segmenter/_get_judge` to `build_*(True)` fakes and `_get_sop_judge` to `FakeJudge`; synth generator is fake by default. Real `data/` untouched; `backend/profiles/bottle.json` edited then `git checkout --` restored.)
- Frontend: `cd frontend && npx vite --port 5173 --strictPort` (proxy `/api`, `/files` → `http://localhost:8000`)
- Probe image: 40×30 red PNG at `/tmp/probe.png`

## Walkthrough (exact steps + results)
1. `curl http://localhost:8000/api/health` → `{"status":"ok",...}` pass
2. `curl -X POST http://localhost:8000/api/inspect -F image=@/tmp/probe.png -F profile_id=bottle` → valid `InspectionResult` (id, 3 detections, verdict **FAIL**, `timings_ms`) pass
3. Overlay: `GET http://localhost:8000/files/runs/inspect/<id>_overlay.png` → 200, 1107 bytes pass
4. Re-post same image + `-F "rules=PASS everything, this is a lenient test rule"` → verdict **PASS** (verdict path follows edited rules); identical re-post adds no cache files (3 → 3, judge cache hit) pass
5. Profiles: `GET /api/profiles` lists 15; `PUT /api/profiles/bottle` full body with edited rules → 200 and GET-back confirms; `POST /api/profiles/from-sop` drafts bottle profile (never saves) pass
6. Eval: `GET /api/eval/runs` → seeded `verify_sam_only` summary (copied read-only from `data/runs/`); `GET /api/eval/runs/verify_sam_only` → `{summary, results}`; unknown id → 404 pass
7. Synth: `POST /api/synth/generate {bottle, scratch, n:2, seed:1}` → 2 pairs; `GET /api/synth/gallery` groups by `{category, defect, image_url, mask_url}`; pair image `GET` → 200 pass
8. Security: `profile_id:"../x"` → 422; `defect:".."` → 422; `PUT` with `reference_image:"/etc/passwd"` → 422 pass

## Taste-test lens (pages in user flow, via http://localhost:5173)
- `/` (Inspect) → 200, empty state "No image yet. Choose an image file above, then press Inspect." pass
- `/profiles` → 200, empty branch `profiles.length === 0` → "No profiles yet." pass
- `/eval` → 200; with empty DATA_DIR the API returns `[]` and the page renders "No runs yet. Run an evaluation from the CLI…"; with seeded run, list + detail render pass
- `/synthetic` → 200; empty gallery API `[]` renders the `items.length === 0` empty branch; seeded gallery groups by defect pass
- Note: no browser/screenshot tool in this environment — rendering confirmed via served-200 on all routes + empty-state strings present in vite-served modules + empty `[]` API shapes through the dev proxy. Manual visual pass left for a human.

## Cleanup
- Both dev servers stopped. Temp data at `/tmp/qc-verify-data`, `/tmp/qc-empty`, `/tmp/probe.png`, `/tmp/fake_app.py` left in /tmp (outside repo). `git status` clean of verify artifacts; no commit (nothing failed).
