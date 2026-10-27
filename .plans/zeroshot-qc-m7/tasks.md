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
- [x] Triage carried-open items per `check-3.md` inventory (13 carry + 1 docs fix; M1-RECORD item already done, M3/M4 carry nothing)
- [x] Docs-only fix: document synth `n_defective` per-defect-type (vs MVTec total) semantics in `docs/EVAL_NOTES.md`
- [x] Carry list: wrote all 13 carry items with owners into docs/HANDOFF.md (new; no handoff list existed) (code debt: M1-LO2, M2-F2 naming call, M2-LO unification, M6-St2/St3/St4, M6-I1 rule call, M6-I2, M6-I3, M5/M3 consider leftovers; manual: M1-AC6 real-smoke, M2-AC5 CLI MVTec, M6-G0 second-device)
- [x] Resolve the gallery Record entry (approve and write, or reject with reason in the summary) → APPROVED + written (verified live: 200, 11 grouped entries)
- [x] Rewrite README run/deploy sections with exact push commands; record the submission checklist state
- [x] Full `pytest` green; `tsc` + `vite build` clean

## Verification
- [x] Container probes confirmed: reuse Phase-2 green evidence (23f70da) + verify tree-clean for code/wiring since; re-run only the 5 probes (health, fake inspect, overlay fetch, traversal block, unknown-profile 404) if image/container still available, else confirm-and-note
- [x] Bundle grep (`sk-`/Bearer/key patterns over fresh prod `frontend/dist/`, read hits per false-positive warning) + Dockerfile grep (no `COPY .env`, no key patterns) clean; README reader-test result from Phase 3 confirmed standing (no README change since)
- [x] Record Updates: append the 2 deploy entries from plan.md Record Updates — first (1) review the complete implementation; (2a) if it matches, write those exact entries into `.agents/RECORD.md`; (2b) if it diverged, write nothing and surface the divergence in the final summary instead

## Manual checks
- [ ] manual: run the documented Modal/Vercel push commands with your logins and confirm the public URL in a private window
