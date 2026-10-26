# Blast radius: feat/zeroshot-qc-m2 vs main

## What it does

M2 adds a measure → inspect → overlay pipeline (`measure.py`, `inspect.py`,
`overlay.py`), a repo-root `inspect` CLI, and five `ProductProfile` JSONs.
It rewires smoke: local tint code deleted, placeholder `bbox=(0,0,0,0)`
detections replaced by measured `Detection`s via `_masks_to_detections`
(`smoke.py:104`), overlay via `make_overlay`. No judge call added (M3).

The non-obvious part: smoke's judge input silently changes shape — real
bboxes/areas instead of zeros, and a `make_overlay` image instead of the
old local tint. Counts printed per image still come from raw masks
(`smoke.py:180-188`), so the count-line contract is untouched.

## The one fact it's safe because of

**M1 contracts are byte-identical, and every changed judge input is hashed
into the cache key — so old entries miss, never stale-hit.**

- `git diff main...HEAD -- backend/app/schemas.py backend/app/pipeline/cache.py backend/app/adapters/base.py backend/app/adapters/fakes.py backend/app/config.py` → empty. Segment cache inputs (image bytes, prompts, model id) are therefore unchanged; segment entries still hit.
- `judge_cache_key` (`cache.py:72`) frames full detection JSON + overlay PNG bytes. Real detections and the new overlay produce different keys than M1-era placeholder entries → miss → recompute, never a collision.
- Step reached: **4 (ran it)**. `/tmp/proof_impact.py` output:
  - segment key stable across calls (`f266cae603755ab4...`)
  - 3 `run_inspection` detections JSON round-trip; all `counts` text
  - placeholder vs real judge keys differ; new key deterministic
  - `PROOF PASSED`, plus `81 passed` (pytest) and smoke `--fake` keeping
    its 3-count-lines + `verdict:` shape.

## Risks

1. **Judge cache churn on first M3 run (likely, trivial).** Every old judge
   entry is now unreachable → one recompute each. Check: entry count under
   `data/cache/` grows once, then stabilizes. No action.
2. **Merged `a+b` labels hit overlay fallback tint (certain, cosmetic).**
   Lookup is on the full label string (`overlay.py:56-58`), so merged
   detections render `(255,200,0)`. M3/M6 consumers keying color off label
   should split on `+` or map explicitly.
3. **`length_px` point-span semantics (certain if misread, low).**
   Filled 100x50 rect measures `99.0`, not `100.0` (`measure.py:44`); only
   `bottle.json` sets `mm_per_px`. M6 thresholds must use these semantics.
4. **Size-mismatched RLE warn-and-skip divergence (unlikely, low).**
   `inspect.py:69` skips before merge; smoke's `_masks_to_detections`
   measures first and lets `make_overlay` skip later (`smoke.py:104`).
   Same visible outcome (no crash, warning); different warning text.
   Carried-over M1 open risk: real-SAM RLE byte-vs-text form still
   unproven against the live API.

## Cleared

- Smoke output shape: counts from pre-measurement masks; `seen_stems`
  naming, discovery, cache wiring untouched. Verified by live run.
- Segment cache: key function and inputs unchanged; CLI reuses smoke's
  `"fake-sam"` id (`cli.py:35`), so fake entries are shared, not forked.
- Profile format: JSONs validate against unchanged `ProductProfile`
  (`load_profile`, `inspect.py:26`); `min_score` default 0.3 applies to
  all five (none override it). M3 reads the same schema.
- Orchestrator reuse: `run_inspection(image, profile, segmenter)` takes
  the M1 `Segmenter` protocol (`base.py:37`); M3/M6 can wrap with
  `CachedSegmenter` unchanged. Empty masks → `[]`, exit 0.
- No secret/endpoint leakage: new source has no model IDs or keys
  (acceptance check 4; M2 only threads `settings.sam_model_id` at wiring).

## Before you merge

Cheapest catch-all: `cd backend && .venv/bin/python -m pytest -q` (81
passed) + `backend/.venv/bin/python backend/scripts/smoke.py --fake`
from root (3 count lines + `verdict:`). Rerun `/tmp/proof_impact.py`
after any cache/schema touch — it fails loud on key collision.
