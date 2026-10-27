# ZeroShot QC — M6 Tasks

Spec: `plan.md` in this folder. Tier: `tier.md` in this folder. Base: `main` (M5 PR #5 merged).

Skill rules for every implementer on this run (all loaded by the orchestrator — follow them, do not reload):
- `bundled:taste` — visual anti-slop filter for every human-viewed page. Negative constraints only; no purple/blue gradients, no gradient headline text, no emoji icons, no glassmorphism-everywhere, respect `prefers-reduced-motion`.
- `bundled:browser-app-delivery` — delivery runs on project runners only: backend `cd backend && .venv/bin/uvicorn app.main:app`, frontend `cd frontend && npm run dev` (Vite proxy to the backend). Hand off exact start commands + concrete URL + open-in-browser wording. Never imply a temp dev server is durable hosting.
- `write-typescript` — boundary validation at the API layer (`unknown` in, parsed domain types out, no `as` casts), typed API client, `tsc --noEmit` clean.
- Durable-test rule: `test_routers.py` is a deliverable in the repo's pytest layout — smallest focused tests, failing-first proof per fix, full suite once at the end.

## Routers
- [x] Pin the routers' fake/real adapter selector (CLI defaults to real with `--fake`); needed for CLI-parity tests (see check-1.md)
- [x] Pin the synth endpoint contract (params, sync/async, response pair URLs via `/files/`) around M5 `generate_pairs` (see check-1.md)
- [x] Implement `POST /api/inspect` in `routers/inspect.py` (multipart image + profile_id + optional rules → `InspectionResult` with overlay `/files/` URL + `timings_ms`; 422 on double judge failure; 404 on unknown profile; segment/judge timings via wrappers around the cached adapters since `run_inspection` fuses both)
- [x] Implement profiles GET list / GET one / PUT in `routers/profiles.py` (validated, atomic write, 422 leaves file untouched; relocate `POST /api/profiles/from-sop` from `main.py` here keeping its path; add shared atomic `save_profile` next to `load_profile` — none exists)
- [x] Implement eval run list + run detail in `routers/eval.py` (404 on missing id; list skips dirs lacking `summary.json`; detail validates `run_id` against traversal, defaults missing `source` to mvtec, builds image URLs from record paths — rows carry no stored overlays)
- [x] Implement synth generation endpoint in `routers/synth.py` reusing the M5 generator
- [x] Mount routers + `/files/...` static serving from `data/` in `main.py` with path-traversal rejection; uploads go to gitignored `data/uploads/`
- [x] Create `backend/tests/test_routers.py` (happy path, judge-only cache hit on new rules, 422 paths, 404 paths, traversal blocked, CLI parity of verdicts)

## Scaffold
- [x] Scaffold `frontend/` (Vite + React + TS + Tailwind — record exact versions incl. Tailwind major, which fixes the scaffold path; dev proxy for `/api` + `/files` → `http://localhost:8000`, matching default CORS `http://localhost:5173`) — versions: Tailwind v4.3.3 (v4 Vite-plugin path, `@import "tailwindcss"`, no PostCSS config); react 19.3.1, react-dom 19.3.1, react-router-dom 7.18.4, vite 8.3.5, typescript 6.0.3, @vitejs/plugin-react 6.1.2; routes `/` `/profiles` `/eval` `/synthetic` + nav; `npm run build` green; lockfile `frontend/package-lock.json` present
- [x] Implement typed `frontend/src/api.ts` client with boundary parsing: `InspectionResult`/`ProductProfile`/`Detection`/`Verdict` from `schemas.py`, plus router-defined shapes with no Pydantic model — eval `{"summary", "results"}` rows (keys per `run.py:179-213` + injected `image_url`, see check-2.md), synth `{profile_id, defect, count, pairs}` (see `routers/synth.py:63-77`), from-sop `{sop_text, category_name}`; typed errors for inspect 422s (judge failure + undecodable image), PUT id-mismatch 422, and 404s

## Inspect page
- [x] Build `Inspect.tsx`: profile picker, file upload, hoverable overlay detections (scale `bbox` pixels to rendered image size over the server overlay PNG), verdict card with per-ruling reasons
- [x] Add debounced rules textarea that re-posts image + rules and aborts stale in-flight requests via the existing `AbortSignal` (clearing restores profile rules — empty `rules` is omitted/`None`); designed empty states (no image, zero detections)

## Profiles + Eval + Synthetic pages
- [ ] Build `Profiles.tsx`: list, edit with PUT, SOP import via from-sop draft with save-as-new confirmation
- [ ] Build `Eval.tsx`: run list, per-category metrics table, ablation bar chart, clickable failure examples (read-only)
- [ ] Build `Synthetic.tsx`: gallery grouped by category and defect type from `data/synth/`

## Verification
- [ ] Walkthrough against live dev servers: upload → verdict → rule flip with timings; profiles round-trip; eval table/chart/failures; gallery grouping (record exact URLs and steps)
- [ ] `pytest` green; `tsc --noEmit` + `vite build` clean; grep guard: no secrets in `frontend/src`, no `data/` writes in git status
- [ ] Record Updates: append the 5 api/frontend entries from the approved plan — first (1) review the complete implementation; (2a) if it matches, write those exact entries into `.agents/RECORD.md`; (2b) if it diverged, write nothing and surface the divergence in the final summary instead. (Note: Tier L spec carries the entries in plan.md Record Updates — use those verbatim.)

## Manual checks
- [ ] manual: full walkthrough on a second device against the dev servers (upload, rule flip, SOP import, gallery)
