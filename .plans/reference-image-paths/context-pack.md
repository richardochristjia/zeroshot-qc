# Context pack

BASE: main
CHANGED: 27 files, +147/-27

## What this change does
Reference image paths become relative to `settings.data_dir`. Backend gets one resolver (`resolve_reference_path`, `backend/app/pipeline/inspect.py:116`) used by inspect and synth. Frontend gets `referenceImageUrl` (`frontend/src/api.ts:503`) mapping a path to `<API_BASE>/files/<path>`. The 16 profiles now set `reference_image` to `mvtec/<cat>/train/good/000.png`.

## Files
- `backend/app/pipeline/inspect.py` — adds `resolve_reference_path` (:116); `_load_reference_image` (:124) opens the resolved path
- `backend/app/synth/generate.py:62` — `load_good_image` uses the resolver; fixture fallback kept when file missing
- `backend/profiles/*.json` (16) — one-line `reference_image` change, null -> `mvtec/<cat>/train/good/000.png`
- `frontend/src/api.ts:503` — `referenceImageUrl`
- `frontend/src/pages/Inspect.tsx:211` — uses it; `refTitle` splits "not set" vs "not found: <path>"
- `frontend/src/pages/Profiles.tsx:375` — thumbnail uses it; hint text (:360)
- Tests: `backend/tests/test_judge.py` (+50), `test_synth.py` (+21), `test_profiles_reference.py` (new), `test_fake_flag.py` and `test_routers.py` (+3 each, create the screw reference file in tmp data_dir), `frontend/src/url-join.test.ts`

## API contracts
- `GET /files/{path relative to data_dir}` → 200 file; mounted `backend/app/main.py:38`. `/data/...` is 404.
- `PUT /api/profiles/{id}` — rejects absolute or `..` `reference_image` with 422 (`_is_unsafe_reference`, `backend/app/routers/profiles.py:21`, unchanged).
- `ProductProfile.referenceImage: string | null` declared `frontend/src/api.ts:61`, parsed from `reference_image` at :342.

## Test entry points
- `cd backend && .venv/bin/python -m pytest` (bare `.venv/bin/pytest` fails collection, pre-existing); focused: `tests/test_judge.py tests/test_synth.py tests/test_profiles_reference.py tests/test_routers.py tests/test_fake_flag.py`
- `cd frontend && npm test && npm run build` (`src/url-join.test.ts`)

## Acceptance criteria
1. A relative reference path opens from `settings.data_dir` for both inspect and synth, independent of CWD (pytest 1, 2, 5).
2. Absolute paths still load; missing relative path raises `ValueError` naming the path (pytest 3, 4).
3. All 16 committed profiles' `reference_image` exists under data_dir (pytest 7, skips without dataset).
4. `referenceImageUrl("mvtec/a.png")` returns `<API_BASE>/files/mvtec/a.png` (vitest 6).
5. Inspect panel: "No reference set for this profile" only when path empty; "Reference image not found: <path>" on load failure (code review of `Inspect.tsx`).
6. PUT with absolute or `..` reference still 422 (`test_put_absolute_reference_image_rejected`).
7. Backend pytest, `npm test`, `npm run build` pass.
8. manual: start backend and frontend, open Inspect, pick Bottle; Reference panel shows good bottle image; repeat with Cable; Profiles thumbnail shows (needs real dataset and servers).

## Do not re-derive
- Before: inspect opened the path relative to process CWD, synth relative to repo root; the browser requested `data/mvtec/...` (404) because `resolveFileUrl` only prepends `API_BASE`.
- `settings.data_dir` resolves against repo root (`backend/app/config.py:35`); `backend/data/mvtec` duplicate is untouched user data, no longer read.
- Plan said profiles held `data/mvtec/...`; on main they were all `null` (see plan.md divergence).
- Eval builds profiles with `reference_image=None` (`backend/app/eval/run.py:63`), unaffected.
- `inspect.py` now imports `app.config`, and `synth/generate.py` imports `app.pipeline.inspect`; check for import cycles if reviewing.
- Last recorded run: pytest 192 passed via `python -m pytest` (risks.md).

## Diff (source only; profile JSON and test files omitted, see Files)
```diff
--- a/backend/app/pipeline/inspect.py
+from app.config import settings
+def resolve_reference_path(path: str) -> Path:
+    """Absolute paths pass through; relative ones resolve under data_dir."""
+    candidate = Path(path)
+    return candidate if candidate.is_absolute() else Path(settings.data_dir) / candidate
 def _load_reference_image(path: str) -> Image.Image:
-        with Image.open(path) as raw:
+        with Image.open(resolve_reference_path(path)) as raw:
--- a/backend/app/synth/generate.py
+from app.pipeline.inspect import resolve_reference_path
     if profile.reference_image:
-        candidate = Path(profile.reference_image)
-        if not candidate.is_absolute():
-            candidate = BACKEND_DIR.parent / candidate
+        candidate = resolve_reference_path(profile.reference_image)
--- a/frontend/src/api.ts
+export function referenceImageUrl(path: string): string {
+  return resolveFileUrl(`/files/${path}`);
+}
--- a/frontend/src/pages/Inspect.tsx
-import { ApiError, inspectImage, listProfiles, resolveFileUrl } from '../api.ts'
+import { ApiError, inspectImage, listProfiles, referenceImageUrl, resolveFileUrl } from '../api.ts'
-  const refUrl = profile?.referenceImage ? resolveFileUrl(profile.referenceImage) : null
+  const refUrl = profile?.referenceImage ? referenceImageUrl(profile.referenceImage) : null
+  const refTitle = refUrl === null ? 'No reference set for this profile' : `Reference image not found: ${profile?.referenceImage}`
-    <EmptyState icon="file" title="No reference set for this profile" className="m-3" />
+    <EmptyState icon="file" title={refTitle} className="m-3" />
--- a/frontend/src/pages/Profiles.tsx
-import { resolveFileUrl } from '../api.ts'
+import { referenceImageUrl } from '../api.ts'
-hint="Path; blank = none"
+hint="Path under data/; blank = none"
-src={resolveFileUrl(draft.referenceImage)}
+src={referenceImageUrl(draft.referenceImage)}
```
