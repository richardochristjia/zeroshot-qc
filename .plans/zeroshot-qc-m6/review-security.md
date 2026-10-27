# Security review — M6 (`feat/zeroshot-qc-m6`)

Source: [context-pack.md](.plans/zeroshot-qc-m6/context-pack.md) (BASE: main/M5; 33 files, routers `inspect`/`profiles`/`eval`/`synth` + `/files` serving + React frontend).
Scope: security only. Every finding below is backed by a real run (probes in `/tmp/secprobe*.py`, isolated tmp `data/`+`profiles/` dirs via `TestClient`, `raise_server_exceptions=False`).

## must-fix

1. **Synth `defect` param → arbitrary file write outside `data/`** (`backend/app/routers/synth.py:83-122` → `generate_pairs` in `backend/app/synth/generate.py:104-106`: `root / profile_id / defect` with no sanitization, unlike the `[A-Za-z0-9_-]+` guards on profiles/runs).
   Proof: `POST /api/synth/generate {"profile_id":"widget","defect":"../../pwned","n":1}` → **200**, wrote `data/pwned/000.png` (outside `data/synth/widget/`); `defect:"../../../../<tmp>/OUTSIDE/pwn"` → **200** and file exists **outside `data_dir` entirely**. Returned `image_url` (`/files/synth/widget/../../pwned/000.png`) is unfetchable only because `/files` blocks `..` — the write itself already happened. Also `defect:"/abs"` → unhandled **500**.
   Fix: validate `defect` (and `profile_id`) against `[A-Za-z0-9_-]+` like `_PROFILE_NAME_RE`/`_RUN_ID_RE`, reject before `mkdir`/`save`.
2. **`PUT /api/profiles/{id}` stores unconstrained `reference_image`, later read off-disk and sent to the external judge API** (`backend/app/schemas.py:33` — free-form `str|None`; consumed by `_load_reference_image` in `backend/app/pipeline/inspect.py:123-130` and `load_good_image` in `backend/app/synth/generate.py:62-68`, both accepting absolute paths).
   Proof: `PUT {"reference_image": "/etc/passwd"}` → **200**; absolute image path → **200** (accepted and persisted; non-image content 500s at inspect time, valid images are loaded and forwarded to the Meta API).
   Fix: constrain `reference_image` to a relative path under `data/` (resolve + containment, same pattern as `/files`), or reject absolute paths.

## consider

3. **No upload size limit; whole file buffered in RAM** (`backend/app/routers/inspect.py:111`: `raw = image.file.read()`, no `Content-Length`/size check anywhere in `backend/app`).
   Proof: 8 MB undecodable upload → **422** (fully read, never 413). Fix: cap size (e.g. 10–20 MB → 413) before/while reading.
4. **Unbounded `n` in synth generate → disk/CPU exhaustion** (`_GenerateBody.n: int`, only `n<1` rejected; loop writes `n` PNG pairs synchronously).
   Proof by code + must-fix-1 runs (each `n=1` wrote 2 files, no upper bound). Fix: cap `n` (e.g. ≤100).
5. **Unbounded SOP/rules/profile string lengths → LLM-cost amplification** (no `max_length` on `SopDraftRequest`, `rules` override, or `ProductProfile.rules`).
   Proof: 500 KB `sop_text` → **200**; 1 MB `rules` via PUT → **200**. Fix: `max_length` on request fields (e.g. 20–50 KB).
6. **Eval `_image_url` doesn't reject backslashes; `source` unsanitized** (`backend/app/routers/eval.py:56-65`: checks `..` parts and absolute, but not `\`).
   Proof: record `{"image": "..\\evil.png"}` → non-null `"/files/mvtec/..\\evil.png"` (dead link on Linux — `/files` rejects `\` — but a real separator on Windows servers). `source` comes from `summary.json` and is interpolated raw. Fix: reject `\` and validate `source` against `[A-Za-z0-9_-]+`.

## noted (checked, no action or accepted risk)

- **`/files` traversal guard is solid**: `..`, absolute, backslash, single/double-encoded (`..%2F`, `..%252F`, `%2e%2e`), and symlink-escape (symlink inside `data/` → outside) all → **404**; legitimate nested file → **200**. One probe artifact: `/files/runs/inspect/../../secret.txt` → 200 is client-side `..` normalization to `/files/secret.txt` (in-bounds), and direct guard call with a literal `..` segment → 404.
- **No secret leakage**: `meta_api_key` stays server-side (`backend/app/adapters/muse_spark.py:133`, `muse_image.py:53` — `Authorization: Bearer` built backend-only); `GET /api/health` exposes only non-secret model IDs (proven body has no key/token material); `grep -rE 'api_key|secret|sk-|token|innerHTML|dangerouslySet' frontend/src` empty.
- **CORS default safe**: `cors_origins` defaults to `http://localhost:5173` (specific, not `*`); evil `Origin` gets no `Access-Control-Allow-Origin` on GET, preflight → 400. Caution only: setting `cors_origins="*"` combined with `allow_credentials=True` would be unsafe — don't.
- **`profile_id`/`run_id` traversal neutralized by regex**: `load_profile`/`save_profile` (`[A-Za-z0-9_-]+`), `_RUN_ID_RE`; `../profiles/widget` and `../secret` run_ids → **404**. Upload filename sanitized (`.../evil.png` stored as `...____evil.png` under `data/uploads/`, proven).
- **Accepted architecture risk (flagged because criterion 5 puts the dev server on the LAN)**: no auth anywhere — PUT silently overwrites *and creates* profiles (proven: `PUT /api/profiles/brandnew` → 200 + new file), SOP/PUT/Inspect/Synth all unauthenticated. Fine for a local tool; don't expose beyond trusted LAN without auth.
