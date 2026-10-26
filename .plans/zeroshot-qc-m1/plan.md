# ZeroShot QC — M1: Scaffold + Adapters

Tier L (estimate: 14 source files, server API, greenfield). Loop and steps are in `tier.md` next to this file.

## Problem

Small factories inspect by eye because automated inspection needs thousands of labeled photos per product. ZeroShot QC claims zero-training inspection: SAM 3.1 segments candidate defects from text prompts, Muse Spark judges them against plain-English rules and a known-good reference, Muse Image generates synthetic test data. The workspace is empty (one initial commit, no code, no `.agents/RECORD.md`), and the whole claim rests on one unproven assumption — that SAM 3.1 text prompts can find small industrial defects (ROADMAP Day-1 risk check). M1 exists to prove the plumbing and surface that risk as early as possible.

## Solution

Scaffold the HANDOFF §4 layout (backend only in M1; frontend arrives at M6), implement the §6 schemas verbatim, and build the three adapter protocols (§5) with two implementations each: a real Meta HTTP adapter whose request shape is isolated in one module so it can be corrected the moment official docs arrive, and a deterministic fake for tests. A disk cache keyed by `sha256` of inputs (§2) wraps every model call from day one, so eval reruns never re-pay. `/api/health` reports configured model IDs without leaking keys. `scripts/smoke.py` runs the adapters over 3 MVTec images and reports per-category mask counts — the Day-1 risk signal.

## Phases

1. **Scaffold.** Repo layout per HANDOFF §4 (backend subtree), `.env.example` (§11), `.gitignore` for `data/` and keys, pinned deps (FastAPI, Pydantic v2, Pillow, numpy, opencv-headless, pycocotools), README stub noting MVTec CC BY-NC-SA 4.0.
2. **Schemas + config.** §6 Pydantic models verbatim in `schemas.py`; `config.py` via pydantic-settings reading `.env` — model IDs never hardcoded (§2).
3. **Adapters.** `Segmenter` / `Judge` / `ImageGenerator` protocols (§5); real HTTP adapters with the Meta request/response mapping isolated in one place per adapter; deterministic fakes in `fakes.py`.
4. **Cache.** `pipeline/cache.py`: disk cache keyed by `sha256(image bytes + prompts + model id)`; a hit must not call the adapter.
5. **Health + smoke.** `GET /api/health` (status + configured model IDs, no secrets); `scripts/smoke.py` runs SAM over 3 MVTec images × 3 prompts, saves overlays, prints counts; calls the judge once and validates JSON against `Verdict`.
6. **Data step.** Documented MVTec download into `data/mvtec/` (manual, license-gated); smoke degrades to a clear “data missing” message, never a stack trace, when absent.
7. **Record.** Bootstrap `.agents/RECORD.md` (see Record Updates in Verification) as the last task, verified against what was actually built.

## Acceptance Criteria

1. `GET /api/health` returns 200 with status and the model IDs from `.env` (empty strings when unset — never a key). Check: `test_health.py`.
2. `python scripts/smoke.py` with fakes enabled completes on any 3 images, saves overlays, and prints per-prompt mask counts. Check: smoke run in Verification.
3. Judge fake returns output that validates against `Verdict` on the first attempt. Check: `test_adapters.py`.
4. Second identical smoke run is served from cache (adapter call count does not increase). Check: `test_cache.py`.
5. `pytest` is green; no model ID, endpoint, or key appears anywhere in source. Check: full `pytest` + grep guard in Verification.
6. `manual:` with real keys + official docs pasted in, smoke prints real SAM mask counts for 3 MVTec images — the Day-1 risk readout (works / weak / fallback to golden-sample route per ROADMAP). Human steps: paste official Meta docs, set `.env`, download MVTec, run smoke.

## Dialectical Outcomes (Why)

- **M1 only, then stop.** The user chose M1-only over M1+M2 and the full M1–M7 build. HANDOFF §10 requires milestone gates; compounding unproven API assumptions across all milestones was rejected.
- **Fake-first adapters.** The user has no Meta keys/docs yet and HANDOFF §2 forbids guessing API details. Real HTTP adapters are still written, but the Meta request/response mapping is isolated in one place per adapter so a wrong guess costs one module. Rejected: local open-weights SAM (changes adapter + deploy shape; revisit only if the Day-1 risk check fails).
- **Cache from day one.** HANDOFF §2: every model call is cached by input hash. Building it in M1 (not M4) keeps eval reruns free and makes the cache-hit test cheap to write now.
- **Golden-sample fallback is a gate decision, not a hedge.** If SAM 3.1 is weak on defects, ROADMAP prescribes segment-the-object + Muse Spark diff against the reference. The pitch is unchanged; the decision is made at the M1 gate with real mask counts, not pre-built.
- **Record bootstrap at end of implementation.** `.agents/RECORD.md` does not exist. Entries are written last and verified against built code; a diverged entry is surfaced, never written wrong.

## Relevant Files (Where)

- `backend/app/main.py` — FastAPI app, routers, CORS; M1 mounts health only.
- `backend/app/config.py` — pydantic-settings reading `.env` (§11 keys).
- `backend/app/schemas.py` — all Pydantic models (§6), verbatim.
- `backend/app/adapters/base.py` — `Segmenter`, `Judge`, `ImageGenerator` protocols (§5).
- `backend/app/adapters/sam.py` — SAM 3.1 via Meta Model API; isolated request mapping.
- `backend/app/adapters/muse_spark.py` — Muse Spark judge + SOP parser (judge only in M1; SOP lands M5).
- `backend/app/adapters/muse_image.py` — Muse Image generator protocol implementation (exercised M5).
- `backend/app/adapters/fakes.py` — deterministic fakes for tests and fake-mode smoke.
- `backend/app/pipeline/cache.py` — disk cache keyed by `sha256` of inputs.
- `backend/app/routers/` — `inspect.py profiles.py eval.py synth.py` stubs; only health is live in M1 (health may live in `main.py`).
- `backend/scripts/smoke.py` — SAM over 3 MVTec images × 3 prompts; overlays + counts; one judge call.
- `backend/tests/test_adapters.py`, `test_cache.py`, `test_health.py` — see Test Strategies.
- `.env.example`, `.gitignore`, `README.md` (stub), `backend/requirements.txt` (or `pyproject.toml`).

## Key Code Context (What)

Schemas are HANDOFF §6 verbatim — `RawMask`, `Detection`, `ProductProfile`, `DefectRuling`, `Verdict`, `InspectionResult` with the exact fields, defaults (`min_score=0.3`), and bounds (`confidence` in [0,1]) given there. Adapter protocols are HANDOFF §5 verbatim:

```python
class Segmenter(Protocol):
    def segment(self, image: Image.Image, prompts: list[str]) -> list[RawMask]: ...

class Judge(Protocol):
    def judge(self, image, overlay, reference, detections, profile) -> Verdict: ...
    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile: ...

class ImageGenerator(Protocol):
    def add_defect(self, good_image, defect_description: str, mask=None) -> Image.Image: ...
```

Config keys are HANDOFF §11 verbatim: `META_API_KEY`, `META_API_BASE_URL`, `SAM_MODEL_ID`, `JUDGE_MODEL_ID`, `IMAGE_MODEL_ID`, `DATA_DIR`, `MVTEC_DIR`, `CORS_ORIGINS`. No endpoint path or model ID is invented; unset values stay empty and health reports them as empty.

## Implementation Algorithm (How)

1. **Config load.** `config.py` reads `.env` via pydantic-settings. Every consumer imports settings; nothing reads `os.environ` directly and nothing hardcodes a model ID.
2. **Adapter call.** Caller builds inputs → cache key `sha256(image bytes + prompts + model id)` → on hit, deserialize and return without touching the adapter → on miss, call the adapter protocol, serialize the result to `data/cache/`, return.
3. **Real adapter request.** Each real adapter maps protocol inputs to the Meta HTTP request inside a single private function (the only place that changes when official docs arrive), sends with `META_API_KEY` auth, and maps the response back to §6 schemas. Any mapping uncertainty is a `TODO(meta-docs)` comment, never a guessed constant presented as fact.
4. **Fake adapter.** Deterministic: same inputs → same outputs (seeded by input hash). The fake segmenter returns a fixed small set of `RawMask`s; the fake judge returns a `Verdict` that validates first-try.
5. **Smoke.** Load 3 images (MVTec if present, else any 3 local images; if none, exit with a clear “data missing” message) → segment with 3 prompts each via the cache → save overlay PNGs → print per-image, per-prompt counts → one judge call → validate against `Verdict` → print verdict.
6. **Health.** Return `{"status": "ok", "models": {sam, judge, image}}` from settings. The API key is never included in any response.

## Anti-Goals (Out of Scope)

- Segmentation pipeline polish, `measure.py`, overlay labeling, duplicate merge (M2).
- Judge rules engine, rule override, retry/consistency logic (M3).
- Eval harness, metrics, ablations (M4). Synthetic generation and SOP import behavior (M5) beyond protocol stubs.
- Frontend (M6), deploy (M7), conveyor video (stretch). Webcam, live rule editor.
- Training or fine-tuning any model — forbidden by HANDOFF §2.
- Guessing Meta API endpoints, request shapes, or model IDs.

## Edge Cases & Gotchas

- **Empty `.env`.** Health must still return 200 with empty model IDs; real adapters must fail with a clear “not configured” error, not a network attempt to an empty URL.
- **Missing MVTec data.** Smoke prints “data missing” guidance and exits non-zero without a traceback; fake-mode smoke on placeholder images still passes.
- **Cache poisoning.** Key must include the model id and the prompt list, not just image bytes — a prompt change is a miss (tested).
- **Secret leakage.** Health, logs, overlays, and cache files must never contain `META_API_KEY`. The grep guard covers source; the health test covers responses.
- **RLE masks.** `mask_rle` is COCO RLE (`dict`); fakes must emit a shape pycocotools accepts so M2 measure code is not blocked.
- **Python version.** Target 3.11 (HANDOFF §3); `X | None` syntax in protocols/schemas assumes it.

## Navigation Anchors

- Entry point: `backend/app/main.py` (FastAPI app factory / `app` object).
- Smoke entry point: `backend/scripts/smoke.py` `main()`.
- Swap point: `backend/app/adapters/base.py` protocols — API vs fake selection happens in one wiring function (in `main.py` or a small `deps` module), never scattered `if fake` branches.
- Cache choke point: `backend/app/pipeline/cache.py` — every model call passes through it (HANDOFF §2).

## Dependency Mappings

- Runtime: `fastapi`, `uvicorn`, `pydantic` v2, `pydantic-settings`, `python-multipart` (for later multipart routes), `numpy`, `opencv-python-headless`, `Pillow`, `pycocotools`, `httpx` (adapter HTTP).
- Tests: `pytest`, FastAPI `TestClient` (via `httpx`).
- No frontend dependencies in M1. No database in M1 (SQLite arrives with profiles/eval persistence; M1 profiles are files per HANDOFF §4 `profiles/`).

## Test Strategies

- `test_health.py`: health with empty `.env` → 200, model IDs empty, no secret fields in the JSON.
- `test_adapters.py`: fake segmenter determinism (same inputs → identical masks); fake judge output validates as `Verdict`; real adapter with unset config raises the clear not-configured error without network.
- `test_cache.py`: same inputs twice → adapter called once, identical results; changed prompt → miss, adapter called again.
- Smoke check (Verification, not a unit test): fake-mode smoke on 3 images saves overlays and prints counts; missing-data run prints guidance, no traceback.
- Grep guard (Verification): no model ID, endpoint, or key string in source outside `.env.example` placeholders.
- Run command: `cd backend && python -m pytest` (plus the smoke commands above).

## Record Updates

Written at the end of implementation, verified against the built code (see the Verification phase in `tasks.md`):

1. Create `.agents/RECORD.md` with the forge `record-preamble.md` copied verbatim as its body, followed by:

```markdown
- (pipeline) Inspection currently routes every model call through a disk cache keyed by a hash of its inputs.
- (adapters) Model access currently goes through Segmenter, Judge, and ImageGenerator protocols with fake implementations for tests.
- (config) Model IDs are currently read from environment configuration and never hardcoded.
- (data) The data directory currently holds datasets, cache, and run outputs and is excluded from version control.
```
