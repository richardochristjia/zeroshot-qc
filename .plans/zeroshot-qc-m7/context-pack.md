# Context pack

BASE: main (M6 merged)
CHANGED: 22 files, +657/-16 (15 code/docs/config files; 7 plan-internal files excluded throughout)

## What this change does
M7 is deploy-ready + polish, config/wiring only (M7-AC3: no app-behavior change). It adds a slim Python 3.11 `Dockerfile` serving the same FastAPI app via uvicorn, a thin `modal_app.py` wrapper importing that app object, and a `vercel.json` static frontend build wired to the backend through build-time `VITE_API_URL` (dev proxy stays the fallback). Same run: a `USE_FAKE_ADAPTERS` env flag so container probes can serve fake inspect, a 13-item carry list in `docs/HANDOFF.md`, the gallery Record entry (approved), and a clone-to-push README rewrite.

## Files
- `Dockerfile` — new; `python:3.11-slim`, installs `backend/requirements.txt`, copies `backend/`, `CMD uvicorn app.main:app` on 8000, `DATA_DIR=/data` default
- `.dockerignore` — new; excludes `.env*`, keys, `data/`, `node_modules/`, `dist/`, caches, `.git/`, `.plans/`, `.agents/`, `docs/`
- `modal_app.py` — new; thin Modal wrapper importing the same `app` object (`backend/app/main.py`); guarded `modal` import so it import-validates without the package
- `vercel.json` — new; build `cd frontend && npm ci && npm run build`, output `frontend/dist`, SPA rewrite to `/index.html`
- `frontend/src/api.ts` — changed; adds `normalizeApiBase`/`API_BASE`/`apiUrl`/`resolveFileUrl` (`frontend/src/api.ts:470-504`); all fetches join onto the build-time origin, empty in dev for the proxy
- `frontend/src/pages/Inspect.tsx` — changed; overlay `img src` via `resolveFileUrl` (`frontend/src/pages/Inspect.tsx:221`)
- `frontend/src/pages/Eval.tsx` — changed; failure-detail `img src` via `resolveFileUrl` (`frontend/src/pages/Eval.tsx:139`)
- `frontend/src/pages/Synthetic.tsx` — changed; gallery image + mask `img src` via `resolveFileUrl` (`frontend/src/pages/Synthetic.tsx:30,46`)
- `backend/app/config.py` — changed; adds `use_fake_adapters: bool = False` (`backend/app/config.py:27`)
- `backend/app/routers/inspect.py` — changed; `_get_segmenter`/`_get_judge` pass `settings.use_fake_adapters` to `build_*` (`backend/app/routers/inspect.py:27-50`)
- `backend/tests/test_fake_flag.py` — new (81 lines); flag-off-real + flag-on-fake-inspect tests (group 2, new file in full)
- `README.md` — changed (+124); prerequisites, local/Docker run, human push commands, checklist state (group 2)
- `docs/HANDOFF.md` — new (67 lines); 13 carried M1–M6 items with owners (group 2, new file in full)
- `docs/EVAL_NOTES.md` — changed (+3); synth `n_defective` per-type note (group 2)
- `.agents/RECORD.md` — changed (+3); gallery + 2 deploy entries (group 2)

## API contracts
- `GET /api/health` → 200 with model IDs; declared in `backend/app/main.py:58`
- `POST /api/inspect` (multipart `image` + `profile_id`, optional `rules`) → `InspectionResult` incl. overlay URL; fake when `USE_FAKE_ADAPTERS=true`; router `backend/app/routers/inspect.py:27-50`, shape parsed in `frontend/src/api.ts`
- `GET /files/{rel_path:path}` → file bytes; traversal outside data root 404; `backend/app/main.py:38`
- `GET /api/synth/gallery` → grouped entries with `/files/synth/...` URLs; `backend/app/routers/synth.py:40`
- Frontend: every `fetch` and page `img src` goes through `API_BASE`/`resolveFileUrl` (`frontend/src/api.ts:470-504`); absolute/`blob:`/`data:` URLs pass through

## Test entry points
- `backend/tests/test_fake_flag.py` — `cd backend && pytest tests/test_fake_flag.py`
- Full suite — `cd backend && pytest` (166 passed; config/wiring-only per M7-AC3)
- Frontend — `cd frontend && npm run build`; prod check `VITE_API_URL=http://localhost:8000 npm run build` + bundle grep for `sk-`/Bearer/key patterns
- Container (needs Docker) — `docker build -t zeroshot-qc .`, run `-v <throwaway>:/data -e DATA_DIR=/data -e CORS_ORIGINS=<origin> -e USE_FAKE_ADAPTERS=true`; prove health, fake inspect (profile `screw`), overlay fetch, `/files/../` 404, unknown-profile 404, `Origin` CORS echo

## Acceptance criteria
1. `docker build` succeeds; the container passes health, fake inspect with fetchable overlay, and `/files` fetch. Check: container runs in Verification.
2. Production frontend build succeeds with no secret patterns in the bundle. Check: build + grep in Verification.
3. `pytest` green; no app-code behavior changes (config/wiring only). Check: full suite.
4. README takes a stranger from clone to local run to (with their own logins) public URL push. Check: README review against the checklist.
5. manual: the user runs the Modal/Vercel push commands and confirms the public URL in a private window (human logins; never run by automation).

## Do not re-derive
- Divergence from `plan.md`: the planned container fake-inspect probe was unreachable as specified — getters default to real adapters and fakes existed only via in-process monkeypatch (`backend/tests/test_routers.py:57-64`), which cannot reach a running container. So M7 added `USE_FAKE_ADAPTERS` (default false; real path byte-identical); pytest stays green.
- `frontend/vite.config.ts` UNCHANGED — dev proxy is the fallback when `VITE_API_URL` is empty; slash stripped once so joins never double-slash.
- `backend/app/main.py` UNCHANGED — CORS already env-driven; M7 proves it with an `Origin` fetch.
- `modal_app.py` has no app logic; host CLIs were never installed here, so push commands are documented-not-run.
- Carry list lives in new `docs/HANDOFF.md` (no handoff list existed; sourced from `.plans/zeroshot-qc-m7/check-3.md`). Gallery Record entry APPROVED (live 200, 11 grouped entries).
- Still open / not this change: M6-G0 second-device walkthrough, M1-AC6 real-keys smoke, M2-AC5 CLI-on-MVTec (all manual); README lacks architecture diagram + metrics table (checklist PARTIAL).

## Diff — group 1 (deploy + wiring code; complete)
```diff
diff --git a/.dockerignore b/.dockerignore
new file mode 100644
index 0000000..d3f2b97
--- /dev/null
+++ b/.dockerignore
@@ -0,0 +1,40 @@
+# Secrets — never bake into layers
+.env
+.env.*
+*.key
+*.pem
+*.p12
+secrets/
+
+# Data — mounted at run time via DATA_DIR, never baked in
+data/
+
+# Frontend
+node_modules/
+frontend/node_modules/
+frontend/dist/
+dist/
+
+# Local/agent state
+.lavish/
+
+# Python caches and envs
+__pycache__/
+*.py[cod]
+*$py.class
+.pytest_cache/
+.mypy_cache/
+.venv/
+venv/
+*.egg-info/
+
+# VCS, plans, docs scratch
+.git/
+.plans/
+.agents/
+docs/
+
+# OS / editor
+.DS_Store
+.idea/
+.vscode/
diff --git a/Dockerfile b/Dockerfile
new file mode 100644
index 0000000..ec5aa1c
--- /dev/null
+++ b/Dockerfile
@@ -0,0 +1,18 @@
+FROM python:3.11-slim
+
+ENV PYTHONDONTWRITEBYTECODE=1 \
+    PYTHONUNBUFFERED=1 \
+    DATA_DIR=/data
+
+WORKDIR /srv/backend
+
+COPY backend/requirements.txt ./requirements.txt
+RUN pip install --no-cache-dir -r requirements.txt
+
+COPY backend/ .
+
+RUN mkdir -p /data
+
+EXPOSE 8000
+
+CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
diff --git a/backend/app/config.py b/backend/app/config.py
index 1801c4d..383b5ea 100644
--- a/backend/app/config.py
+++ b/backend/app/config.py
@@ -24,6 +24,7 @@ class Settings(BaseSettings):
     sam_model_id: str = ""
     judge_model_id: str = ""
     image_model_id: str = ""
+    use_fake_adapters: bool = False
     data_dir: str = "./data"
     mvtec_dir: str = "./data/mvtec"
     cors_origins: str = "http://localhost:5173"
diff --git a/backend/app/routers/inspect.py b/backend/app/routers/inspect.py
index 2e3d24c..a0c30d9 100644
--- a/backend/app/routers/inspect.py
+++ b/backend/app/routers/inspect.py
@@ -27,17 +27,27 @@ router = APIRouter()
 def _get_segmenter(
     cache: DiskCache | None = None,
 ) -> CachedSegmenter:
-    """Real cached segmenter; tests monkeypatch this to ``build_*(True)``."""
+    """Cached segmenter; fake when ``USE_FAKE_ADAPTERS`` is set.
+
+    Tests monkeypatch this to ``build_*(True)``; a running container
+    cannot be monkeypatched, so it reads the env-gated settings flag
+    instead (default real, byte-identical when unset).
+    """
     if cache is None:
         cache = DiskCache(Path(settings.data_dir) / "cache")
-    return build_segmenter(False, cache)
+    return build_segmenter(settings.use_fake_adapters, cache)
 
 
 def _get_judge(cache: DiskCache | None = None) -> CachedJudge:
-    """Real cached judge; tests monkeypatch this to ``build_*(True)``."""
+    """Cached judge; fake when ``USE_FAKE_ADAPTERS`` is set.
+
+    Tests monkeypatch this to ``build_*(True)``; a running container
+    cannot be monkeypatched, so it reads the env-gated settings flag
+    instead (default real, byte-identical when unset).
+    """
     if cache is None:
         cache = DiskCache(Path(settings.data_dir) / "cache")
-    return build_judge(False, cache)
+    return build_judge(settings.use_fake_adapters, cache)
 
 
 class _TimedSegmenter:
diff --git a/frontend/src/api.ts b/frontend/src/api.ts
index 30f0527..deefd7c 100644
--- a/frontend/src/api.ts
+++ b/frontend/src/api.ts
@@ -3,8 +3,10 @@
 Every backend call the four pages need flows through here. Boundary
 rule (write-typescript): `unknown` in, parsed domain types out — each
 parser validates the JSON payload at runtime and throws on mismatch,
-so pages never cast. No secrets here: same-origin relative URLs only
-(the Vite dev proxy forwards `/api` + `/files` to the backend).
+so pages never cast. No secrets here: every backend URL is built from
+`API_BASE` below — the build-time `VITE_API_URL` with the trailing slash
+stripped once, empty in dev so same-origin relative URLs flow through
+the Vite dev proxy (`/api` + `/files` → localhost:8000).
 */
 
 const JSON_HEADERS = { Accept: "application/json" };
@@ -465,6 +467,44 @@ function parseSynthGalleryItem(value: unknown, index: number): SynthGalleryItem
   };
 }
 
+// ---------------------------------------------------------------------------
+// Backend origin wiring (M7 deploy): build-time `VITE_API_URL` with the
+// trailing slash stripped once, so `/api/...` joins never double-slash.
+// Empty/unset (dev) keeps same-origin relative URLs for the Vite proxy.
+// `import.meta.env` values arrive untyped, so the raw value is narrowed
+// from `unknown` here at the boundary and trusted as `string` below.
+// ---------------------------------------------------------------------------
+
+function normalizeApiBase(rawBase: unknown): string {
+  if (typeof rawBase !== "string") return "";
+  return rawBase.replace(/\/+$/, "");
+}
+
+const API_BASE: string = normalizeApiBase(import.meta.env.VITE_API_URL);
+
+/** Join a server-absolute path onto the configured backend origin. */
+function apiUrl(path: string): string {
+  return `${API_BASE}${path}`;
+}
+
+/** Resolve a backend file URL for `img src` (M7 deploy).
+ *
+ * Server-relative `/files/...` URLs (what the backend emits) are joined
+ * onto the backend origin so images load when the frontend is served from
+ * a separate Vercel origin. Already-absolute URLs (`http(s):`, `blob:`
+ * upload previews, `data:`) pass through untouched. */
+export function resolveFileUrl(url: string): string {
+  if (
+    url.startsWith("blob:") ||
+    url.startsWith("data:") ||
+    url.startsWith("http://") ||
+    url.startsWith("https://")
+  ) {
+    return url;
+  }
+  return `${API_BASE}${url}`;
+}
+
 // ---------------------------------------------------------------------------
 // Transport.
 // ---------------------------------------------------------------------------
@@ -520,7 +560,7 @@ async function throwForStatus(
 }
 
 async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
-  const response = await fetch(path, { headers: JSON_HEADERS, signal });
+  const response = await fetch(apiUrl(path), { headers: JSON_HEADERS, signal });
   if (!response.ok) {
     await throwForStatus(response, "generic");
   }
@@ -533,7 +573,7 @@ async function postJson(
   body: Record<string, string | number>,
   signal?: AbortSignal,
 ): Promise<unknown> {
-  const response = await fetch(path, {
+  const response = await fetch(apiUrl(path), {
     method: "POST",
     headers: { ...JSON_HEADERS, "Content-Type": "application/json" },
     body: JSON.stringify(body),
@@ -569,7 +609,7 @@ export async function inspectImage(params: InspectParams): Promise<InspectionRes
   if (params.rules !== undefined && params.rules !== "") {
     form.append("rules", params.rules);
   }
-  const response = await fetch("/api/inspect", {
+  const response = await fetch(apiUrl("/api/inspect"), {
     method: "POST",
     body: form,
     signal: params.signal,
@@ -608,7 +648,7 @@ export async function putProfile(
   signal?: AbortSignal,
 ): Promise<ProductProfile> {
   const response = await fetch(
-    `/api/profiles/${encodeURIComponent(profile.id)}`,
+    apiUrl(`/api/profiles/${encodeURIComponent(profile.id)}`),
     {
       method: "PUT",
       headers: { ...JSON_HEADERS, "Content-Type": "application/json" },
diff --git a/frontend/src/pages/Eval.tsx b/frontend/src/pages/Eval.tsx
index bae4020..e854dc9 100644
--- a/frontend/src/pages/Eval.tsx
+++ b/frontend/src/pages/Eval.tsx
@@ -1,6 +1,6 @@
 import { useEffect, useState } from 'react'
 import type { JSX } from 'react'
-import { ApiError, getEvalRun, listEvalRuns } from '../api.ts'
+import { ApiError, getEvalRun, listEvalRuns, resolveFileUrl } from '../api.ts'
 import type {
   CategoryMetrics,
   EvalResultRow,
@@ -136,7 +136,7 @@ function FailureDetail({ row }: FailureDetailProps): JSX.Element {
         </div>
       ) : (
         <img
-          src={row.imageUrl}
+          src={resolveFileUrl(row.imageUrl)}
           alt={`${row.category} ${row.image}`}
           className="mt-3 block max-w-full"
           onError={() => setImgBroken(true)}
diff --git a/frontend/src/pages/Inspect.tsx b/frontend/src/pages/Inspect.tsx
index 535b97e..1319496 100644
--- a/frontend/src/pages/Inspect.tsx
+++ b/frontend/src/pages/Inspect.tsx
@@ -4,6 +4,7 @@ import {
   ApiError,
   inspectImage,
   listProfiles,
+  resolveFileUrl,
 } from '../api.ts'
 import type { Detection, InspectionResult, ProductProfile } from '../api.ts'
 
@@ -217,7 +218,7 @@ export default function Inspect(): JSX.Element {
             <h2 className="text-sm font-semibold">Overlay</h2>
             <div className="relative mt-2 inline-block max-w-full">
               <img
-                src={shownImage}
+                src={resolveFileUrl(shownImage)}
                 alt={result !== null ? `Inspection overlay for ${result.profileId}` : 'Uploaded image preview'}
                 className="block max-w-full"
                 onLoad={(event) => {
diff --git a/frontend/src/pages/Synthetic.tsx b/frontend/src/pages/Synthetic.tsx
index c683192..497582c 100644
--- a/frontend/src/pages/Synthetic.tsx
+++ b/frontend/src/pages/Synthetic.tsx
@@ -1,6 +1,6 @@
 import { useEffect, useState } from 'react'
 import type { JSX } from 'react'
-import { ApiError, listSyntheticGallery } from '../api.ts'
+import { ApiError, listSyntheticGallery, resolveFileUrl } from '../api.ts'
 import type { SynthGalleryItem } from '../api.ts'
 
 function errorDetail(err: unknown, fallback: string): string {
@@ -27,7 +27,7 @@ function PairCard({ item }: PairCardProps): JSX.Element {
         </div>
       ) : (
         <img
-          src={item.imageUrl}
+          src={resolveFileUrl(item.imageUrl)}
           alt={`${item.category} ${item.defect} synthetic image`}
           className="block w-full"
           onError={() => setImgBroken(true)}
@@ -43,7 +43,7 @@ function PairCard({ item }: PairCardProps): JSX.Element {
         </div>
       ) : (
         <img
-          src={item.maskUrl}
+          src={resolveFileUrl(item.maskUrl)}
           alt={`${item.category} ${item.defect} defect mask`}
           className="mt-2 block w-full"
           onError={() => setMaskBroken(true)}
diff --git a/modal_app.py b/modal_app.py
new file mode 100644
index 0000000..4b2adfb
--- /dev/null
+++ b/modal_app.py
@@ -0,0 +1,38 @@
+"""Modal hosting wrapper (M7). Thin wrapper — no app logic lives here.
+
+Imports the same FastAPI ``app`` object the container serves
+(``backend/app/main.py``) and exposes it through Modal's ASGI construct
+when the ``modal`` package is installed. Import-validates without
+``modal`` installed: the ``modal`` import is guarded, and a clear error
+is raised only on the deploy path (calling ``build_modal_asgi`` /
+accessing ``asgi_app`` without ``modal``).
+"""
+
+import os
+import sys
+
+sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
+
+from app.main import app  # noqa: E402  (same object the container serves)
+
+try:
+    import modal  # type: ignore[import-not-found]
+except ImportError:
+    modal = None  # type: ignore[assignment]
+
+
+def build_modal_asgi(app_obj=app):
+    """Expose the ASGI app through Modal. Requires the ``modal`` package."""
+    if modal is None:
+        raise RuntimeError(
+            "The 'modal' package is not installed. "
+            "Install it with `pip install modal` and run `modal setup` "
+            "before deploying modal_app.py."
+        )
+    modal_app = modal.App("zeroshot-qc")
+    return modal_app.function(image=modal.Image.debian_slim())(modal.asgi_app()(lambda: app_obj))
+
+
+asgi_app = None
+if modal is not None:
+    asgi_app = build_modal_asgi()
diff --git a/vercel.json b/vercel.json
new file mode 100644
index 0000000..4204416
--- /dev/null
+++ b/vercel.json
@@ -0,0 +1,7 @@
+{
+  "$schema": "https://openapi.vercel.sh/vercel.json",
+  "buildCommand": "cd frontend && npm ci && npm run build",
+  "outputDirectory": "frontend/dist",
+  "framework": "vite",
+  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
+}
```
## Diff — group 2 (docs, record, new test; summarized, new files in full in repo)
Reproduce exactly with: `git diff main...HEAD -- README.md docs/ .agents/RECORD.md backend/tests/test_fake_flag.py`
- `README.md` (+124): Prerequisites/Setup/Run-locally/Docker-run/Push-to-public-URL sections, submission checklist state, verbatim reader test.
- `docs/HANDOFF.md` (new, 67 lines): 13 carried M1–M6 items with owners — code debt M1-LO2, M2-F2, M2-LO, M6-St2/St3/St4, M6-I1/I2/I3, M5/M3 consider leftovers; manual M1-AC6, M2-AC5, M6-G0.
- `docs/EVAL_NOTES.md` (+3): synth `n_defective` is per defect type, unlike MVTec total cap.
- `.agents/RECORD.md` (+3): synth gallery entry + 2 M7 deploy entries.
- `backend/tests/test_fake_flag.py` (new, 81 lines): `test_flag_off_default_is_real_construction`, `test_flag_on_serves_fake_inspect`.
