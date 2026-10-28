# Reference image paths relative to data/ (Tier M)

## Problem

The Inspect page Reference panel shows nothing. `frontend/src/pages/Inspect.tsx:211` builds the `<img src>` with `resolveFileUrl(profile.referenceImage)`, which only prepends `API_BASE`, so the browser requests `data/mvtec/...`. The backend serves dataset files only under `/files/<path relative to data_dir>` (`backend/app/main.py:38`). Probe: `curl :8000/files/mvtec/bottle/train/good/000.png` → 200; `curl :8000/data/mvtec/...` → 404. The `onError` fallback then shows "No reference set for this profile", which hides the real cause. The Profiles editor thumbnail (`frontend/src/pages/Profiles.tsx:375`) has the same bug. Separately, the backend resolves the path against different bases: inspect opens it relative to the process CWD (`backend/app/pipeline/inspect.py:115`, `_load_reference_image`), synth against the repo root (`backend/app/synth/generate.py:62`, `load_good_image`). Inspect only works because a duplicate dataset sits at `backend/data/mvtec`.

## Solution

- Convention: `ProductProfile.reference_image` is a path relative to `settings.data_dir` (e.g. `mvtec/bottle/train/good/000.png`). Absolute paths still load on the backend (existing tests use them); PUT keeps rejecting absolute and `..` paths (`_is_unsafe_reference`, `backend/app/routers/profiles.py:21`, unchanged).
- One backend helper resolves a reference path: absolute → as-is; relative → `Path(settings.data_dir) / path`. Inspect and synth both use it. Synth keeps its fixture fallback when the resolved file is missing.
- Frontend helper in `frontend/src/api.ts` maps a reference path to `resolveFileUrl(`/files/${path}`)`. Inspect and Profiles use it.
- Inspect panel: empty path → "No reference set for this profile"; load failure → "Reference image not found: <path>".
- Profiles field hint: "Path under data/; blank = none".

## Files

- `backend/app/pipeline/inspect.py` — add `resolve_reference_path(path: str) -> Path` (imports `settings` from `app.config`); `_load_reference_image` opens the resolved path; error message keeps naming the original path.
- `backend/app/synth/generate.py` — `load_good_image` uses `resolve_reference_path` instead of `BACKEND_DIR.parent / candidate`.
- `backend/profiles/*.json` (16 files) — `reference_image` value `data/mvtec/<cat>/train/good/000.png` → `mvtec/<cat>/train/good/000.png`; one-line change each, keep file layout (some files are single-line JSON).
- `frontend/src/api.ts` — add exported `referenceImageUrl(path: string): string`.
- `frontend/src/pages/Inspect.tsx` — use `referenceImageUrl`; split the empty state into "not set" vs "not found: <path>".
- `frontend/src/pages/Profiles.tsx` — thumbnail uses `referenceImageUrl`; hint text update.
- `backend/tests/test_judge.py` — relative-path tests (data_dir monkeypatched to tmp_path).
- `backend/tests/test_synth.py` — synth uses relative profile reference.
- `backend/tests/test_profiles_reference.py` (new) — every committed profile's reference exists under data_dir; skip when dataset absent.
- `frontend/src/url-join.test.ts` — `referenceImageUrl` cases.
- `.agents/RECORD.md` — one entry (end of run).

## Acceptance criteria

1. A relative reference path opens from `settings.data_dir` for both inspect and synth, independent of CWD — check: pytest cases 1, 2, 5.
2. Absolute paths still load; missing relative path raises `ValueError` naming the path — check: pytest cases 3, 4.
3. All 16 committed profiles' `reference_image` exists under data_dir — check: pytest case 7 (skips without dataset).
4. `referenceImageUrl("mvtec/a.png")` returns `<API_BASE>/files/mvtec/a.png` — check: vitest case 6.
5. Inspect panel text: "No reference set for this profile" only when the path is empty; "Reference image not found: <path>" on load failure — check: code review of `Inspect.tsx`.
6. PUT with absolute or `..` reference still returns 422 — check: existing `test_put_absolute_reference_image_rejected`.
7. `cd backend && .venv/bin/pytest` and `cd frontend && npm test` and `npm run build` pass.
8. manual: start backend (`cd backend && .venv/bin/uvicorn app.main:app --port 8000`) and frontend (`cd frontend && npm run dev`), open Inspect, pick Bottle — the Reference panel shows the good bottle image; repeat with Cable; open Profiles and see the thumbnail.

## Risks

- `settings.data_dir` resolves against the repo root (`backend/app/config.py:35`); in Docker it is `/data`, so the dataset must be mounted there — if not, inspect raises `could not open reference image`. Out of scope to change mounts.
- Test monkeypatching: `settings` is a module singleton; patch `settings.data_dir` via `monkeypatch.setattr(settings, "data_dir", str(tmp_path))` — `object.__setattr__` may be needed if the model is frozen.
- Duplicate `backend/data/mvtec` stays (user data, gitignored); do not delete it.
- Eval builds its own profiles with `reference_image=None` (`backend/app/eval/run.py:63`) — unaffected.

## Test plan

| # | Case | Expect | File |
|---|------|--------|------|
| 1 | Relative path, CWD = backend/ | opens file under data_dir | test_judge.py |
| 2 | Relative path, CWD = repo root (monkeypatch.chdir) | same file | test_judge.py |
| 3 | Absolute path (existing tests) | still opens | test_judge.py |
| 4 | Missing relative path | ValueError naming path | test_judge.py |
| 5 | Synth with relative profile reference | uses profile image, not fixture | test_synth.py |
| 6 | `referenceImageUrl("mvtec/a.png")` | `<API_BASE>/files/mvtec/a.png` | url-join.test.ts |
| 7 | Every committed profile | reference exists under data_dir (skip if absent) | test_profiles_reference.py |

Commands: `cd backend && .venv/bin/pytest`; `cd frontend && npm test && npm run build`.

## Divergence (context-pack)
- On `main` all 16 committed profiles had `reference_image: null`, not `data/mvtec/...`; the branch sets them to `mvtec/<cat>/train/good/000.png` (new value, not a rewrite). Tests in test_fake_flag.py / test_routers.py gained a tmp reference file because the screw profile now points at one.
