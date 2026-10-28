## Backend
- [x] Add `resolve_reference_path` in `backend/app/pipeline/inspect.py` and use it in `_load_reference_image`
- [x] Use `resolve_reference_path` in `load_good_image` (`backend/app/synth/generate.py`), keep fixture fallback
- [x] Change all 16 `backend/profiles/*.json` reference_image values to `mvtec/<cat>/train/good/000.png`, one-line diff each

## Frontend
- [x] Add exported `referenceImageUrl` in `frontend/src/api.ts`
- [x] Inspect.tsx: use `referenceImageUrl`; "No reference set" only when empty, "Reference image not found: <path>" on load failure
- [x] Profiles.tsx: thumbnail uses `referenceImageUrl`; hint "Path under data/; blank = none"

## Tests
- [x] test_judge.py: relative path from backend/ and repo-root CWD, missing relative path raises ValueError
- [x] test_synth.py: synth uses relative profile reference
- [x] New test_profiles_reference.py: every committed profile reference exists under data_dir, skip if dataset absent
- [x] url-join.test.ts: `referenceImageUrl` cases

## Verification
- [x] AC1: relative path opens from data_dir for inspect and synth regardless of CWD
- [x] AC2: absolute paths still load; missing relative path raises ValueError naming the path
- [x] AC3: all 16 profile references exist under data_dir
- [x] AC4: `referenceImageUrl("mvtec/a.png")` returns `<API_BASE>/files/mvtec/a.png`
- [x] AC5: Inspect panel shows "not set" only for empty path, "not found: <path>" on load failure
- [x] AC6: PUT with absolute or `..` reference still returns 422
- [x] AC7: `cd backend && .venv/bin/pytest`, `cd frontend && npm test && npm run build` pass
- [x] Record Updates: (1) review the complete implementation; (2a) if it matches, append to `.agents/RECORD.md` exactly: `- (profiles) Profile reference_image paths are currently resolved relative to the data directory and served to the frontend under /files/.`; (2b) if the implementation diverged, do not write the entry — surface the divergence in the final summary

## Manual checks
- [ ] Run backend + frontend dev servers, open Inspect, pick Bottle and Cable: Reference panel shows the good image; Profiles thumbnail shows it
