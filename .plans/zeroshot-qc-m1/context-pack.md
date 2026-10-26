# Context pack

BASE: main @ f6320a9 (empty initial commit; `git ls-tree -r main` is empty)
BRANCH: feat/zeroshot-qc-m1 @ a1a569c
CHANGED: 39 files, +1839/-0 (all additions; 7 commits, `git log --oneline main..HEAD`)
REPRODUCE FULL DIFF: `git diff main...HEAD` (re-run locally; not inlined below — see Diff)

## What this change does

M1 scaffold + adapters only (no inspection pipeline, no frontend): HANDOFF §6 Pydantic schemas (`backend/app/schemas.py:8`), §5 adapter protocols with real Meta HTTP adapters whose request mapping is isolated and marked `TODO(meta-docs)`, deterministic fakes, a `sha256` disk cache for segment/judge calls, `GET /api/health`, and a 3-image smoke script (`backend/scripts/smoke.py:161`). MVTec data, real Meta docs, and real-key smoke remain manual (see Acceptance criteria 6).

## Files

- `.env.example:1` — 8-key env template (`META_API_KEY`, `META_API_BASE_URL`, `SAM_MODEL_ID`, `JUDGE_MODEL_ID`, `IMAGE_MODEL_ID`, `DATA_DIR`, `MVTEC_DIR`, `CORS_ORIGINS`); the only place model-ID placeholders live.
- `.gitignore:1` — ignores `data/`, `.env`, key material, `__pycache__/`, `.venv/`; `.env.example` deliberately not ignored.
- `.python-version:1` — pins Python `3.11`.
- `README.md:1` — stub + MVTec CC BY-NC-SA 4.0 manual-download instructions into repo-root `data/mvtec/` (`README.md:9`).
- `backend/requirements.txt:1` — pinned deps: fastapi 0.115.6, pydantic 2.10.4, pydantic-settings 2.7.0, httpx, Pillow, numpy, opencv-headless, pycocotools, pytest.
- `backend/app/schemas.py:8` — all §6 models verbatim: `RawMask`, `Detection`, `ProductProfile`, `DefectRuling`, `Verdict`, `InspectionResult`.
- `backend/app/config.py:16` — pydantic-settings `Settings`; single shared instance `settings` at `backend/app/config.py:40`.
- `backend/app/main.py:8` — module-level FastAPI `app`; CORS + the only live route, `GET /api/health` at `backend/app/main.py:20`.
- `backend/app/adapters/base.py:10` — `AdapterNotConfiguredError` + `Segmenter`/`Judge`/`ImageGenerator` protocols (§5).
- `backend/app/adapters/sam.py:22` — real SAM segmenter; Meta mapping isolated in `_segment_via_meta_api` (`backend/app/adapters/sam.py:33`).
- `backend/app/adapters/muse_spark.py:22` — real Muse Spark judge; mapping in `_judge_via_meta_api` (`backend/app/adapters/muse_spark.py:44`); SOP is an M5 stub.
- `backend/app/adapters/muse_image.py:21` — real Muse Image generator; mapping in `_add_defect_via_meta_api` (`backend/app/adapters/muse_image.py:34`); unexercised in M1.
- `backend/app/adapters/fakes.py:29` — deterministic `FakeSegmenter`/`FakeJudge`/`FakeImageGenerator`; no config reads, no network.
- `backend/app/pipeline/cache.py:55` — `segment_cache_key`/`judge_cache_key`, `DiskCache`, `CachedSegmenter`, `CachedJudge`.
- `backend/app/routers/inspect.py:1`, `profiles.py:1`, `eval.py:1`, `synth.py:1` — one-line stubs, not mounted in M1; health lives in `main.py` instead.
- `backend/app/__init__.py:1`, `adapters/__init__.py:1`, `pipeline/__init__.py:1`, `routers/__init__.py:1` — package markers so `from app...` imports work with `backend/` on path.
- `backend/profiles/.gitkeep`, `backend/tests/.gitkeep` — empty placeholders.
- `backend/scripts/smoke.py:35` — smoke CLI: `SMOKE_PROMPTS`, single fake/real wiring `build_adapters` (`backend/scripts/smoke.py:46`), `main()` (`backend/scripts/smoke.py:161`).
- `backend/tests/test_adapters.py:60` — fake determinism/RLE/Verdict + not-configured-without-HTTP tests.
- `backend/tests/test_cache.py:60` — cache hit/miss/persistence + key-leak tests.
- `backend/tests/test_health.py:26` — health shape/echo/no-leak tests.
- `.plans/zeroshot-qc-m1/{plan,tasks,tier,risks}.md` + `check-1..7.md` — spec, tier, risks, phase checks; not review code, excluded from the code diff groups below.

## API contracts

- `GET /api/health` → `200 {"status":"ok","models":{"sam":"…","judge":"…","image":"…"}}`; declared at `backend/app/main.py:20`, built from shared `settings` at request time (`backend/app/main.py:25`). `META_API_KEY`/`META_API_BASE_URL` never appear (`backend/app/main.py:22`).
- Env → settings (the only config contract): `.env.example:1` keys map to snake_case fields at `backend/app/config.py:22`; key/base/model IDs default `""`, `DATA_DIR`/`MVTEC_DIR` default `./data`, `./data/mvtec`, `CORS_ORIGINS` default `http://localhost:5173` (`backend/app/config.py:27`). `.env` is repo-root-anchored (`backend/app/config.py:13`) and relative data dirs are rebased to the repo root (`backend/app/config.py:31`).
- `Segmenter.segment(image, prompts) -> list[RawMask]` at `backend/app/adapters/base.py:14`; `Judge.judge(image, overlay, reference|None, detections, profile) -> Verdict` + `sop_to_profile(...)` at `backend/app/adapters/base.py:19`; `ImageGenerator.add_defect(good_image, defect_description, mask|None) -> Image` at `backend/app/adapters/base.py:32`. Shapes: `RawMask{label,score,mask_rle:dict}` (`backend/app/schemas.py:8`), `Verdict{verdict:PASS|FAIL, confidence∈[0,1], rulings, missed_defects, summary}` (`backend/app/schemas.py:43`), `ProductProfile.min_score=0.3` (`backend/app/schemas.py:32`), `DefectRuling.rule_violated` required-but-nullable, no default (`backend/app/schemas.py:39`).
- Cache keys (disk contract): segment = `sha256` over framed `kind|PNG|prompts…|model_id` (`backend/app/pipeline/cache.py:55`); judge adds overlay PNG, reference PNG-or-`__none__`, canonical detections/profile JSON, model id (`backend/app/pipeline/cache.py:72`). Entries are `<key>.json` `model_dump` JSON, rebuilt via `model_validate` (`backend/app/pipeline/cache.py:162`, `backend/app/pipeline/cache.py:190`).
- Meta HTTP is NOT a settled contract: each real adapter POSTs `httpx.post(url=settings.meta_api_base_url, …)` with an assumed `Bearer` header and assumed payload/response shapes, all inside one private function with `TODO(meta-docs)` markers — SAM `backend/app/adapters/sam.py:40`/`backend/app/adapters/sam.py:46`, judge `backend/app/adapters/muse_spark.py:59`/`backend/app/adapters/muse_spark.py:70`, image `backend/app/adapters/muse_image.py:44`/`backend/app/adapters/muse_image.py:54`. Before any HTTP, an empty key/base/model ID raises `AdapterNotConfiguredError` (`backend/app/adapters/sam.py:26`, `backend/app/adapters/muse_spark.py:33`, `backend/app/adapters/muse_image.py:27`; type at `backend/app/adapters/base.py:10`).
- Smoke CLI: `cd backend && python scripts/smoke.py [--fake]`; `--fake` is the only flag (`backend/scripts/smoke.py:163`), real adapters are the default, selection happens once in `build_adapters` (`backend/scripts/smoke.py:46`). Output: one `<stem>: scratch=N, crack=N, dent=N` line per image (`backend/scripts/smoke.py:218`) + one `verdict: <json>` line (`backend/scripts/smoke.py:262`); overlays to `data/runs/smoke/<stem>_overlay.png` (`backend/scripts/smoke.py:200`).

## Test entry points

- `backend/tests/test_health.py:26` — health empty/echo/no-leak; run `cd backend && .venv/bin/python -m pytest tests/test_health.py -q`.
- `backend/tests/test_adapters.py:60` — fakes + not-configured guard (HTTP stubbed, `backend/tests/test_adapters.py:130`); judge-only: `cd backend && .venv/bin/python -m pytest tests/test_adapters.py -k judge -q`.
- `backend/tests/test_cache.py:60` — hit/miss/persistence/no-key-on-disk; run `cd backend && .venv/bin/python -m pytest tests/test_cache.py -q`.
- Full suite: `cd backend && .venv/bin/python -m pytest -q` (23-passed baseline noted at `.plans/zeroshot-qc-m1/tasks.md:52`; bare `python` outside `backend/.venv` is not the verifier).
- Smoke check: `cd backend && .venv/bin/python scripts/smoke.py --fake` (placeholders OK, no dataset/keys needed); rerun proxy for cache: run twice, `ls data/cache/*.json | wc -l` unchanged (`.plans/zeroshot-qc-m1/tasks.md:51`).
- Grep guard (scope `backend/app`+`backend/scripts`, `*.py` only): no `https?://` except the CORS default in `config.py`, no non-empty model-ID literals, no key/`Bearer` literals (`.plans/zeroshot-qc-m1/tasks.md:53`).

## Acceptance criteria

Verbatim from `.plans/zeroshot-qc-m1/plan.md:25` (manual: = outside automated verification):

1. `GET /api/health` returns 200 with status and the model IDs from `.env` (empty strings when unset — never a key). Check: `test_health.py`.
2. `python scripts/smoke.py` with fakes enabled completes on any 3 images, saves overlays, and prints per-prompt mask counts. Check: smoke run in Verification.
3. Judge fake returns output that validates against `Verdict` on the first attempt. Check: `test_adapters.py`.
4. Second identical smoke run is served from cache (adapter call count does not increase). Check: `test_cache.py`.
5. `pytest` is green; no model ID, endpoint, or key appears anywhere in source. Check: full `pytest` + grep guard in Verification.
6. `manual:` with real keys + official docs pasted in, smoke prints real SAM mask counts for 3 MVTec images — the Day-1 risk readout (works / weak / fallback to golden-sample route per ROADMAP). Human steps: paste official Meta docs, set `.env`, download MVTec, run smoke.

## Do not re-derive

- Config decides everything: model IDs/keys come only from the shared `settings` instance (`backend/app/config.py:40`); empty string means unset. Health reads `settings` per request (`backend/app/main.py:25`); real adapters read it at call time and raise before HTTP (`backend/app/adapters/sam.py:26`).
- Fake vs real is decided once in `build_adapters` (`backend/scripts/smoke.py:46`); fakes run under distinct cache ids `fake-sam`/`fake-judge` (`backend/scripts/smoke.py:50`) so fake entries can never be served to real adapters. Those two strings are cache discriminators, not env model IDs (`.plans/zeroshot-qc-m1/plan.md:136`).
- Only segment + judge are cached: `CachedSegmenter` (`backend/app/pipeline/cache.py:146`) and `CachedJudge` (`backend/app/pipeline/cache.py:175`) exist; `ImageGenerator` caching is deferred to M5 (`backend/app/pipeline/cache.py:17`), and `CachedJudge.sop_to_profile` delegates uncached (`backend/app/pipeline/cache.py:211`). The plan's "(pipeline) every model call" Record entry is therefore divergent — nothing was written to `.agents/RECORD.md` (`.plans/zeroshot-qc-m1/plan.md:136`).
- `MuseSparkJudge.sop_to_profile` raises `NotImplementedError` until M5 (`backend/app/adapters/muse_spark.py:40`); `FakeJudge.sop_to_profile` returns a profile with empty prompts (`backend/app/adapters/fakes.py:82`). Do not review SOP parsing.
- Fake masks: one `RawMask` per prompt, label = prompt, score ∈ [0.55, 0.95], `mask_rle` = `{"size":[H,W],"counts":<utf-8 text>}` in JSON-safe text form (`backend/app/adapters/fakes.py:44`). Real SAM `counts` form is still `TODO(meta-docs)` and may not be JSON-storable as-is (`.plans/zeroshot-qc-m1/risks.md:8`).
- Smoke detections are placeholders until M2: `bbox=(0,0,0,0)`, `area_px=0`, `length_px=0.0` (`backend/scripts/smoke.py:232`); overlay tint is smoke-local (`backend/scripts/smoke.py:142`), M2 owns `overlay.py`. Smoke image discovery: first 3 recursive images under `mvtec_dir`, else 3 under `data_dir` excluding `cache/` and `runs/smoke/` (`backend/scripts/smoke.py:95`); fewer than 3 → fake mode generates placeholders (`backend/scripts/smoke.py:112`), real mode prints data-missing guidance and exits 1 with no traceback (`backend/scripts/smoke.py:188`).
- Known-broken, not part of this change: host global `python3.11` has mixed fastapi/starlette + pycocotools-decode failures — always verify in `backend/.venv` (`.plans/zeroshot-qc-m1/risks.md:5`, `.plans/zeroshot-qc-m1/tasks.md:52`); real Meta API shapes are placeholders until official docs arrive (`.plans/zeroshot-qc-m1/risks.md:6`).

## Diff

Budget: the full diff is 39 files / +1839 lines (all additions against the empty `main`), which exceeds this pack's 3,000-token budget inline. Reproduce it exactly with `git diff main...HEAD`; `git diff --stat main...HEAD` gives:

```text
.env.example 8 | .gitignore 24 | .python-version 1 | README.md 15
backend/requirements.txt 11
backend/app/schemas.py 57 | backend/app/config.py 40 | backend/app/main.py 29
backend/app/adapters/base.py 37 | sam.py 66 | muse_spark.py 87
backend/app/adapters/muse_image.py 68 | fakes.py 109
backend/app/pipeline/cache.py 212
backend/app/routers/*.py 4×1 (stubs) | backend/app/**/__init__.py 4×1
backend/scripts/smoke.py 267
backend/tests/test_adapters.py 179 | test_cache.py 230 | test_health.py 71
.plans/zeroshot-qc-m1/*.md 11 files, 352 lines (spec/checks, not review code)
39 files changed, 1839 insertions(+), 0 deletions
```

Groups for partial review: schemas+config (`git diff main...HEAD -- backend/app/schemas.py backend/app/config.py`); adapters (`-- backend/app/adapters/`); cache (`-- backend/app/pipeline/cache.py`); health+smoke (`-- backend/app/main.py backend/scripts/smoke.py`); tests (`-- backend/tests/`). No lockfiles, generated output, or vendored code exist in this diff to drop.
