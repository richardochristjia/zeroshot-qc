# Risks — single-compose (f041ebc)

1. CORS is a manual `.env` edit — a reviewer who skips adding `http://localhost:8080` to `CORS_ORIGINS` gets a working page with failing API calls and no error pointing at the cause (`docker-compose.yml`, `backend/app/main.py:28`).
2. `VITE_API_URL` bakes at build time — pointing compose at a non-localhost backend silently serves a stale origin until `docker compose build frontend` is re-run (`frontend/Dockerfile:10-11`).
3. `depends_on` has no health condition — the frontend can serve (and browser probes can run) before the backend is ready; first-load API errors may be transient, not real failures.
4. Missing `.env` fails with compose's generic `env_file` error, not the friendly `cp .env.example .env` hint the plan asked for — recoverable, but first-run UX is rougher than planned.
5. Fresh `zqc-data` volume starts empty (`data/` is never baked in) — MVTEC/eval flows need reseeding; `down -v` wipes everything with no warning beyond docs.
6. Fixed host ports `8000`/`8080` with no fallback — clashes with dev servers fail the whole `up`; mitigation is docs-only ("stop dev servers first").
