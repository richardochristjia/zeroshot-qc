# Correctness review — M7 (branch feat/zeroshot-qc-m7)

Sources: [.plans/zeroshot-qc-m7/context-pack.md](/.plans/zeroshot-qc-m7/context-pack.md)
(claims cited as CP) and `plan.md` acceptance criteria (cited as AC1–AC5).
Every finding below carries its proof (a real run, not a re-read).

Live evidence this review produced (all on this branch):
- `docker build -t zeroshot-qc .` → success.
- Container + `USE_FAKE_ADAPTERS=true` → `/api/health` 200
  (`{"status":"ok","models":{"sam":"","judge":"","image":""}}`),
  fake inspect profile `screw` → `FAIL / "Fake judge: …"` with
  overlay `/files/runs/inspect/…_overlay.png` → 200,
  `/files/../outside.txt` → 404, unknown profile → 404,
  `Origin: http://localhost:5173` → `access-control-allow-origin` echoed.
- Container without the flag → boots, `/api/health` 200 (real default intact).
- `pytest` → 166 passed (incl. `tests/test_fake_flag.py`, 2 passed).
- `VITE_API_URL=http://localhost:8000 npm run build` → success;
  bundle contains the origin once, `sk-…` grep → no match, `dist/` gitignored.
- `modal_app` without `modal` installed → imports, `asgi_app is None`,
  `build_modal_asgi()` raises the documented `RuntimeError`.
- `Settings()`: default `use_fake_adapters=False`;
  `USE_FAKE_ADAPTERS=true/false` map to `True/False`.
- Node probe of the shipped logic: trailing `/` and `///` strip to one join,
  `""`/`undefined` stay same-origin relative; absolute/`blob:` pass through.

## Must-fix

1. **`.dockerignore` patterns miss everything under `backend/` — image bakes in
   a 335 MB `.venv` plus caches.** Patterns like `.venv/`, `__pycache__/`,
   `.pytest_cache/` only match the context root, but the Dockerfile copies the
   `backend/` subtree, so `backend/.venv`, `backend/app/__pycache__`,
   `backend/.pytest_cache` sail through. Proof from the built image:
   `du -sh /srv/backend/.venv` → `335M`, image size `1.04GB`, plus
   `app/__pycache__`, `scripts/__pycache__`, `tests/__pycache__` present.
   Beyond bloat, a stale baked-in `.venv` is the exact mismatched-package
   hazard the README warns about. Fix: `**/`-prefix the directory patterns
   (e.g. `**/.venv/`, `**/__pycache__/`, `**/.pytest_cache/`) so they match at
   any depth. Failing-now proof: `docker run --rm zeroshot-qc sh -c
   'ls /srv/backend/.venv'` succeeds; after the fix + rebuild it must fail.
   (Plan AC1 / Dockerfile layer hygiene; CP "layer hygiene" claim.)
2. **README fake-inspect step references `/tmp/zqc-data/probe.png`, which the
   README never creates — the verbatim reader test fails.** `README.md:101`
   curls `image=@/tmp/zqc-data/probe.png`, but no earlier step writes that
   file (`mkdir -p /tmp/zqc-data` only makes the dir). Proof: the exact command
   against a fresh dir exits `curl-exit=26` (couldn't open local file) before
   any byte is sent — this reviewer had to synthesize `probe.png` by hand to
   run the container probes. Fix: one line creating it (e.g. a 3-line
   PIL snippet or "substitute any PNG/JPG at that path"). This breaks the
   README's own "verified verbatim" claim and plan AC4.

## Consider

- **Exclude `tests/` (and `scripts/` smoke) from the image once `.dockerignore`
  is touched.** Harmless today (probes all pass with them present), but they
  are dead weight in a deploy artifact and `tests/` drags `__pycache__` with
  it. One-line addition next to the must-fix #1 edit; re-prove with the same
  rebuild check.
- **`vercel.json` buildCommand `cd frontend && …` assumes repo-root builds.**
  Correct for Vercel's default root, but if the dashboard project ever sets
  Root Directory to `frontend/` the build breaks. Not a code change — one
  README half-line ("leave Root Directory at the repo root") removes the trap.

## Noted (checked, no action)

- **Dockerfile base/install/CMD/DATA_DIR correct.** `python:3.11-slim` matches
  the `.python-version` pin; requirements layer precedes `COPY backend/`;
  `CMD uvicorn app.main:app` serves the same object `modal_app.py` imports;
  `DATA_DIR=/data` + live overlay write/fetch through the `-v …:/data` mount
  prove the mount contract end to end (AC1 green).
- **No secrets in layers.** `.env*`/`*.key`/`*.pem`/`secrets/` excluded and
  verified absent in the running image (`find /srv -name ".env*"` → empty);
  `backend/` tree itself contains no `.env*`/key files to leak.
- **USE_FAKE_ADAPTERS semantics exact.** Default `False` keeps the real path
  byte-identical (same `build_*(False, cache)` call — full suite green);
  env-gated only, read at call time so tests can monkeypatch while the
  container gets it from `-e` at process start (CP "flag only via env").
- **Vercel wiring complete, dev fallback preserved.** All 4 fetch sites route
  through `apiUrl` (no raw `fetch("/api…` remains); all 3 page `img src`
  fixes route through `resolveFileUrl`; `vite.config.ts` proxy untouched so
  empty `VITE_API_URL` stays same-origin (AC2 green incl. secret grep).
- **Modal wrapper valid as far as keyless automation can reach.** Same `app`
  object, guarded import, clear deploy-path error (all run-proven). Full
  decorator validity against real Modal needs `modal deploy` with human
  credentials — explicitly plan AC5/manual, documented-not-run in README.
- **Dismissed: whitespace-only `VITE_API_URL` (`"   /api/…"`) and
  leading-slash-less `resolveFileUrl` input (`"http://h:8000files/…"`)** — both
  reproduced in the node probe, both unreachable: the value arrives via
  `vercel env add` paste, and every backend emitter (`routers/synth.py:120`,
  `routers/eval.py:_image_url`, inspect `overlay_url`) always emits
  leading-slash `/files/…`. Not worth a code branch; no change.
- **Dismissed: `modal.App`/`asgi_app` composition shape** — cannot be proven
  without the `modal` package + credentials (never installed here per plan);
  not asserted as a finding for that reason. Covered by manual AC5.
