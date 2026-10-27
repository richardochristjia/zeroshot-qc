# M7 Verify — 2026-10-27

- `cd backend && .venv/bin/python -m pytest -q` → 171 passed in 1.79s
- `cd frontend && npx tsc --noEmit` → exit 0, no errors
- `cd frontend && npx vite build` → built in 146ms (index-BzlfxRVP.js 295.54 kB, gzip 90.54 kB)
- `cd frontend && npx vitest run` → 7 passed (url-join.test.ts)
- `docker build -t zeroshot-qc-m7 .` → image zeroshot-qc-m7:latest, 570MB
- Container (throwaway host dir /tmp/qcm7data, `-v /tmp/qcm7data:/data -e DATA_DIR=/data`):
  - `GET /api/health` → 200 `{"status":"ok","models":{"sam":"","judge":"","image":""}}`
  - Fake inspect (`-e USE_FAKE_ADAPTERS=1`, multipart image + `profile_id=bottle`) → 200, verdict FAIL, overlay `/files/runs/inspect/6799734aa8cb41039882f22216007f02_overlay.png`
  - `GET <overlay_url>` → 200, 2846 bytes, PNG 64x64 (fetchable)
  - `GET /files/../../etc/passwd` → 404; `GET /files/..%2F..%2Fetc%2Fpasswd` → 404 (traversal blocked)
  - `GET /files/nope.png` → 404; `GET /api/does-not-exist` → 404
- Secret greps over `frontend/dist Dockerfile backend/app backend/profiles` (sk-…, AKIA…, api-key assignments, private keys, ghp_…) → no matches
- `.agents/RECORD.md` → holds both deploy entries (backend 3.11/uvicorn/env; frontend static + build-time API URL) plus gallery entry (`GET /api/synth/gallery`, `/files/` URLs)
- Container `qcm7` stopped; no fix commit needed (nothing failed).
