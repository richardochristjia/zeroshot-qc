# Blast radius — M7 (feat/zeroshot-qc-m7 vs main)

## What it does
M7 is deploy/config wiring only (M7-AC3: no app-behavior change). New: slim
`Dockerfile` (same FastAPI app via uvicorn), thin `modal_app.py` (imports the
same `app` object, guarded `modal` import), `vercel.json` (static build, SPA
rewrite), `USE_FAKE_ADAPTERS` env flag (default false) so container probes can
serve fake inspect. Changed: `frontend/src/api.ts:470-506` builds every fetch
and `img src` from build-time `VITE_API_URL` (empty in dev → relative URLs,
dev proxy fallback); three pages route image URLs through `resolveFileUrl`.
Docs only: README rewrite, `docs/HANDOFF.md`, `docs/EVAL_NOTES.md` (+3),
`.agents/RECORD.md` (+3), `backend/tests/test_fake_flag.py` (new).

## The one fact it's safe because of
**Both new defaults are byte-identical to the old path when unset: fake flag
defaults to real adapters, and an empty `VITE_API_URL` reproduces the exact
pre-M7 relative URLs.** Proven by running real code (step 4), not by reading:

```
use_fake_adapters default: False
getters gate on settings.use_fake_adapters: OK
2 passed, 1 warning in 0.50s   (tests/test_fake_flag.py, project .venv)
```

```
undefined -> /api/health
"" -> /api/health
"http://localhost:8000/" -> http://localhost:8000/api/health
"https://x.modal.run///" -> https://x.modal.run/files/a.png
normalizeApiBase: dev-relative preserved, no double-slash: OK   (node, exact fn)
```

The Python probe imported the real `Settings` with `USE_FAKE_ADAPTERS` unset
and asserted `False`, plus that both getters read the flag; the flag-on/off
tests pass. The node probe ran the exact `normalizeApiBase` body: `undefined`
(non-string, e.g. env missing at build) and `""` both yield `""`, so
`apiUrl("/api/health") === "/api/health"` — byte-identical to pre-M7 fetches,
and the dev proxy in `frontend/vite.config.ts:9-14` (UNCHANGED) still receives
`/api` + `/files`. Trailing slashes are stripped once, so joins never
double-slash. This single fact clears the default path for every existing
consumer at once: local dev, existing tests, and any container run without
the flag.

## Risks (how it breaks · file:line · likelihood × cost · check)
1. **Prod frontend built without `VITE_API_URL` silently points at itself.**
   `frontend/src/api.ts:483` → `API_BASE=""` → relative `/api/...` fetches hit
   the Vercel static origin, where the catch-all rewrite
   (`vercel.json:6` → `/index.html`) answers 200 with HTML instead of JSON, so
   parsers throw and every page fails. Likelihood: medium (env is set in the
   Vercel dashboard, outside the repo — nothing in `vercel.json` enforces it);
   cost: high (fully broken deployed frontend). Mitigated in-repo: README
   documents `vercel env add VITE_API_URL production` (`README.md:122`) and the
   prod-build requirement (`README.md:68`). Check: after `vercel --prod`, curl
   the public `/api/health` path — JSON from the backend means the env stuck;
   HTML means it didn't.
2. **`resolveFileUrl` only rewrites server-relative URLs.**
   `frontend/src/api.ts:496-506` passes through anything starting with
   `http`, `blob:`, `data:`. If the backend ever emits a protocol-relative
   (`//host/...`) or bare-relative (`files/...`) URL, prod joins it onto the
   wrong origin. Likelihood: low (backend emits `/files/...` per
   `backend/app/main.py:38` and `/files/synth/...` per
   `backend/app/routers/synth.py:40`); cost: medium (broken images only).
   Check: grep backend-emitted URLs for any non-`/`-leading value.
3. **`USE_FAKE_ADAPTERS=true` left on in a real deployment serves fake
   results.** `backend/app/routers/inspect.py:27-50` — the flag is process-wide
   with no per-request marker, so fake inspections are indistinguishable
   downstream. Likelihood: low (default false, proven above; only the documented
   container probe sets it); cost: high (silent wrong verdicts). Check: prod
   deploy env must not contain the flag; `/api/health` could assert it.
4. **README push path is documented-not-run.** `modal setup` / `vercel login`
   were never executed here (no CLIs, human credentials per context-pack).
   Likelihood of doc drift: low-medium; cost: medium (stranger stalls at push).
   Check: first human push follows `README.md:115-130` verbatim and reports back.

## Cleared
- **Dev proxy path**: `vite.config.ts` untouched; empty-base URLs are
  character-identical to pre-M7 (proven above), so local dev and all existing
  tests see zero change. Full suite was 166 green per context-pack.
- **CORS**: `main.py` untouched, still env-driven; M7's container probe covers
  the `Origin` echo.
- **`modal_app.py`**: no app logic — imports the same object the container
  serves; guarded import means it can't break backend import when `modal` is
  absent. Nothing existing imports it.
- **`.dockerignore`**: excludes secrets, data, frontend artifacts, plans —
  additive only; cannot affect running code.
- **`/files/../` traversal, unknown-profile 404**: covered by the M7 container
  probe per context-pack; no code touched those paths.
- **README secret-bundle risk**: prod build + bundle grep for `sk-`/Bearer/key
  patterns is the M7-AC2 gate; `api.ts` header comment confirms no secrets
  (`frontend/src/api.ts:184`).

## Before you merge
Cheapest repro catching the real bug (risk 1): build without the env and show
all fetches stay relative —
`cd frontend && npm run build && grep -o 'VITE_API_URL[^,]*' dist/assets/*.js`
should show nothing backend-absolute; then
`VITE_API_URL=https://<backend> npm run build` and confirm the bundle contains
the origin. Backend: `env -u USE_FAKE_ADAPTERS .venv/bin/python -m pytest
tests/test_fake_flag.py -q` (2 passed, observed this session).
