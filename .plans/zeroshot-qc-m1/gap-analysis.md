# Gap analysis — ZeroShot QC M1 (Plan mode)

Branch `feat/zeroshot-qc-m1` vs `main` (9 commits, 42 files). Verified 2026-10-26: `cd backend && .venv/bin/python -m pytest -q` → 62 passed; fake smoke exit 0; real-mode smoke exit 1 with data-missing guidance, no traceback.

| ID | Criterion | Met? | Evidence |
|---|---|---|---|
| AC1 | `GET /api/health` 200, model IDs from `.env`, empty when unset, never a key | Yes | [test_health.py](backend/tests/test_health.py); [main.py](backend/app/main.py) reads shared settings at request time |
| AC2 | `python scripts/smoke.py` (fakes) completes on any 3 images, saves overlays, prints per-prompt counts | Yes | Live run: 3 `placeholder_N: scratch=1, crack=1, dent=1` lines + `verdict:` line, exit 0; 3 `*_overlay.png` in `data/runs/smoke/` |
| AC3 | Judge fake validates against `Verdict` first attempt | Yes | [test_adapters.py](backend/tests/test_adapters.py) judge tests pass; smoke round-trips via `Verdict` |
| AC4 | Second identical run served from cache (call count flat) | Yes | [test_cache.py](backend/tests/test_cache.py): identical→once, prompt/model/profile change→miss, hit survives fresh instance |
| AC5 | `pytest` green; no model ID/endpoint/key in source | Yes | 62 passed; grep guards: only whitelisted CORS default `http://localhost:5173` in [config.py:29](backend/app/config.py:29); no ID-literal or secret-pattern hits |
| AC6 | `manual:` real keys + docs → real SAM counts for 3 MVTec images (Day-1 readout) | Can't tell | Needs human: paste Meta docs, set `.env`, download MVTec. Real adapters are `TODO(meta-docs)` placeholders ([sam.py](backend/app/adapters/sam.py), [muse_spark.py](backend/app/adapters/muse_spark.py), [muse_image.py](backend/app/adapters/muse_image.py), 6 markers each) — by design, not a gap |

No F-rows: plan Anti-Goals (M2–M7) correctly absent; router stubs empty as specified.

## Record reconciliation

`.agents/RECORD.md` does not exist — correctly not written (Verification 2b). Divergence check: **real**. [cache.py:17-19](backend/app/pipeline/cache.py:17) defers `ImageGenerator` caching to M5; only `CachedSegmenter` ([cache.py:146](backend/app/pipeline/cache.py:146)) and `CachedJudge` ([cache.py:175](backend/app/pipeline/cache.py:175)) exist; `CachedJudge.sop_to_profile` delegates uncached ([cache.py:211-212](backend/app/pipeline/cache.py:211)). So planned entry 1 ("every model call") is false as written. Entries 2–4 hold (`fake-sam`/`fake-judge` at [smoke.py:50-51](backend/scripts/smoke.py:50) are cache discriminators, not env model IDs).

Proposed corrected entry 1, verbatim, for human approval (entries 2–4 unchanged from plan.md):

```markdown
- (pipeline) Inspection currently routes segment and judge model calls through a disk cache keyed by a hash of their inputs.
```

## Gaps

- None automated. No code fixes made; nothing to commit.

## Next

- Human approves the corrected Record entry above, then bootstrap `.agents/RECORD.md` (preamble verbatim + 4 entries).
- AC6 manual gate: Meta docs + keys + MVTec, then real smoke readout (works / weak / golden-sample fallback).
