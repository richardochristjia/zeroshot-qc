# ZeroShot QC — M7: Deploy-ready + polish

Tier L (deploy surface: `Dockerfile` + hosting config). Loop and steps are in `tier.md` next to this file.

## Problem

The app runs only on this machine: no container image, no hosting config, no documented path to a public URL — which the submission checklist requires. The polish backlog from M1–M6 (deferred review items, README gaps, one undecided Record entry) is also still open. No Modal/Vercel CLIs or credentials exist here, so the cloud push itself stays a human step.

## Solution

Ship a verified-local deploy path the user pushes: a slim Python 3.11 `Dockerfile` running uvicorn (config by environment, no keys in layers), a thin `modal_app.py` wrapping the same ASGI app, and a `vercel.json` static frontend build wired to the backend through a build-time `VITE_API_URL` (dev proxy stays the fallback). Verify everything that can be verified locally (`docker build` + `docker run` + health/inspect/`/files` against the container, prod frontend build). Polish in the same run: triage every open item from the M1–M6 falsify/gap reports, decide the gallery Record entry, and bring the README to clone-to-push quality.

## Phases

1. **Container + hosting configs.** `Dockerfile` (python:3.11-slim, uvicorn, `DATA_DIR` env, `.dockerignore` excluding keys/data/node_modules), `modal_app.py` (no logic fork — imports the app), `vercel.json` + frontend `VITE_API_URL` wiring with dev-proxy fallback, CORS behavior verified against configured origins.
2. **Local verification.** `docker build`, run the container, and prove health + fake inspect + `/files` fetch against it; `vite build` with a production API URL and a secrets grep over the bundle.
3. **Polish sweep.** Triage all carried-open items from `.plans/*/falsify.md` and `gap-analysis.md` (fix what is small and proven, carry the rest with owners); resolve the gallery Record entry approve/reject; rewrite README run/deploy sections; record the submission checklist state.
4. **Record.** Append the M7 entries from Record Updates after verifying them against the build.

## Acceptance Criteria

1. `docker build` succeeds; the container passes health, fake inspect with fetchable overlay, and `/files` fetch. Check: container runs in Verification.
2. Production frontend build succeeds with no secret patterns in the bundle. Check: build + grep in Verification.
3. `pytest` green; no app-code behavior changes (config/wiring only). Check: full suite.
4. README takes a stranger from clone to local run to (with their own logins) public URL push. Check: README review against the checklist.
5. `manual:` the user runs the Modal/Vercel push commands and confirms the public URL in a private window. Human steps: log in to each host, run the documented commands, open the URL privately.

## Dialectical Outcomes (Why)

- **Deploy-ready, user pushes.** The user chose this over a full in-run deploy: no hosting credentials exist here, so the run verifies everything short of the cloud push and hands over exact commands. A run that blocks on credentials it cannot get helps nobody.
- **Polish over conveyor.** The user applied the cut-list (conveyor is cut #1): hardening, docs, and the submission path beat a second project nearly M6's size on fake video.
- **No logic forks for hosting.** The Modal wrapper imports the same app object the container serves; the frontend needs only a URL switch. Rejected: host-specific code paths, which would double every future backend change.
- **CORS verified, not reworked.** Origins are already env-driven; the run proves browser fetches succeed rather than redesigning what works.

## Relevant Files (Where)

- `Dockerfile` — new; slim backend image.
- `.dockerignore` — new; keys, data, node_modules, caches excluded.
- `modal_app.py` — new; thin Modal wrapper at repo root.
- `vercel.json` — new; frontend static build config.
- `frontend/src/api.ts`, `frontend/vite.config.ts` — change; build-time API URL with proxy fallback.
- `backend/app/main.py` — change only if CORS/proxy verification demands it; otherwise untouched.
- `README.md` — change; run + deploy + push documentation.
- `.agents/RECORD.md` — change; M7 entries on verified match only.

## Key Code Context (What)

The deliverable surface is config, not app logic: `backend/app/main.py` (29 lines — FastAPI app + CORS from `settings.cors_origins` + `/api/health` + M6 routers + `/files` mount), `frontend/vite.config.ts` (dev proxy targeting local uvicorn on 8000), `frontend/src/api.ts` (the single backend-call choke point), and `.env.example` (the 8 keys from M1). The container runs `uvicorn app.main:app` from `backend/`; `DATA_DIR` stays an env var so the image never bakes in data.

## Implementation Algorithm (How)

1. **Image.** `FROM python:3.11-slim`, install `backend/requirements.txt`, copy `backend/`, expose 8000, `CMD uvicorn app.main:app`. Build args carry nothing secret; `.dockerignore` keeps `.env`, `data/`, and caches out of the layers.
2. **Run.** `docker run -e DATA_DIR=/data -p 8000:8000` against a throwaway host dir; prove `/api/health`, a fake `POST /api/inspect` with fetchable overlay, and a `/files/...` fetch through the container's port.
3. **Frontend.** `VITE_API_URL` read at build time, dev proxy when unset; `vite build` output checked for key patterns; `vercel.json` serves the static build.
4. **Modal.** `modal_app.py` imports the app object and exposes it with Modal's ASGI construct; validated by import + config check without credentials (no `modal deploy` in the run).
5. **Polish.** Walk every `leave-open`/`your-call`/carried item in the M1–M6 plan folders: fix it with a test if small and proven, else write it into the handoff list with an owner. Decide the gallery entry. Update README and the checklist.

## Anti-Goals (Out of Scope)

- The cloud push itself (`modal deploy`, `vercel --prod`) — human step with human credentials. Conveyor video. Webcam. Eval-run launching. Auth/multi-user. Real-model validation (still keyless). Any M1–M6 behavior change beyond config/wiring.

## Edge Cases & Gotchas

- **Secrets in layers.** Build args and env files must never land in the image; grep the build context and the Dockerfile for key patterns, and never `COPY .env`.
- **`VITE_API_URL` trailing slash.** Normalize once in `api.ts` so `/api/...` joins never double-slash or drop the path.
- **CORS in prod.** The container must accept the Vercel origin; prove with an `Origin`-header fetch, not by opening `*` further than M1 already did.
- **`/files` outside `data/`.** The M6 traversal guard must hold identically in the container (re-prove, don't assume).
- **`DATA_DIR` unwritable in container.** Fail with the existing clear config error, not a traceback on first upload.

## Navigation Anchors

- Entry point: `Dockerfile` CMD (`uvicorn app.main:app` from `backend/`).
- Wiring choke point: `frontend/src/api.ts` (base-URL normalization lives here, once).
- Docs choke point: `README.md` run/deploy sections (the push handoff lives here, exact commands).

## Dependency Mappings

- No new runtime dependencies. Build-time only: `docker` CLI (present), `modal`/`vercel` CLIs are the user's (documented, not installed). Frontend deps resolve from the M6 lockfile.

## Test Strategies

- Container probes (Verification, live): health 200 with model IDs, fake inspect returns valid `InspectionResult`, overlay URL fetches 200, `/files/../` blocked, unknown profile 404 — all against the container port.
- Bundle grep: no `sk-`/Bearer/key patterns in `frontend/dist`; `VITE_API_URL` honored by a build-and-inspect of the output.
- Regression: full `pytest` green (config-only changes must move nothing); `tsc` + `vite build` clean.
- README check: a reader test — follow the documented commands verbatim on a clean checkout path and confirm each works up to the credential boundary.

## Record Updates

Entries only (Record exists). Append after verifying against the build:

```markdown
- (deploy) The backend currently ships as a Python 3.11 container running uvicorn with configuration by environment.
- (deploy) The frontend currently builds to static assets targeting the backend through a build-time API URL.
```
