# Security review — `feat/zeroshot-qc-m7` (M7)

Source of change description: [context-pack.md](.plans/zeroshot-qc-m7/context-pack.md)
(BASE `main` M6-merged; M7 is deploy-ready + polish, config/wiring only).
Scope reviewed: secrets in image layers (ENV, COPY, build args, `.dockerignore`
gaps), CORS origins in prod, `/files` traversal, modal wrapper secret handling,
frontend bundle secrets, `DATA_DIR` writability errors. Every finding below is
backed by a real run on this branch (commands + observed output quoted).

## Must-fix (1)

1. **`.dockerignore` silently covers nothing under `backend/` — the only tree
   ever copied.** Patterns (`.venv/`, `.pytest_cache/`, `.env`, …) are
   context-root-relative, but the Dockerfile does `COPY backend/ .`, so
   `backend/.venv`, `backend/.pytest_cache` (and `backend/tests`,
   `backend/scripts`) are baked in anyway. Proof (`docker run --rm zeroshot-qc
   ls /srv/backend`): image contains `.pytest_cache/`, `.venv/`, `app/`,
   `profiles/`, `scripts/`, `tests/` (COPY layer 353 MB). No live secret was
   found inside (env/image greps below came back clean, and no `.env` file
   exists in the repo — only `.env.example`), but the guard is fail-open: any
   future `backend/.env` or key material lands in a published layer, and the
   README ("`.env`, keys … never baked into layers") currently overstates the
   guarantee. Fix: add `backend/`-prefixed entries (or `**/` globs) for
   `.venv/`, `.pytest_cache/`, `tests/`, `scripts/`, `.env*`, and rebuild.

## Consider

- **Container runs as root (no `USER` in `Dockerfile`).** Proof:
  `docker run --rm zeroshot-qc sh -c 'whoami; id'` → `root`,
  `uid=0(root)`. Combined with an app that writes uploads/overlays/cache under
  `DATA_DIR` and serves `/files`, any future path-handling bug runs with full
 uid. Fix: add a non-root `USER` + `chown /data` (and the `DATA_DIR` mount).
- **Modal push has no secrets story.** `modal_app.py` holds no secrets (good —
  it only re-exports the `app` object from `backend/app/main.py` and reads
  nothing secret-like; `grep` for key/secret/token in it is clean), but the
  README Modal section documents only `modal setup` + `modal deploy`, with no
  `modal secret create …` / `secrets=[…]` wiring for `META_API_KEY`. Operators
  following the README get real adapters with empty keys (runtime 500s) and may
  improvise insecure key passing (bake into the image decorator, paste into
  shell history). Fix: document Modal secrets and wire them in `modal_app.py`.
- **README push path omits prod `CORS_ORIGINS`.** The Modal+Vercel steps never
  set `CORS_ORIGINS` to the Vercel origin, so a README-following deploy serves
  the frontend from an origin the backend does not allow (browsers block every
  call), or tempts `CORS_ORIGINS=*` — which with the current
  `allow_credentials=True` + `allow_methods/headers=["*"]`
  (`backend/app/main.py:28-35`) is a credentialed-wildcard misconfiguration.
  Fix: document setting `CORS_ORIGINS=https://<vercel-app>` on the Modal app.
- **Stale local `frontend/dist/` bakes `http://localhost:8000`.** Proof:
  `grep -o 'localhost:8000'` hits `frontend/dist/assets/index-*.js`
  (`API_BASE` baked from a local `VITE_API_URL` build). `frontend/dist/` is
  gitignored (`frontend/.gitignore:11`) and Vercel rebuilds from source, so
  this does not ship — but anyone serving that directory as "prod" points all
  browsers at localhost. Fix: `git clean`/rebuild at release time; no code
  change needed.

## Noted (checked, no action)

- **No secrets in image env or layers.** Proof: `docker inspect zeroshot-qc`
  Env = only `PATH/LANG/GPG_KEY/PYTHON_*/PYTHONDONTWRITEBYTECODE/
  PYTHONUNBUFFERED/DATA_DIR=/data` — no keys, no tokens, no build `ARG`
  (Dockerfile has none). `find` inside the image for `.env*`/`*.key`/`*.pem`/
  `secrets` → nothing.
- **`/files` traversal blocked, three ways.** Proof against the live container
  (`USE_FAKE_ADAPTERS=true`): `/files/../outside.txt` → 404,
  `/files/%2e%2e/outside.txt` → 404, `/files//etc/passwd` → 404. Code
  (`backend/app/main.py:38-55`) rejects `..`/absolute/backslash segments AND
  re-resolves against the data root (defense in depth).
- **CORS is explicit-origin echo, fail-closed.** Proof (live, with
  `CORS_ORIGINS=https://app.example.com`): allowed `Origin` →
  `access-control-allow-origin: https://app.example.com`; `Origin:
  https://evil.example.com` → no echo header. Default
  `cors_origins=http://localhost:5173` (`backend/app/config.py:30`) is safe.
- **Frontend bundle carries no secrets.** Proof: full-pattern grep over
  `frontend/dist` (`sk-…`, `sk-ant-…`, `xox*`, `AIza…`, `AKIA…`, private-key
  blocks, `Bearer …`) → the single `sk-` hit is the `mask-type` SVG attribute
  substring (false positive, shown with ±80 chars context). No
  `frontend/.env*` files exist; the only baked env value is `VITE_API_URL`
  (a public origin URL by design, and `ApiError`/parsers send no auth
  headers — `frontend/src/api.ts` builds auth-free fetches).
- **`DATA_DIR` unwritable fails as a generic 500 with no leak.** Proof (live,
  `/data` mounted `:ro`): `POST /api/inspect` → HTTP 500, body exactly
  `Internal Server Error` (21 bytes, verified via `wc -c` — the traceback
  stays in server logs only). Availability-only: single request fails, server
  stays up. Cache entries themselves never contain the API key by construction
  (`backend/app/pipeline/cache.py:1-20` docstring + key = sha256 of inputs).
- **No authentication on any route — accepted, out of scope.** The API
  (health/inspect/files/synth) is intentionally open in M1–M6 design; adding
  auth would be new behavior (M7-AC3 forbids app-behavior change). Risk stands
  for the public Modal URL (anyone can spend model budget / fill `DATA_DIR`);
  carried as a known limitation, not a regression.
- **`/api/health` exposes model IDs.** By design (context-pack API contract);
  IDs are non-secret identifiers, key stays server-side. No action.
