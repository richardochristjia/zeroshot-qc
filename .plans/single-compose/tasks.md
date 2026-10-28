## Frontend image
- [x] Add `frontend/Dockerfile` (node builder with `VITE_API_URL` arg, nginx runtime)
- [x] Add `frontend/nginx.conf` (static serving with SPA fallback to `index.html`)

## Compose file
- [x] Add repo-root `docker-compose.yml` (backend + frontend, `env_file`, data volume, ports, `depends_on`)
- [x] Verify `docker compose build` exits 0 and both services start

## Docs
- [x] Add short compose section to `README.md` next to `Run with Docker` (`.env` setup, `CORS_ORIGINS`, ports, fake-adapter demo)

## Verification
- [x] Backend healthy in compose: `curl localhost:8000/api/health` → 200 `status ok`
- [x] Fake inspect through compose returns 200 with verdict JSON
- [x] Composed frontend loads and its API calls succeed
- [x] Data persists across `down`/`up`
- [x] Backend `pytest` and frontend `vitest run` stay green
- [x] Record Updates: implementation matches the planned entry — written verbatim into `.agents/RECORD.md`

## Manual checks
- [ ] `manual:` real-model inspect/synth with filled `.env` keys returns 200 through the composed frontend origin (needs human keys)
