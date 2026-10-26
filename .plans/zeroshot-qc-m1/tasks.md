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
- [x] Install pinned `backend/requirements.txt` into the Python 3.11 env and confirm imported `pydantic`/`pydantic-settings` report the pinned versions (2.10.4 / 2.7.0) before writing Phase 2 code — host `python3.11` currently resolves 2.13.4 / 2.14.2 (see check-2.md)
- [x] Implement §6 Pydantic schemas verbatim in `backend/app/schemas.py` (HANDOFF §6 exactly, including `DefectRuling.rule_violated` with no default — required-but-nullable — and only `Verdict.confidence` bounded; do not add defaults or bounds)
- [x] Implement `backend/app/config.py` via pydantic-settings: snake_case string fields for the 8 §11 keys, defaults mirroring `.env.example` (key/base/model IDs empty; `DATA_DIR`, `MVTEC_DIR`, `CORS_ORIGINS` as in `.env.example`), `CORS_ORIGINS` kept as a string, one shared settings instance imported by consumers (no direct `os.environ` reads, no hardcoded IDs)
- [x] Make `.env` discovery CWD-independent in `backend/app/config.py` (resolve `.env` at the repo root regardless of repo-root vs `backend/` launch; interpret `DATA_DIR`/`MVTEC_DIR` from the repo root) so `cd backend && python -m pytest` and root launches read the same file

## Adapters
- [x] Define `Segmenter`/`Judge`/`ImageGenerator` protocols in `backend/app/adapters/base.py` verbatim from HANDOFF §5 (full argument types, `Image.Image | None` where §5 has it, image-generator mask argument with no default, PIL/schemas imports), plus one shared `AdapterNotConfiguredError` exception type in the same module for all real adapters
- [x] Implement the SAM real adapter in `backend/app/adapters/sam.py`: synchronous `httpx` call satisfying `Segmenter`; before any HTTP, raise `AdapterNotConfiguredError` when the shared settings' API key, base URL, or SAM model ID is empty (settings read at call time, never `os.environ`, never hardcoded); endpoint path, request payload, auth, image encoding, and response-to-`RawMask` parsing live inside a single private mapping function built only from settings values, every uncertain detail marked `TODO(meta-docs)` with no guessed constant presented as fact
- [x] Implement the Muse Spark judge in `backend/app/adapters/muse_spark.py`: same not-configured guard (judge model ID) and single-private-mapping-function isolation with `TODO(meta-docs)` markers for the `judge` method only; `sop_to_profile` is an explicit not-implemented stub marked for M5 (no SOP parsing behaviour in M1)
- [x] Implement the Muse Image adapter in `backend/app/adapters/muse_image.py`: same not-configured guard (image model ID) and single-private-mapping-function isolation with `TODO(meta-docs)` markers; present but unexercised in M1 (first exercised in M5), so no M1 caller or behaviour test beyond the guard
- [x] Implement deterministic fakes in `backend/app/adapters/fakes.py`: fake segmenter seeded by a hash of image bytes plus the prompt list, returning one `RawMask` per prompt labelled by that prompt with deterministic scores and mask geometry clamped to the actual image dimensions (RLE size equals image height/width, counts stored in JSON-safe text form of COCO compressed RLE that pycocotools' encoder accepts); fake judge returning a `Verdict` that validates first-try (one ruling per input detection with `rule_violated` always present even when null, confidence within [0,1], deterministic verdict/summary); fake image generator returning a deterministic same-size image; no fake reads config or touches the network
- [x] Create `backend/tests/test_adapters.py` covering: fake segmenter determinism (identical inputs give identical masks), emitted RLE acceptance by pycocotools plus structural size/counts checks, fake judge output validating against `Verdict` on the first attempt, and each real adapter with emptied settings raising `AdapterNotConfiguredError` without any HTTP call (HTTP layer stubbed/mocked to prove it)

## Cache
- [x] Implement the cache store and key builders in `backend/app/pipeline/cache.py`: a `DiskCache` rooted at an explicit directory (wiring passes `Path(settings.data_dir) / "cache"`, created on demand) storing one `<sha256>.json` file per entry with atomic writes; keys are `sha256` over length-prefixed components in fixed order (call kind, PNG image bytes, then call inputs, then the explicit model id — segment: each prompt in list order + SAM model id; judge: overlay/reference PNG bytes with a None marker, detections JSON, profile JSON + judge model id so any profile/rules edit is a miss); keys and entries never contain `META_API_KEY`, entries store only result JSON, adapter exceptions propagate uncached, and unreadable/corrupt entries count as misses
- [x] Implement protocol-shaped `CachedSegmenter` and `CachedJudge` wrappers in `backend/app/pipeline/cache.py` (inner adapter + explicit model id + `DiskCache` injected; model ids come from shared settings at wiring): on a hit, rebuild `list[RawMask]` / `Verdict` from the stored JSON via model validation without calling the inner adapter; on a miss, call the inner adapter once and store its `model_dump` JSON; `ImageGenerator` caching is deferred to M5 (unexercised in M1, returns a PIL Image needing a binary entry format)
- [x] Create `backend/tests/test_cache.py` covering: identical segment inputs twice → inner adapter called once with identical result dumps; changed prompt → miss (adapter called again); changed model id → miss; changed judge profile (rules/prompts) → miss; a hit survives a fresh wrapper/cache instance over the same directory; cache files never contain a sentinel API key

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
