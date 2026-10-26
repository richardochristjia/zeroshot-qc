# M1 Verify — feat/zeroshot-qc-m1

Date: 2026-10-26
Branch: `feat/zeroshot-qc-m1`

## 1. Pytest (run once)

Command: `cd backend && .venv/bin/python -m pytest -q`

```
62 passed, 1 warning in 0.45s
```

Warning: `starlette/testclient.py:40 DeprecationWarning: anyio.abc.BlockingPortal alias deprecated` — pre-existing, unrelated to M1 code.

Result: **PASS**

## 2. Live health check

Method: threaded `uvicorn.Server` on `127.0.0.1:18923`, `urllib` GET `/api/health`, then `should_exit`.

Response:

```json
{"status":"ok","models":{"sam":"","judge":"","image":""}}
```

Empty model strings are expected — no `.env` configured in this checkout; `config.py` defaults are `""` and health echoes settings verbatim. Server stopped cleanly (`stopped`).

Result: **PASS**

## 3. Fake smoke

Command: `cd backend && .venv/bin/python scripts/smoke.py --fake`

```
placeholder_1: scratch=1, crack=1, dent=1
placeholder_2: scratch=1, crack=1, dent=1
placeholder_3: scratch=1, crack=1, dent=1
verdict: {"verdict":"PASS","confidence":0.9,"rulings":[{"detection_id":"d1","is_real_defect":false,"rule_violated":null,"reason":"Fake judge: no rule violation found for this candidate."},{"detection_id":"d2","is_real_defect":false,"rule_violated":null,"reason":"Fake judge: no rule violation found for this candidate."},{"detection_id":"d3","is_real_defect":false,"rule_violated":null,"reason":"Fake judge: no rule violation found for this candidate."}],"missed_defects":[],"summary":"Fake judge: all candidates dismissed, part passes."}
```

Overlays on disk (3):

- `data/runs/smoke/placeholder_1_overlay.png`
- `data/runs/smoke/placeholder_2_overlay.png`
- `data/runs/smoke/placeholder_3_overlay.png`

Result: **PASS** — 3 overlays + verdict line present.

## 4. Grep guard — hardcoded model IDs / endpoints / keys

Scope: `backend/app` + `backend/scripts` (`*.py`).

- Pattern `sam-vit|facebook/sam|gpt-|claude-|sk-…|api_key="…"|https://api.…`: **no matches**.
- Secrets pattern `sk-|AKIA|ghp_|BEGIN PRIVATE|password=|secret=`: **clean**.
- All model IDs / base URL flow through `app/config.py:Settings` (`meta_api_key`, `meta_api_base_url`, `sam_model_id`, `judge_model_id`, `image_model_id`, all default `""`, sourced from repo-root `.env` via `pydantic-settings`). Adapters call `require_configured()` in `app/adapters/base.py` and read `settings.*` — no literals.
- Only `http` literals are `httpx` imports/calls and the `https` scheme check; `cors_origins` default `http://localhost:5173` is a dev CORS origin, not a model endpoint.

Result: **PASS**

## 5. Lint / format

Checked: `backend/requirements.txt`, `backend/pyproject.toml` (absent), root `pyproject.toml`/`setup.cfg`/`.pre-commit-config.yaml` (all absent), `.venv/bin/{ruff,black,flake8}` (none installed).

**No lint/format tool is configured in this repo.** Nothing to run; no files reformatted.

## Fixes

None required — all checks passed on first run. No `fix(qc):` commit created.

## Summary

| Check | Result |
|---|---|
| pytest | 62 passed |
| health `/api/health` | `{"status":"ok","models":{"sam":"","judge":"","image":""}}` |
| fake smoke | 3 overlays + verdict PASS |
| grep guard | clean |
| lint/format | no tool configured |
