# Context pack

BASE: main
CHANGED: 4 files, +95/-0 (all new except README +19)

## What this change does
Adds a prod-like two-service `docker-compose.yml` (commit f041ebc): existing backend image on `8000` plus a new nginx frontend image on `8080`. Single command `docker compose up --build` runs the whole app locally. No backend code change.

## Files
- `docker-compose.yml:1-43` — new compose file; backend (build `.`, `env_file: .env`, `DATA_DIR=/data`, `zqc-data:/data`, `8000:8000`) + frontend (build `./frontend`, `VITE_API_URL` arg, `8080:80`, `depends_on: backend`).
- `frontend/Dockerfile:1-22` — new frontend image; `node:20-alpine` builder (`npm ci && npm run build`, `ARG VITE_API_URL`) → `nginx:alpine` serving `dist/`.
- `frontend/nginx.conf:1-11` — new nginx config; static root plus `try_files $uri $uri/ /index.html` SPA fallback.
- `README.md:110-128` — new "Run everything with a single command" section; `.env` setup, CORS note, build-time `VITE_API_URL` note, volume note, port-clash note.

## API contracts
- `GET /api/health` → 200 `{"status": "ok", "models": {...}}`; declared in `backend/app/main.py:58`.
- `POST /api/inspect` (multipart `image` + `profile_id`) → 200 verdict JSON; fake path via `USE_FAKE_ADAPTERS=true` (see `backend/tests/test_fake_flag.py`).
- `GET /files/{rel_path:path}` → serves `data/`, traversal → 404; declared in `backend/app/main.py:38`.
- CORS: `allow_origins` parsed from `CORS_ORIGINS` in `backend/app/main.py:28`; composed frontend origin (`http://localhost:8080`) must be listed or browser API calls fail.
- Frontend API base: build-time `import.meta.env.VITE_API_URL` normalized by `normalizeApiBase` in `frontend/src/api.ts:475-485`.

## Test entry points
- Backend: `pytest backend/tests/` (`test_health.py`, `test_inspect.py`, `test_fake_flag.py` cover the composed paths) — `python -m pytest backend/tests/ -q`.
- Frontend: `frontend/src/url-join.test.ts` — `npx vitest run` from `frontend/`.
- Compose (manual, needs docker): `docker compose build`; `docker compose up -d`; `curl localhost:8000/api/health`; README fake-inspect probe; `down`/`up` persistence check.
- Per run-state: builder verified criteria 1–5, pytest 172 passed, vitest 7 passed.

## Acceptance criteria
1. `docker compose build` exits 0 from a clean checkout.
2. `docker compose up` starts both services; backend check: `curl localhost:8000/api/health` returns 200 with `status ok`.
3. Fake inspect through compose: `POST /api/inspect` with `USE_FAKE_ADAPTERS=true` returns 200 with verdict JSON.
4. Composed frontend loads in a browser and its API calls succeed (Inspect page against the composed backend).
5. Data persists: a file written under `/data` survives `down`/`up`.
6. manual: real-model inspect/synth with filled `.env` keys returns 200 through the composed frontend origin (needs human keys).

## Do not re-derive
- `VITE_API_URL` bakes at build time (`frontend/Dockerfile:10-11`); changing the backend origin needs `docker compose build frontend`, not just `up`.
- CORS is the manual step: compose does not set it; the user's `.env` `CORS_ORIGINS` must include `http://localhost:8080` (`docker-compose.yml` header comment, `README.md` note).
- `data/` is gitignored/`.dockerignore`d and never baked into the image; seed data on a fresh machine comes only from the `zqc-data` volume mount (`docker-compose.yml` comment).
- `depends_on: backend` is start-order only, no health condition; frontend can serve before the backend is ready.
- Missing `.env` fails with compose's generic `env_file` error, not a custom message.
- Out of scope by plan: no single-container variant, no Vite-dev compose service, no Modal/Vercel/backend-code/API/auth changes.

## Diff
```diff
diff --git a/README.md b/README.md
index c758f39..c32343e 100644
--- a/README.md
+++ b/README.md
@@ -107,6 +107,25 @@ curl -s -F 'image=@/tmp/zqc-data/probe.png;type=image/png' \
   -F 'profile_id=screw' localhost:8000/api/inspect | head -c 300
 ```

+## Run everything with a single command
+
+`docker-compose.yml` (repo root) runs the whole app prod-like: backend on `8000`, nginx frontend on `8080`.
+
+```sh
+cp .env.example .env   # required: compose reads .env and fails without it
+docker compose up --build
+```
+
+Then open `http://localhost:8080` (backend health: `curl localhost:8000/api/health`).
+
+Notes:
+
+- `.env` must list the composed frontend origin in `CORS_ORIGINS`, e.g. `CORS_ORIGINS=http://localhost:5173,http://localhost:8080`, or the page's API calls fail.
+- Keyless demo: set `USE_FAKE_ADAPTERS=true` in `.env`, then the fake `/api/inspect` probe above works through compose unchanged.
+- `VITE_API_URL` bakes into the frontend at build time (default `http://localhost:8000`); changing the backend origin needs `docker compose build frontend`, not just `up`.
+- Data persists in the `zqc-data` volume across `down`/`up` (`down -v` deletes it).
+- Stop the dev servers (`uvicorn :8000`, Vite) first if the host ports are taken.
+
 ## Push to a public URL (human steps — need YOUR logins; never run by automation)

 Backend → Modal:
diff --git a/docker-compose.yml b/docker-compose.yml
new file mode 100644
index 0000000..5cd3444
--- /dev/null
+++ b/docker-compose.yml
@@ -0,0 +1,43 @@
+# Single-command local run: backend + frontend.
+#
+# Setup:
+#   cp .env.example .env   # compose fails without .env (env_file below)
+# and make sure CORS_ORIGINS in .env lists the composed frontend origin,
+# e.g. CORS_ORIGINS=http://localhost:5173,http://localhost:8080
+#
+# Run:
+#   docker compose up --build
+#
+# Frontend: http://localhost:8080 (VITE_API_URL bakes in at build time;
+# changing the backend origin needs `docker compose build frontend`).
+# Backend:  http://localhost:8000
+#
+# Stop the Vite/uvicorn dev servers first if host :8000 is taken.
+# Data persists in the zqc-data volume across `down`/`up`
+# (`down -v` deletes it). Seed data comes only from the volume —
+# data/ is gitignored and never baked into the image.
+
+services:
+  backend:
+    build: .
+    env_file:
+      - .env
+    environment:
+      DATA_DIR: /data
+    volumes:
+      - zqc-data:/data
+    ports:
+      - "8000:8000"
+
+  frontend:
+    build:
+      context: ./frontend
+      args:
+        VITE_API_URL: ${VITE_API_URL:-http://localhost:8000}
+    ports:
+      - "8080:80"
+    depends_on:
+      - backend
+
+volumes:
+  zqc-data:
diff --git a/frontend/Dockerfile b/frontend/Dockerfile
new file mode 100644
index 0000000..8d22050
--- /dev/null
+++ b/frontend/Dockerfile
@@ -0,0 +1,22 @@
+FROM node:20-alpine AS builder
+
+WORKDIR /srv/frontend
+
+COPY package.json package-lock.json ./
+RUN npm ci
+
+COPY . .
+
+ARG VITE_API_URL=http://localhost:8000
+ENV VITE_API_URL=$VITE_API_URL
+
+RUN npm run build
+
+FROM nginx:alpine
+
+COPY --from=builder /srv/frontend/dist /usr/share/nginx/html
+COPY nginx.conf /etc/nginx/conf.d/default.conf
+
+EXPOSE 80
+
+CMD ["nginx", "-g", "daemon off;"]
diff --git a/frontend/nginx.conf b/frontend/nginx.conf
new file mode 100644
index 0000000..3aa17e6
--- /dev/null
+++ b/frontend/nginx.conf
@@ -0,0 +1,11 @@
+server {
+    listen 80;
+    server_name _;
+
+    root /usr/share/nginx/html;
+    index index.html;
+
+    location / {
+        try_files $uri $uri/ /index.html;
+    }
+}
+```
