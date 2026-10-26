# Security review — feat/zeroshot-qc-m1 (M1)

Scope: security only — secret leakage (health/logs/cache/source), unsafe file
handling, CORS, adapter HTTP handling. Reviewed against
`.plans/zeroshot-qc-m1/context-pack.md` (BASE `main @ f6320a9`, BRANCH
`feat/zeroshot-qc-m1 @ a1a569c`, 39 files / +1839).

Proof method: every finding below was exercised with a real run in
`backend/.venv` (Python 3.11), not read-only inspection. Reproduce with
`backend/.venv/bin/python /tmp/sec_probe.py` (plus the traversal/RLE/symlink
follow-up in `/tmp/sec_probe2.py`). Baseline re-verified before review:
`cd backend && .venv/bin/python -m pytest -q` → **23 passed**.

Severity key: **must-fix** = exploitable/reachable in M1 as wired today;
**consider** = hardening at a trust boundary, needs an extra precondition;
**noted** = verified-safe behaviour or accepted-by-design exposure.

---

## Must-fix

### S1. Bearer key and inspection images are sent over cleartext HTTP — no scheme check in any real adapter

- Where: `backend/app/adapters/sam.py:40` + `sam.py:52-53`,
  `backend/app/adapters/muse_spark.py:59` + `muse_spark.py:79-80`,
  `backend/app/adapters/muse_image.py:44` + `muse_image.py:61-62`.
  All three build `url = settings.meta_api_base_url` verbatim and call
  `httpx.post(url, ..., headers={"Authorization": f"Bearer {settings.meta_api_key}"})`.
  Nothing rejects `http://`. `META_API_BASE_URL` is operator-supplied via `.env`
  (`backend/app/config.py:23`), so a typo, an internal staging endpoint, or a
  docs paste of an `http://` URL silently downgrades the key and every
  base64-encoded inspection image (`sam.py:44`, `muse_spark.py:72-74`,
  `muse_image.py:56-57`) to plaintext.
- Proof (real run): pointed `SamSegmenter` at a local `http://127.0.0.1:<port>/meta`
  capture server with a sentinel key. Adapter returned normally and the server
  recorded, over cleartext HTTP:
  `server saw Authorization over CLEARTEXT http: Bearer [REDACTED]
- Impact: credential theft + image disclosure by any on-path observer; also
  enables S2 (a MITM can then inject crafted responses).
- Fix: before any HTTP, require `urlsplit(settings.meta_api_base_url).scheme == "https"`
  (fail with `AdapterNotConfiguredError` otherwise). Permit `http://` only for
  loopback behind an explicit opt-in (e.g. `META_API_ALLOW_HTTP=1`), never by default.

### S2. Remotely supplied RLE is fed unchecked into the native pycocotools decoder; a dimension mismatch crashes smoke with an uncaught `IndexError`

- Where: `backend/app/adapters/sam.py:59-65` copies `entry["mask_rle"]` from the
  HTTP response into `RawMask` with no validation (`mask_rle: dict` in
  `backend/app/schemas.py:11` accepts anything). `backend/scripts/smoke.py:125-139`
  (`_decode_mask`) passes `counts`/`size` straight to `mask_api.decode`, and in
  `smoke.py:142-158` (`_make_overlay`) only the decode is inside `try/except` —
  the boolean indexing at `smoke.py:157` is not. `main()` catches only
  `AdapterNotConfiguredError` (`smoke.py:224`, `smoke.py:252`), so the crash is
  an unhandled traceback. The same unvalidated dict is persisted to the disk
  cache (`backend/app/pipeline/cache.py:171`) and replayed on later runs.
- Proof (real run): stubbed `httpx.post` to return one valid, non-empty RLE with
  `"size": [200, 200]` for a 40x30 image (donor RLE produced by `FakeSegmenter`
  on a 200x200 image). The adapter returned it verbatim
  (`adapter passed through size: [200, 200]`), then:
  `overlay raised: IndexError boolean index did not match indexed array along dimension 0; dimension is 30 but corresponding boolean dimension is 200`.
  A counts payload with an inflated `size` also makes the native decoder
  allocate attacker-chosen memory before any check runs.
- Note: this does not need an adversary — the Meta response shape is still a
  `TODO(meta-docs)` placeholder (context-pack "Meta HTTP is NOT a settled
  contract"), so a merely *unexpected* real response on the criterion-6
  real-key smoke hits the same path.
- Fix: validate before decode — `mask_rle["size"] == [image.height, image.width]`,
  `counts` is `str`/`bytes` with a sane length cap, decoded pixel total bounded —
  in the SAM adapter (reject/repair malformed masks) and defensively in
  `_decode_mask`; move the `overlay_arr[sel]` indexing inside the existing
  `try/except` (or skip masks whose decoded shape ≠ image shape).

---

## Consider

### C1. `DiskCache` keys are interpolated into filesystem paths unsanitised — read/write escape of the cache root

- Where: `backend/app/pipeline/cache.py:115-116`
  (`return self.root / f"{key}.json"`), used by `get` (`cache.py:118-126`) and
  `put` (`cache.py:128-143`). No key format check, no resolved-parent assertion.
- Proof (real run): `DiskCache(<tmp>/nest/cache).put("../../escaped", {"forged": True})`
  wrote `<tmp>/escaped.json` — two levels above the cache root — and
  `cache.get("../../escaped")` read it back (`{'forged': True}`).
- Reachability today: low. The only callers pass `hashlib.sha256().hexdigest()`
  from `segment_cache_key`/`judge_cache_key` (`cache.py:63-69`, `cache.py:87-98`),
  which is always 64 lowercase hex chars. This becomes a vulnerability the first
  time a later milestone keys the cache with anything user-influenced (M2+
  routers are already stubbed in `backend/app/routers/`).
- Impact if reached: overwrite of any `*.json` file the process can write
  (other cache entries, JSON configs) with caller-controlled JSON; `get` reads
  and returns the parsed content of any `*.json` file on disk.
- Fix: at the `DiskCache` boundary, accept only `^[0-9a-f]{64}$` keys (raise
  `ValueError` otherwise) or hash the key again before use; belt-and-braces,
  assert `self._path_for(key).resolve().parent == self.root.resolve()`.

### C2. Cache entries are trusted without integrity — a planted file silently replaces a verdict

- Where: `backend/app/pipeline/cache.py:162-172` (`CachedSegmenter`) and
  `cache.py:198-209` (`CachedJudge`) rebuild results with `model_validate` only.
  Any JSON that validates is served as if the model produced it; there is no
  HMAC, signature, or provenance check, and cache hits never call the model.
- Proof (real run): computed the real `judge_cache_key(...)`, wrote a forged
  entry directly to `<key>.json` with `"summary": "FORGED-PASS-no-judge-called"`,
  then called `CachedJudge(...).judge(...)`. Result:
  `poisoned verdict: FORGED-PASS-no-judge-called | inner calls: 0`.
- Reachability today: needs write access to `data/cache/` (same OS user as the
  app in M1), so this is integrity hardening, not a remote hole. It matters
  because the cached value is a QC PASS/FAIL verdict — a stale/planted entry
  changes inspection outcomes invisibly.
- Fix: document the trust assumption (cache dir is trusted local state) and/or
  store an HMAC of the payload keyed by a local secret; at minimum keep the
  cache dir out of any shared/upload-writable location in later milestones.

### C3. `Settings.meta_api_key` is a plain `str` — the shared settings object prints the key in full

- Where: `backend/app/config.py:22` (`meta_api_key: str = ""`), singleton at
  `config.py:40`. Pydantic renders field values in `repr`/`str`.
- Proof (real run): with a sentinel key set,
  `repr(settings) leaks key: True | str: True`.
- Reachability today: no code logs `settings` (verified: no `logging`/`logger`
  anywhere in `backend/app` or `backend/scripts`; `smoke.py` prints only mask
  counts, paths, and the verdict JSON). One future `logger.info(settings)`,
  debug dump, or exception reporter turns this into a leak.
- Fix: type the field as `pydantic.SecretStr` and call
  `.get_secret_value()` at the three header-construction sites; the adapters'
  empty-check becomes `settings.meta_api_key.get_secret_value()`.

### C4. No size limits on remote responses or decoded images (memory DoS from the API endpoint)

- Where: `response.json()` with no byte cap in all three adapters
  (`sam.py:57`, `muse_spark.py:84`, `muse_image.py:67`);
  `base64.b64decode` + `Image.open` with no dimension/pixel check in
  `muse_image.py:67-68`; local files get the same treatment via
  `Image.open(...).convert("RGB").copy()` in `backend/scripts/smoke.py:178-184`.
  Nothing sets or checks `Image.MAX_IMAGE_PIXELS` anywhere (`grep` confirms).
- Proof (real run): stubbed the image adapter's HTTP response with a base64 PNG
  header declaring 12000x9000. The adapter returned it unchecked:
  `returned lazy image size: (12000, 9000) px: 108000000 | warnings: ['DecompressionBombWarning'] | Pillow MAX_IMAGE_PIXELS: 89478485`.
  Pillow only *warns* between 1x and 2x its limit; the first `.load()`/`.copy()`
  by a caller allocates the full raster (~324 MB here, unbounded in general).
- Reachability: needs a malicious/compromised/MITM'd Meta endpoint (S1 makes
  MITM practical) or a crafted local image for smoke. `MuseImageGenerator` is
  unexercised in M1 (context-pack: "first exercised in M5"), so fix before M5.
- Fix: enforce an explicit pixel budget (e.g. reject `width*height > 50_000_000`)
  after `Image.open` in the image adapter and before `convert()` in smoke;
  treat `DecompressionBombError`/`Warning` as rejection, and cap accepted
  response sizes (stream with a byte limit or check `Content-Length` + decoded
  length before `b64decode`).

### C5. CORS allows credentials with wildcard methods/headers, and silently accepts `CORS_ORIGINS=*`

- Where: `backend/app/main.py:10-17` — `allow_credentials=True`,
  `allow_methods=["*"]`, `allow_headers=["*"]`, origins taken verbatim from
  `settings.cors_origins` (`backend/app/config.py:29`) with no validation.
- Proof (real run): on the app as shipped, an evil origin gets no
  `Access-Control-Allow-Origin` (default `['http://localhost:5173']` is safe —
  see N4). But rebuilding the middleware with the exact kwargs from
  `main.py:11-17` and `allow_origins=["*"]` (i.e. an operator setting
  `CORS_ORIGINS=*` in `.env`) yields, for `Origin: https://evil.example.com`:
  `ACAO= * ACAC= true`. Browsers refuse to expose `*` responses to credentialed
  fetches, which blunts the worst case today; the dangerous combination is
  still one config line away and the wildcard method/header grants are
  unnecessary for a single `GET /api/health` API.
- Fix: restrict to `allow_methods=["GET"]` and the headers actually needed;
  drop `allow_credentials=True` until an endpoint needs cookies/auth; reject
  (or loudly warn on) `*` in `CORS_ORIGINS` while credentials are enabled.

### C6. Smoke image discovery follows symlinks out of the data root — and real mode uploads what it finds to Meta

- Where: `backend/scripts/smoke.py:62-84` (`_collect_images`, `rglob` over the
  tree) and `smoke.py:95-109` (`discover_image_paths` calls it on `mvtec_dir`
  with `exclude_roots=[]`). The `_is_under` containment helper
  (`smoke.py:87-92`) is applied only to the `cache/` and `runs/smoke/`
  exclusions, never to the discovered images themselves. Anything discovered
  is opened (`smoke.py:178-184`) and, in real mode, base64-sent to the Meta
  API (`sam.py:42-50`).
- Proof (real run): placed `linked.png` inside a temp `data_dir` as a symlink
  to `outside/secret.png`. Discovery returned it, and:
  `.../data/linked.png -> resolves to .../outside/secret.png | under data? False`.
- Reachability: needs write access to the dataset dir (dataset drops, shared
  MVTec extractions). Impact is bounded (images only, smoke takes the first 3),
  but the upload-to-third-party step makes it an exfiltration path, not just a
  local read.
- Fix: skip symlinked files/dirs during collection, or drop any candidate whose
  `path.resolve()` is not under the intended root's `resolve()` — reuse
  `_is_under` for that.

---

## Noted

### N1. Health endpoint does not leak the key or base URL — verified

`backend/app/main.py:20-29` returns only `status` and the three model IDs.
Proof (real run) with sentinel key/URL set: `status 200`,
`key in body: False | base_url in body: False`. The committed tests assert the
same (`backend/tests/test_health.py:55-71`) and pass. Model IDs themselves are
exposed unauthenticated — that is the accepted contract (context-pack
acceptance criterion 1), recorded here so later milestones re-decide
consciously rather than by drift.

### N2. No hardcoded secrets, endpoints, or model IDs in source — verified

Grep guard over `backend/app` + `backend/scripts` (`*.py`): the only
`https?://` literal is the CORS default in `backend/app/config.py:29`; all
model-ID/key references read the shared `settings` instance. `.env` and
`data/` are ignored (`.gitignore:2,5`; `git check-ignore` confirms both) and
`git ls-files` shows no `.env` or `data/` path tracked; `.env.example` values
are empty placeholders. Real adapters raise `AdapterNotConfiguredError` before
any HTTP when key/base/model ID is empty (`sam.py:26-30`,
`muse_spark.py:33-37`, `muse_image.py:27-31`), proven by the no-HTTP tests in
`backend/tests/test_adapters.py:142-174` (all passing).

### N3. Cache writes no secrets to disk and uses restrictive file permissions — verified

Cache keys are `sha256` over framed inputs + model ID only
(`cache.py:55-98`); entries store `model_dump` JSON (`cache.py:171`,
`cache.py:208`). The committed sentinel test
(`backend/tests/test_cache.py:170-189`) passes: the sentinel API key appears in
neither filenames nor contents. Independently observed: entry files are mode
`0o600` (atomic `tempfile.mkstemp` + `os.replace`, `cache.py:128-143`); the
cache directory itself is default `0o755`, which is acceptable since entries
hold model outputs, not secrets. Adapter exceptions are never cached
(`cache.py:14`, proven by `test_cache.py:191-212`).

### N4. CORS as shipped (default origins) does not reflect arbitrary origins — verified

Proof (real run) against the deployed app: `Origin: http://localhost:5173` →
reflected with `ACAC= true` (intended dev frontend); `Origin: https://evil.example.com`
→ `ACAO= None`. The risk in C5 is configurational, not present in the default.

### N5. HTTP client defaults are safe: no TLS bypass, no redirect credential forwarding — verified

No `verify=False`, `cert=`, or environment-trust override anywhere (`grep`
over `backend/app`, `backend/scripts`). Installed `httpx 0.28.1` defaults to
`follow_redirects=False` (confirmed at runtime), and all three adapters use
plain `httpx.post(..., timeout=60.0)`, so a 3xx from the API cannot re-send
the `Authorization` header to a redirect target; `response.raise_for_status()`
(`sam.py:54`, `muse_spark.py:81`, `muse_image.py:63`) fails the call instead.
Timeouts are set on every call. Residual: HTTP error tracebacks can echo the
configured base URL (never the key, which travels in a header) to smoke's
stderr — acceptable, but keep it that way if error logging is added.

### N6. Interactive docs/OpenAPI are enabled and unauthenticated

`FastAPI()` at `backend/app/main.py:8` keeps the defaults. Proof (real run):
`/openapi.json`, `/docs`, `/redoc` all return `200`. In M1 this discloses only
the health route's shape. Disable (`docs_url=None, redoc_url=None, openapi_url=None`)
or gate them before any deployment beyond localhost, especially once the
stubbed routers (`backend/app/routers/inspect.py`, `profiles.py`, `eval.py`,
`synth.py`) are mounted.

### N7. Operator-controlled paths are honoured verbatim

`backend/app/config.py:31-37` resolves relative `DATA_DIR`/`MVTEC_DIR` against
the repo root and accepts absolute values as-is; `DiskCache` and smoke then
create directories there (`cache.py:113`, `smoke.py:200-201`). This is correct
 behaviour for env-supplied config (the operator already controls the process),
recorded only so nobody later wires request input into these settings without
containment checks (see C1/C6).

---

## Summary

| Severity | Count | IDs |
|---|---|---|
| Must-fix | 2 | S1 cleartext-HTTP credential/image exposure; S2 unchecked remote RLE into native decoder |
| Consider | 6 | C1 cache path traversal, C2 cache verdict poisoning, C3 `SecretStr`, C4 response/image size limits, C5 CORS wildcard+credentials, C6 symlink escape in smoke discovery |
| Noted | 7 | N1-N7 verified-safe or accepted-by-design items above |

Fix S1 and S2 before the acceptance-criterion-6 real-key smoke
(context-pack: "manual: with real keys ... smoke prints real SAM mask counts").
All other items are safe to schedule with M2/M5, when user input first reaches
the cache, the routers, and `MuseImageGenerator`.
