# Context pack

BASE: main (M5 merged)
CHANGED: 33 files, +5477/-21 (source: 22 files, +5169/-21; rest is `.plans/` + RECORD entries)

## What this change does

M6 builds the web app: four FastAPI routers (`inspect`, `profiles`, `eval`, `synth`) plus
`/files/...` static serving from gitignored `data/` in `backend/app/main.py:42-66`, and a new
`frontend/` tree (Vite + React 19 + TS + Tailwind v4) with Inspect / Profiles / Eval / Synthetic
pages behind a typed boundary-parsed client in `frontend/src/api.ts:1-754`. One divergence from
plan/HANDOFF §8: new read-only `GET /api/synth/gallery` in `backend/app/routers/synth.py:39-80`
because no list endpoint existed (see plan.md Divergence notes).

## Files

- `backend/app/routers/inspect.py:94-160` — `POST /api/inspect`; multipart image + profile_id + optional rules → `InspectionResult` with overlay `/files/` URL + `timings_ms`; 422 double-judge-failure / undecodable image, 404 unknown profile
- `backend/app/routers/profiles.py:39-91` — GET list / GET one / PUT (atomic, validated) + relocated `POST /api/profiles/from-sop` (moved from `main.py`, path kept)
- `backend/app/routers/eval.py:37-101` — GET run list (skips dirs lacking `summary.json`) + run detail `{summary, results}` with injected `image_url|null`; 404 on missing/traversal run_id
- `backend/app/routers/synth.py:83-122` — `POST /api/synth/generate` reusing M5 `generate_pairs`; fake generator by default via `_get_image_generator`
- `backend/app/routers/synth.py:39-80` — DIVERGENCE: new `GET /api/synth/gallery` enumerating `data/synth/` as `{category, defect, image_url, mask_url|null}`, skipping `_reference.png`
- `backend/app/main.py:17-66` — mounts 4 routers; `GET /files/{rel_path}` with explicit `..`/absolute/backslash guard + resolve-containment backstop (not StaticFiles)
- `backend/app/pipeline/inspect.py:51-81` — new shared atomic `save_profile` (temp + `os.replace`) used by PUT; no save helper existed before
- `backend/tests/test_routers.py:1-333` — TestClient coverage for every route (happy path, judge-only cache hit, 422s, 404s, traversal, CLI parity, gallery grouping)
- `frontend/src/api.ts:1-754` — typed client; `unknown`-in/parsed-out boundary parsers (`api.ts:279-498`), typed errors 422/404 (`api.ts:536-559`); sole backend choke point
- `frontend/src/pages/Inspect.tsx` — upload → hoverable overlay (bbox scaled to rendered size) → verdict card; debounced rules re-post with stale-request abort
- `frontend/src/pages/Profiles.tsx` — list / edit via PUT / SOP-import draft with save-as-new confirm (page-side existence check; `save_profile` overwrites silently)
- `frontend/src/pages/Eval.tsx` — run list, per-category metrics table + F1 bar chart from same summary, clickable failures via nullable `image_url`; read-only
- `frontend/src/pages/Synthetic.tsx` — gallery grouped by category/defect via gallery endpoint
- `frontend/src/App.tsx`, `main.tsx`, `index.css`, `vite.config.ts`, `index.html`, `package.json`, `tsconfig.*` — scaffold; proxy `/api`+`/files` → `http://localhost:8000`
- `frontend/package-lock.json` — lockfile (2000 lines, excluded from Diff below)
- `backend/tests/fixtures` — none added; tests synthesize PNGs in-memory (`test_routers.py:55-59`) and isolate data/profiles to tmp dirs

## API contracts

- `POST /api/inspect` multipart(`image`, `profile_id`, `rules?`) → 200 `InspectionResult`; 422 judge-failed-twice / undecodable image; 404 unknown profile — declared in `backend/app/schemas.py:51`, `backend/app/routers/inspect.py:94`
- `GET /api/profiles` → `list[ProductProfile]` sorted by id; `GET /api/profiles/{id}` → 404 unknown — `backend/app/schemas.py:26`, `backend/app/routers/profiles.py:39-59`
- `PUT /api/profiles/{id}` body `ProductProfile` → 200; 422 body-id≠path-id or invalid body (file untouched); 404 bad path id — `backend/app/routers/profiles.py:61-79`
- `POST /api/profiles/from-sop` `{sop_text, category_name}` (min_length=1) → draft, never saves; 422 double validation failure — `backend/app/routers/profiles.py:22-24,81-91`
- `GET /api/eval/runs` → summaries of dirs having `summary.json`; `GET /api/eval/runs/{run_id}` → `{summary, results[]+image_url}` (`source` defaults `mvtec`); 404 missing/traversal — `backend/app/routers/eval.py:37-101` (untyped `dict`; row keys per `backend/app/eval/run.py:179-213`)
- `POST /api/synth/generate` `{profile_id, defect, n, seed=0}` → `{profile_id, defect, count, pairs:[{image_url, mask_url|null}]}`; 422 `n<1`; 404 unknown profile — `backend/app/routers/synth.py:32-37,83-122`
- `GET /api/synth/gallery` → `[{category, defect, image_url, mask_url|null}]`, `[]` when empty — `backend/app/routers/synth.py:39-80` (no Pydantic model)
- `GET /files/{path}` → file bytes; 404 on `..`/absolute/backslash/escape/missing — `backend/app/main.py:42-66`
- Frontend mirrors: `InspectionResult`/`ProductProfile`/`Detection`/`Verdict` in `frontend/src/api.ts:18-76`; `EvalRunSummary`/`EvalRunDetail` (`api.ts:114-130`, optional-keys-with-defaults parsing for pre-M6 summaries); `SynthGalleryItem`/`SynthGenerateResponse` (`api.ts:132-158`); callers `inspectImage` (`api.ts:605`), `listProfiles`/`getProfile`/`putProfile`/`draftProfileFromSop` (`api.ts:624-686`), `listEvalRuns`/`getEvalRun` (`api.ts:691-707`), `generateSynthetic`/`listSyntheticGallery` (`api.ts:715-739`)

## Test entry points

- `backend/tests/test_routers.py` — `cd backend && .venv/bin/python -m pytest -q` (full suite; also covers M5 `test_sop.py` path-compat for relocated from-sop)
- `cd frontend && npm run build` (`tsc -b && vite build`); guards: `grep -rE 'sk-|api[_-]?key|secret' frontend/src` (empty), `git status` shows no `data/` writes
- Walkthrough record: `.plans/zeroshot-qc-m6/walkthrough.md` (fake adapters, exact URLs/timings; e.g. rule flip FAIL→PASS, segment 1ms→0ms cache hit, total 21ms→8ms)
- No jsdom/unit suite for pages in M6 — page behavior proven by walkthrough only (plan decision)

## Acceptance criteria

1. End-to-end inspect works in the browser: upload → overlay with hoverable detections → verdict card with reasons. Check: walkthrough in Verification.
2. Editing rules flips the verdict without re-uploading (judge-only rerun, visibly fast). Check: walkthrough with timings.
3. Profiles list/edit/SOP-import round-trips; Eval shows table + chart + clickable failures; Synthetic gallery groups correctly. Check: walkthrough per page.
4. `pytest` green (TestClient router tests); frontend `tsc` + `vite build` clean; no secrets in frontend code. Check: suite + build + grep.
5. manual: full walkthrough on a second device against the dev servers (upload, rule flip, SOP import, gallery). Human steps: run backend + `npm run dev` on the host, open the Vite URL from another device on the LAN.

## Do not re-derive

- Judge-only rerun is by construction: segment cache key covers image + prompts only (`pipeline/cache.py:55-69`); `rules` override replaces only `profile.rules` (`pipeline/inspect.py:212-213`). Timings use wrapper adapters because `run_inspection` fuses both stages (`pipeline/inspect.py:117-190`).
- Fake/real selector: module factory indirection defaulting to REAL (mirrors CLI `--fake` opt-in); synth generator factory defaults to FAKE (mirrors synth CLI `--fake` default-True). No env var / setting / request param anywhere.
- Clearing the rules textarea restores profile rules (empty `rules` omitted client-side `api.ts:587-589`, falsy→`None` server-side `routers/inspect.py:129`) — never judges with empty rules.
- Eval rows have no stored overlays: `image_url` is built as `/files/<source>/<image>`, null on absolute/escaping paths (`routers/eval.py:56-65`); failures render only when dataset files sit under `data/<source>/`.
- Eval list skips dirs without `summary.json` (`runs/inspect/`, `smoke/`, `cli/` hold overlays/flat files, not runs).
- `save_profile` overwrites silently (`os.replace`); SOP save-as-new confirm is page-side existence check before PUT.
- Frontend overlay boxes must scale `bbox` (original-image pixels) to rendered size over the server PNG.
- Prior behavior: all four routers were one-line stubs; `from-sop` lived in `main.py:33`; only `load_profile` existed. M1–M5 pipeline/adapter/cache/schema/CLI contracts unchanged.
- Known-broken/outside: none reported; `manual:` criterion 5 is human-only (second device).

## Diff

Over budget as one block (5169 source lines + 2000-line lockfile), so split by group — run per group:

```sh
git diff main...HEAD -- backend/app/main.py backend/app/pipeline/inspect.py .gitignore .agents/RECORD.md
git diff main...HEAD -- backend/app/routers/inspect.py backend/app/routers/profiles.py backend/app/routers/eval.py backend/app/routers/synth.py
git diff main...HEAD -- backend/tests/test_routers.py
git diff main...HEAD -- frontend/src/api.ts
git diff main...HEAD -- frontend/src/pages/Inspect.tsx frontend/src/pages/Profiles.tsx frontend/src/pages/Eval.tsx frontend/src/pages/Synthetic.tsx
git diff main...HEAD -- frontend/src/App.tsx frontend/src/main.tsx frontend/src/index.css frontend/vite.config.ts frontend/index.html frontend/package.json frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json
# lockfile omitted: frontend/package-lock.json (2000 lines, generated)
```

Inline: the two small structural hunks (from-sop relocation, new save helper) — routers/pages/api/tests diffs via the commands above:

```diff
diff --git a/backend/app/main.py b/backend/app/main.py
index d3e7828..c8a32e0 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -1,23 +1,32 @@
 """FastAPI application entry point. Health endpoint lives here in M1."""
+from pathlib import Path
 from fastapi import FastAPI, HTTPException
 from fastapi.middleware.cors import CORSMiddleware
-from pydantic import BaseModel, Field
+from fastapi.responses import FileResponse
-from app.adapters.muse_spark import JudgeValidationError, MuseSparkJudge
+from app.adapters.muse_spark import MuseSparkJudge
 from app.config import settings
-from app.schemas import ProductProfile
+from app.routers.eval import router as eval_router
+from app.routers.inspect import router as inspect_router
+from app.routers.profiles import router as profiles_router
+from app.routers.synth import router as synth_router
 app = FastAPI()
-class SopDraftRequest(BaseModel):
-    sop_text: str = Field(min_length=1)
-    category_name: str = Field(min_length=1)
+app.include_router(profiles_router)
+app.include_router(inspect_router)
+app.include_router(eval_router)
+app.include_router(synth_router)
+@app.get("/files/{rel_path:path}")
+def serve_data_file(rel_path: str) -> FileResponse:
+    if (not rel_path or rel_path.startswith("/") or "\\" in rel_path
+            or any(seg in (".", "..") for seg in rel_path.split("/"))):
+        raise HTTPException(status_code=404, detail="not found")
+    data_dir = Path(settings.data_dir).resolve()
+    candidate = (data_dir / rel_path).resolve()
+    if candidate != data_dir and data_dir not in candidate.parents:
+        raise HTTPException(status_code=404, detail="not found")
+    if not candidate.is_file():
+        raise HTTPException(status_code=404, detail="not found")
+    return FileResponse(candidate)
```

```diff
diff --git a/backend/app/pipeline/inspect.py b/backend/app/pipeline/inspect.py
index 8e388ff..fae4e2a 100644
--- a/backend/app/pipeline/inspect.py
+++ b/backend/app/pipeline/inspect.py
@@ -48,6 +48,37 @@ def load_profile(name: str) -> ProductProfile:
     return ProductProfile.model_validate(data)
+def save_profile(profile: ProductProfile) -> Path:
+    import os
+    import tempfile
+    if not _PROFILE_NAME_RE.fullmatch(profile.id):
+        raise ValueError(f"unknown profile {profile.id!r}: invalid profile name")
+    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
+    path = PROFILES_DIR / f"{profile.id}.json"
+    payload = json.dumps(profile.model_dump(), indent=2, sort_keys=True) + "\n"
+    fd, tmp_name = tempfile.mkstemp(dir=PROFILES_DIR, suffix=".tmp")
+    try:
+        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
+            tmp.write(payload)
+        os.replace(tmp_name, path)
+    except BaseException:
+        try:
+            os.unlink(tmp_name)
+        except OSError:
+            pass
+        raise
+    return path
```
