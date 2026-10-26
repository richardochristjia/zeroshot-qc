# M2 verify — feat/zeroshot-qc-m2 (2026-10-26)

Single-pass verification. Nothing failed; no fix commit needed.

## 1. pytest (run once)

`cd backend && .venv/bin/python -m pytest -q`

- **95 passed**, 2 warnings (pre-existing: starlette BlockingPortal deprecation, one RLE size-mismatch UserWarning in test_smoke), 0.68s.

## 2. CLI inspect (real process, placeholder image)

`backend/.venv/bin/python cli.py inspect /tmp/zqc_verify_part.png --profile bottle --no-judge --fake`
(128x96 gray PNG generated with PIL; `--fake` because no `.env`/API keys exist — see §5.)

Output, exit=0:

```text
d1 broken bottle glass score=0.94 area_px=480 length_px=29.0 area_mm2=4.80 length_mm=2.90
d2 chip on bottle score=0.77 area_px=583 length_px=52.0 area_mm2=5.83 length_mm=5.20
d3 contamination stain score=0.74 area_px=1596 length_px=41.0 area_mm2=15.96 length_mm=4.10
overlay: /Users/167560.KEVIN/orca/projects/Zeroshot QC/data/runs/cli/zqc_verify_part_overlay.png
```

- 3 detection lines + `overlay:` line; overlay file verified on disk (3683 bytes).
- NOTE: system `python3` lacks PIL — venv python is required for `cli.py`.

## 3. smoke.py --fake shape check

`cd backend && .venv/bin/python scripts/smoke.py --fake`, exit=0:

```text
placeholder_1: scratch=1, crack=1, dent=1
placeholder_2: scratch=1, crack=1, dent=1
placeholder_3: scratch=1, crack=1, dent=1
verdict: {"verdict":"PASS","confidence":0.9,...}
```

- 3 count lines + 1 `verdict:` line (PASS, fake judge, 3 rulings).

## 4. grep guard (hardcoded model IDs / endpoints / keys)

Pattern over `cli.py` + `backend/app/pipeline/`: `sk-…`, `api_key="…"`, `http(s)://*.com|ai|io|net`,
`bearer …`, `muse-*`, `gpt-*`, `model_id="…"` → **GUARD_CLEAN, no hits**.

Model IDs reach adapters only via settings:

- `backend/app/pipeline/wiring.py:27` → `settings.sam_model_id`
- `backend/scripts/smoke.py:47` → `settings.judge_model_id`

## 5. real-mode error contract (no keys configured)

Same CLI without `--fake` → exit=1, clean stderr, no traceback:

```text
error: SAM adapter is not configured: META_API_KEY, META_API_BASE_URL and SAM_MODEL_ID must all be set.
```

## verdict

M2 verify: PASS. 95 tests, CLI 3 detections + overlay, smoke 3+1 lines, guard clean.
