# ZeroShot QC — M1 Tasks

Spec: `plan.md` in this folder. Tier: `tier.md` in this folder.

## Scaffold
- [x] Create M1-only backend layout per HANDOFF §4 as enumerated in plan Relevant Files: `backend/app/{main,config,schemas}.py`, `backend/app/adapters/`, `backend/app/pipeline/cache.py` only, `backend/app/routers/` with empty `inspect.py profiles.py eval.py synth.py` stubs (health in `main.py`), `backend/scripts/` (canonical smoke path `backend/scripts/smoke.py`), `backend/tests/`, `backend/profiles/` (empty); defer `pipeline/{inspect,measure,overlay}.py`, `prompts/`, `eval/`, `synth/`, `cli.py`, frontend to M2-M6 phases
- [x] Add Python package markers/import root so `from app.schemas import ...` works (`backend/` on path, `__init__.py` in `app/`, `adapters/`, `pipeline/`, `routers/`)
- [x] Create `.env.example` verbatim from HANDOFF §11 (8 keys: `META_API_KEY`, `META_API_BASE_URL`, `SAM_MODEL_ID`, `JUDGE_MODEL_ID`, `IMAGE_MODEL_ID`, `DATA_DIR`, `MVTEC_DIR`, `CORS_ORIGINS`)
- [x] Create `.gitignore` covering `data/`, `.env` (never `.env.example`), keys/secrets, `__pycache__/`, `.venv/`; no committed placeholders inside ignored `data/`
- [x] Create pinned deps in `backend/requirements.txt` (chosen over `pyproject.toml` for M1; full Dependency Mappings set: FastAPI, uvicorn, Pydantic v2, pydantic-settings, python-multipart, httpx, Pillow, numpy, `opencv-python-headless`, pycocotools, pytest); target Python 3.11
- [x] Pin Python 3.11 for the project (`.python-version` or equivalent note) — host default is newer, do not assume it
- [x] Create README stub noting MVTec CC BY-NC-SA 4.0 (download instructions left to Data step phase)

## Schemas + config
- [ ] Implement §6 Pydantic schemas verbatim in `backend/app/schemas.py`
- [ ] Implement `backend/app/config.py` via pydantic-settings; model IDs from `.env` only

## Adapters
- [ ] Define `Segmenter`/`Judge`/`ImageGenerator` protocols in `backend/app/adapters/base.py` (§5)
- [ ] Implement real HTTP adapters (`sam.py`, `muse_spark.py`, `muse_image.py`) with Meta mapping isolated per adapter and clear not-configured error
- [ ] Implement deterministic fakes in `backend/app/adapters/fakes.py`

## Cache
- [ ] Implement `backend/app/pipeline/cache.py` keyed by `sha256(image bytes + prompts + model id)`

## Health + smoke
- [ ] Implement `GET /api/health` (status + model IDs, never secrets)
- [ ] Implement `backend/scripts/smoke.py` (3 images × 3 prompts, overlays, counts, one validated judge call, clear data-missing path)

## Data step
- [ ] Document MVTec AD download into `data/mvtec/` (manual, CC BY-NC-SA 4.0) in README

## Verification
- [ ] `GET /api/health` returns 200 with model IDs from `.env` (empty when unset, never a key)
- [ ] Fake-mode smoke completes on 3 images, saves overlays, prints per-prompt counts
- [ ] Fake judge output validates against `Verdict` on first attempt
- [ ] Second identical run is a cache hit (adapter call count unchanged); changed prompt is a miss
- [ ] `pytest` green; grep guard finds no model ID/endpoint/key in source
- [ ] Record Updates: (1) review the complete implementation; (2a) if it matches the planned Record Updates in `plan.md`, write those exact entries into `.agents/RECORD.md` (bootstrapping the file with the forge preamble verbatim); (2b) if the implementation diverged, do not write a wrong entry — surface the divergence in the final summary instead

## Manual checks
- [ ] manual: with real keys + official Meta docs pasted in and MVTec downloaded, run `python scripts/smoke.py` — confirm real SAM mask counts print for 3 MVTec images (Day-1 risk readout: works / weak / golden-sample fallback)
