# Single `docker compose` run — plan

## Problem

The whole app takes two terminals today: backend `uvicorn :8000` plus
frontend `npm run dev :5173`, with production split across Modal +
Vercel. There is no single-command local run.

## Solution

- Prod-like, two-service compose (decision 1A):
  - `backend`: the existing `Dockerfile` image, unchanged.
  - `frontend`: a new nginx image serving the built `frontend/dist`,
    with `VITE_API_URL` passed as a build arg.
- Compose reads the existing `.env` and persists data in a volume
  (decision 2A). No backend code change; CORS and `/files` behavior
  stay as-is.

## Phases

1. **Frontend image** — `frontend/Dockerfile` (node builder + nginx
   runtime, SPA fallback) plus `frontend/nginx.conf`.
2. **Compose file** — repo-root `docker-compose.yml` wiring backend +
   frontend, `env_file: .env`, `DATA_DIR=/data` volume, published
   ports, frontend origin covered by `CORS_ORIGINS`.
3. **Docs** — short `README` compose section next to `Run with Docker`.

## Acceptance criteria

1. `docker compose build` exits 0 from a clean checkout.
2. `docker compose up` starts both services; backend check:
   `curl localhost:8000/api/health` returns 200 with `status ok`.
3. Fake inspect through compose: `POST /api/inspect` with
   `USE_FAKE_ADAPTERS=true` returns 200 with verdict JSON.
4. Composed frontend loads in a browser and its API calls succeed
   (Inspect page against the composed backend).
5. Data persists: a file written under `/data` survives `down`/`up`.
6. `manual:` real-model inspect/synth with filled `.env` keys returns
   200 through the composed frontend origin (needs human keys).

## Dialectical Outcomes (Why)

- Two services over one container (1A over 1B): keeps the existing
  split-deploy shape (Modal backend, Vercel frontend) intact, so the
  compose setup mirrors production instead of forking it. 1B would
  couple frontend rebuilds to the backend image and add static-serving
  code to FastAPI for no deploy benefit.
- Dev-mode compose rejected (1C): the Vite dev server image is for
  daily coding, not the asked single command a reviewer runs to see
  the whole app; prod-like build is what the submission checklist
  needs.
- `.env` + data volume over hardcoded fake defaults (2A over 2B):
  matches today's `docker run` flags and `.dockerignore` behavior
  (secrets never baked into layers); keyless demo still works by
  setting `USE_FAKE_ADAPTERS=true` in `.env`.

## Relevant Files (Where)

- `docker-compose.yml` (repo root) — CREATE: backend + frontend
  services, `env_file`, volumes, ports.
- `frontend/Dockerfile` — CREATE: multi-stage node build → nginx.
- `frontend/nginx.conf` — CREATE: static serving + SPA fallback.
- `README.md` — CHANGE: compose section next to `Run with Docker`.

## Key Code Context (What)

Backend image, `Dockerfile` (unchanged, compose reuses it):

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data
WORKDIR /srv/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
RUN mkdir -p /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Frontend origin is build-time, `frontend/src/api.ts:475-485`:

```ts
export function normalizeApiBase(rawBase: unknown): string {
  if (typeof rawBase !== "string") return "";
  return rawBase.replace(/\/+$/, "");
}
const API_BASE = normalizeApiBase(import.meta.env.VITE_API_URL);
```

Dev proxy being replaced in compose, `frontend/vite.config.ts:9-14`:

```ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/files': 'http://localhost:8000',
  },
},
```

Backend CORS + data + health, `backend/app/main.py:28-35,38-58`:

```python
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, ...)
# GET /files/{rel_path:path} serves data/ with traversal → 404
# GET /api/health → {"status": "ok", "models": {...}}
```

Build output dir, `vercel.json`: build `cd frontend && npm ci && npm
run build`, output `frontend/dist`. Env keys, `.env.example`:
`META_API_KEY`, `META_API_BASE_URL`, `SAM_MODEL_ID`,
`JUDGE_MODEL_ID`, `IMAGE_MODEL_ID`, `DATA_DIR=./data`,
`MVTEC_DIR=./data/mvtec`, `CORS_ORIGINS=http://localhost:5173`,
`USE_FAKE_ADAPTERS=false`.

## Implementation Algorithm (How)

1. `frontend/Dockerfile`: `node:20-alpine` builder runs
   `npm ci && npm run build` with `ARG VITE_API_URL`; runtime
   `nginx:alpine` copies `dist/` and `frontend/nginx.conf`;
   `nginx.conf` serves static files with `try_files $uri $uri/
   /index.html` fallback.
2. `docker-compose.yml`: `backend` builds `.` (existing Dockerfile),
   `env_file: [.env]`, `DATA_DIR=/data` volume mount, port
   `8000:8000`; `frontend` builds `frontend/` with
   `VITE_API_URL` arg defaulting to `http://localhost:8000`, port
   `8080:80` (or `5173:80`), `depends_on: [backend]`.
3. Compose-time `CORS_ORIGINS` must include the frontend origin;
   document setting it in `.env` (e.g. add the composed frontend
   URL alongside `http://localhost:5173`).
4. Verify criteria 1–5 in order; criterion 6 stays manual.

## Anti-Goals (Out of Scope)

- No single-container backend-serves-frontend variant.
- No dev-mode (Vite HMR) compose service.
- No change to Modal/Vercel deploy, backend code, API, or auth.
- No test-file changes; no new runtime dependencies.

## Edge Cases & Gotchas

- `VITE_API_URL` bakes at build time: changing the backend origin
  needs `docker compose build frontend`, not just `up`. Default the
  arg to `http://localhost:8000`.
- Browser-origin CORS: the composed frontend origin differs from
  `:5173`, so `.env` `CORS_ORIGINS` must list it or API calls fail.
- `.env` is required at compose time (`env_file`); missing file must
  fail with a message telling the user to `cp .env.example .env`.
- `data/` is gitignored and `.dockerignore`d: seed data comes only
  from the volume mount, never the image.
- `/files/...` URLs are built from `API_BASE`: with the default arg
  they resolve to the backend origin, which browsers reach directly.
- Port clash: if host `:8000` is taken by a dev backend, compose
  fails — document stopping the dev servers first.

## Navigation Anchors

- `backend/app/main.py` — CORS origins, `/files/`, `/api/health`.
- `frontend/src/api.ts` (`API_BASE`, `normalizeApiBase`) — why the
  build arg exists.
- `Dockerfile` — the backend image compose reuses verbatim.
- `vercel.json` — canonical frontend build command + `dist` output.

## Dependency Mappings

- New external images only: `node:20-alpine` (builder),
  `nginx:alpine` (runtime). No new npm or pip dependencies; no new
  internal module imports.

## Test Strategies

- Per-phase: after the frontend image, `docker build frontend/`
  then serve check; after compose, criteria 1–5 end to end.
- Regression: backend `pytest` (`backend/tests/`) and frontend
  `vitest run` unchanged — compose adds no code paths, so both suites
  must stay green; run once at the end.
- Commands: `docker compose build`, `docker compose up -d`,
  `curl localhost:8000/api/health`, fake-inspect curl from the README
  probe, `docker compose down -v` for the persistence negative case.

## Record Updates

- (deploy) The app currently runs as backend and frontend containers via a single docker compose file.

## Divergences (as built f041ebc)

- Port fixed at `8080:80`; the `5173:80` alternative floated in the algorithm was not used.
- Missing-`.env` failure is compose's generic `env_file` error, not a custom `cp .env.example .env` message (criterion edge case only partially met; README + compose header document the step instead).
- No other divergence: two-service shape, `env_file` + volume, build-time `VITE_API_URL`, nginx SPA fallback, and anti-goals all match.
