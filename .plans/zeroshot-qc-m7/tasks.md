# ZeroShot QC — M7 Tasks

Spec: `plan.md` in this folder. Tier: `tier.md` in this folder. Base: `main` (M6 PR #6 merged).

## Container + hosting
- [x] Write `Dockerfile` (python:3.11-slim, requirements install, uvicorn CMD, absolute `DATA_DIR` env default per check-1.md, no secrets in layers) + `.dockerignore`
- [x] Write `modal_app.py` (thin wrapper importing the app; sys.path insert for `backend/`, guarded/lazy `modal` import validatable without the package installed per check-1.md)
- [x] Write `vercel.json` + `VITE_API_URL` wiring in `frontend/src/api.ts` with dev-proxy fallback and slash normalization, plus exported file-URL resolver applied at page img-src sites (Inspect/Eval/Synthetic) per check-1.md

## Local verification
- [x] Add env-gated fake-adapter flag for container probes (default real; wire to `build_*(fake)` in `backend/app/routers/inspect.py:27-40` — monkeypatch in `backend/tests/test_routers.py:57-64` cannot reach a running container)
- [x] Start Docker daemon if still down (down at check-2); `docker build` clean; run with `-v <throwaway>:/data -e DATA_DIR=/data -e CORS_ORIGINS=<probe-origin>` and prove health shape + fake multipart inspect (profile `screw`) + overlay fetch + `/files` traversal block per `backend/tests/test_routers.py` patterns
- [x] Production `npm run build` (tsc + vite) clean with `VITE_API_URL` set, rebuilding stale `frontend/dist/`; bundle grep shows no secret patterns; CORS proven with an `Origin`-header fetch matching `CORS_ORIGINS`

## Polish sweep
- [ ] Triage every carried-open item from M1–M6 falsify/gap reports (fix-if-small-and-proven with a test, else carry with owner into the handoff list)
- [ ] Resolve the gallery Record entry (approve and write, or reject with reason in the summary)
- [ ] Rewrite README run/deploy sections with exact push commands; record the submission checklist state
- [ ] Full `pytest` green; `tsc` + `vite build` clean

## Verification
- [ ] Container probes all pass (health, inspect, overlay fetch, traversal block, 404s)
- [ ] Bundle + Dockerfile greps clean; README commands followed verbatim up to the credential boundary
- [ ] Record Updates: append the 2 deploy entries from plan.md Record Updates — first (1) review the complete implementation; (2a) if it matches, write those exact entries into `.agents/RECORD.md`; (2b) if it diverged, write nothing and surface the divergence in the final summary instead

## Manual checks
- [ ] manual: run the documented Modal/Vercel push commands with your logins and confirm the public URL in a private window
