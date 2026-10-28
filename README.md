# ZeroShot QC

Zero-training visual inspection: SAM 3.1 segments candidate defects from text prompts, Muse Spark judges them against plain-English rules and a known-good reference, and Muse Image generates synthetic test data.

> Requires Python 3.11 (pinned in `.python-version`). Model IDs and API keys are read from `.env` (see `.env.example`); never hardcode them.

## Data & licensing

This project uses the [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) dataset for evaluation. MVTec AD is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (non-commercial, share-alike). Do not redistribute the dataset. To download it, open the official [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) page in a web browser, accept the CC BY-NC-SA 4.0 terms on the site, and download the archive manually — there is no direct or scripted (`curl`/`wget`) download URL.

Extract the archive into the repo-root `data/mvtec/` directory (the default `MVTEC_DIR` from `.env.example`, resolved from the repo root; set `MVTEC_DIR` in `.env` to override it) so its category folders sit directly under `data/mvtec/`. `data/mvtec/` is the canonical dataset location, not the only path smoke can read. Smoke needs at least 3 `*.png`/`*.jpg`/`*.jpeg` images anywhere beneath `data/mvtec/` — discovery is recursive.

Verify with `cd backend && python scripts/smoke.py --fake` (needs no dataset or keys). The real run, `cd backend && python scripts/smoke.py`, additionally needs the dataset present plus `.env` keys (see `.env.example`).

`data/` is gitignored — never commit images, cache, or keys.

## Prerequisites

- Python 3.11 (`python3.11 --version`; pinned in `.python-version`)
- Node 18+ (`node --version`) with npm
- Docker with the daemon running (`docker info` must succeed)
- No API keys are needed for a fake-adapter local run. Real SAM 3.1 / Muse Spark / Muse Image calls need the keys below.

## Setup

```sh
cp .env.example .env
```

Fill in `.env` (all 8 keys; empty values keep local/fake defaults):

| Key | What it is |
|---|---|
| `META_API_KEY` | Meta Model API key |
| `META_API_BASE_URL` | Meta Model API base URL |
| `SAM_MODEL_ID` | SAM 3.1 model id (from Meta docs) |
| `JUDGE_MODEL_ID` | Muse Spark model id (from Meta docs) |
| `IMAGE_MODEL_ID` | Muse Image model id (from Meta docs) |
| `DATA_DIR` | Data dir (`./data` local; `/data` in the container) |
| `MVTEC_DIR` | MVTec AD location (`./data/mvtec`) |
| `CORS_ORIGINS` | Allowed browser origins, comma-separated (`http://localhost:5173` local) |

## Run locally

Backend (from `backend/`, serves on `:8000`):

```sh
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
curl localhost:8000/api/health
```

(Skip the first two lines if `.venv` already exists.) Use the venv's
`uvicorn` — a system-wide `uvicorn` may resolve mismatched packages.

Frontend (dev proxy: same-origin `/api` + `/files` → `localhost:8000`, so no `VITE_API_URL` is needed in dev):

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The backend must be running on `:8000` alongside it.

Production frontend build (needs `VITE_API_URL` — the backend origin; trailing slashes are stripped once in `frontend/src/api.ts`):

```sh
cd frontend
VITE_API_URL=http://localhost:8000 npm run build
```

## Run with Docker

Image layout: `python:3.11-slim`, installs `backend/requirements.txt`, copies `backend/`, serves `uvicorn app.main:app` on `8000` (see `Dockerfile`). Configuration is environment-only — `.env`, keys, and `data/` are excluded by `.dockerignore` and never baked into layers. `DATA_DIR=/data` is the in-container default; mount a host dir there at run time.

```sh
docker build -t zeroshot-qc .
mkdir -p /tmp/zqc-data
docker run --rm -p 8000:8000 \
  -v /tmp/zqc-data:/data \
  -e DATA_DIR=/data \
  -e CORS_ORIGINS=http://localhost:5173 \
  -e USE_FAKE_ADAPTERS=true \
  zeroshot-qc
```

`USE_FAKE_ADAPTERS=true` serves the fake segmenter/judge for `/api/inspect` only (no keys needed); synth, eval, and from-sop keep their own adapter paths regardless. Unset it defaults to the real adapters. Prove the container:

```sh
curl localhost:8000/api/health
curl -i -H 'Origin: http://localhost:5173' localhost:8000/api/health  # access-control-allow-origin echoed
curl -o /dev/null -w '%{http_code}\n' localhost:8000/files/../outside.txt  # 404 traversal block
```

Fake inspect through the container (profile `screw` ships inside the image; any PNG/JPG works — substitute your own file for `probe.png` if you have one):

```sh
python3 -c "import struct,zlib
def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
ihdr=struct.pack('>IIBBBBB',8,8,8,2,0,0,0)
raw=b''.join(b'\x00'+bytes([200,200,200]*8) for _ in range(8))
open('/tmp/zqc-data/probe.png','wb').write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',ihdr)+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))"
curl -s -F 'image=@/tmp/zqc-data/probe.png;type=image/png' \
  -F 'profile_id=screw' localhost:8000/api/inspect | head -c 300
```

## Run everything with a single command

`docker-compose.yml` (repo root) runs the whole app prod-like: backend on `8000`, nginx frontend on `8080`.

```sh
cp .env.example .env   # required: compose reads .env and fails without it
docker compose up --build
```

Then open `http://localhost:8080` (backend health: `curl localhost:8000/api/health`).

Notes:

- `.env` must list the composed frontend origin in `CORS_ORIGINS`, e.g. `CORS_ORIGINS=http://localhost:5173,http://localhost:8080`, or the page's API calls fail.
- Keyless demo: set `USE_FAKE_ADAPTERS=true` in `.env`, then the fake `/api/inspect` probe above works through compose unchanged.
- `VITE_API_URL` bakes into the frontend at build time (default `http://localhost:8000`); changing the backend origin needs `docker compose build frontend`, not just `up`.
- Data persists in the `zqc-data` volume across `down`/`up` (`down -v` deletes it).
- Stop the dev servers (`uvicorn :8000`, Vite) first if the host ports are taken.

## Push to a public URL (human steps — need YOUR logins; never run by automation)

Backend → Modal:

```sh
pip install modal
modal setup
modal deploy modal_app.py
```

`modal_app.py` (repo root) imports the same `app` object the container serves (`backend/app/main.py`); it contains no app logic. Note the backend URL it prints — that is the `VITE_API_URL` below.

Frontend → Vercel (from the repo root; `vercel.json` already sets the build command and output dir):

```sh
npm i -g vercel
vercel login
vercel env add VITE_API_URL production
vercel --prod
```

When `vercel env add` prompts, paste the Modal backend URL (e.g. `https://<you>--zeroshot-qc.modal.run`). Then confirm the public URL in a private browser window. If the installed CLIs spell a flag differently, follow their `--help` — these commands were written without the CLIs present.

## Submission checklist state (M7)

Source: the hackathon `ROADMAP.md` submission checklist. State as of this README rewrite:

- [ ] Public URL works in a private window — NOT DONE. Commands above; needs human `modal deploy` + `vercel --prod` with human logins.
- [ ] Demo video uploaded and link tested — NOT DONE. Out of scope for this repo change.
- [~] README: problem, architecture diagram, models used, metrics table, how to run — PARTIAL. Run/deploy rewritten here (verified below); problem + models at the top of this file; MVTec license below; eval numbers live in `docs/EVAL_NOTES.md`. Still missing: an architecture diagram and a metrics table in this file.
- [x] MVTec AD license noted (CC BY-NC-SA 4.0, non-commercial) — DONE (`Data & licensing` above).
- [x] No API keys in the repo — DONE (`.env` and `data/` gitignored; `.dockerignore` keeps both out of the image; `frontend/dist/` bundle grep clean per the M7 Phase 2 verification).
- [ ] Submitted before 5 PM ET Nov 4 — NOT DONE. Submission-day step.

Reader test (this section was verified verbatim up to the credential boundary): `cp .env.example .env`, backend venv `uvicorn` + `/api/health`, frontend `npm run dev` + page/proxy fetch, `docker build` + `docker run` with the flags above + health/CORS-trace/traversal/inspect probes, `VITE_API_URL=... npm run build`. Stopped at `modal setup` / `vercel login`: neither CLI is installed here, and both need human credentials — those two commands were not run.
