# Falsify — M7 must-fix rulings

Merged rule: correctness + security `.dockerignore` findings describe one root
cause → one ruling, doubly-weighted. Impact-review kept risks are not fixes;
they sit in the open-findings list as leave-open candidates. Worst harm first.

## Rulings

fix: `.dockerignore` covers nothing under `backend/` — image bakes 335 MB `.venv`, caches, tests (correctness + security, doubly-raised). Reproduced: `docker run --rm zeroshot-qc` shows `/srv/backend/.venv` present at 335M, image 1.04GB, plus `.pytest_cache/` and `tests/` baked in. Harm is worst in set: stale baked-in venv is a wrong-package wrong state, and the secrets guard is fail-open for any future `backend/.env`. Fix buys a slim honest image plus a real secrets guarantee; test: `ls /srv/backend/.venv` in image must fail after rebuild.
fix: Modal image is bare `debian_slim()` with no requirements (structure). Shown by run: `grep pip_install modal_app.py` empty, so the deployed function imports the full backend (FastAPI/pydantic/adapters) into an image that installs none of it — cold start dies on `ImportError`. Who hits it: anyone running the README push path; harm: deployed dead backend. Not live-runnable here (AC5 is human-creds-only by plan), premise proven statically. Fix buys a working push; test: stub-`modal` import test asserting the image installs `backend/requirements.txt`.
fix: `modal.App` built inside `build_modal_asgi` closure, nothing at module scope (structure). Shown by run: AST of `modal_app.py` has no module-level `App` assignment, so `modal deploy modal_app.py` finds no App to deploy. Who hits it: the one human push command M7 exists to enable; harm: deploy fails outright. Fix buys a deployable entrypoint; test: stub-`modal` test asserting a module-level App exists.
narrow: `USE_FAKE_ADAPTERS` honored only by inspect router despite global name/placement (structure). Reproduced: only `inspect.py:38,50` reads `settings.use_fake_adapters`; `synth.py` and `eval/run.py:77-79` take separate fake paths. Who hits it: a prober calling synth/eval with the flag on gets real-adapter 500s without keys — recoverable wrong message, and only off the README's documented inspect-only probe path. Cheapest answer is narrowing, not rewiring: document the flag as inspect-only (README + config comment); widening shared wiring risks AC3 behavior change. Rename-or-widen remains open only if the user wants more.
fix: README fake-inspect step references `/tmp/zqc-data/probe.png`, which the README never creates (correctness). Reproduced: `mkdir` is the only setup step (`README:81`); against a fresh dir the verbatim curl exits `curl-exit=26` before any byte is sent. Who hits it: every stranger following the README; harm: recoverable-but-blocking docs failure that voids the "verified verbatim" claim (AC4). Fix buys a copy-paste-true README; test: fresh-dir reader run of the exact command.
fix: `.env.example` omits `USE_FAKE_ADAPTERS` (structure). Reproduced: file read shows 8 keys, no flag line, while `config.py:27` defines it. Who hits it: a stranger setting up from docs — flag undiscoverable, default-real guarantee unverifiable. Harm is looks/discoverability only. Fix is one line plus comment; test: grep for the key in `.env.example`.
fix: `USE_FAKE_ADAPTERS` env→settings binding untested (tests). Reproduced: no `setenv` in `test_fake_flag.py` (grep exit 1); the binding itself works (`Settings()` maps `true/false` correctly, verified by run), so the exact mechanism M7 added is proven only by a one-off manual container probe. Who hits it: a future editor renaming the field breaks container probes with a green suite. Fix buys a regression net; test: `Settings()`-with-`setenv` test that breaks on rename/drift.
fix: `modal_app.py` has zero committed tests (tests). Reproduced: no `modal` hits in `backend/tests/`; the import-without-`modal` guard works live (`asgi_app=None`) but lives only in a commit message. Who hits it: any editor of the wrapper regresses silently. Fix buys a credential-free safety net; test: stub-`modal` import test plus `build_modal_asgi` `RuntimeError` test (also covers the two Modal structure fixes above).
fix: frontend `normalizeApiBase`/`resolveFileUrl` have zero tests and no runner (tests). Reproduced: no `*.test.*` files, no `test` script in `frontend/package.json` (scripts are dev/build/lint/preview only). Who hits it: a future editor of the join sites diverges fetches vs images with no signal; harm is process-only today (build is green, probe-verified). Fix buys edge-case cover for the slash/passthrough variants plan.md calls out; test: new spec for slash variants, `blob:`/`data:`/absolute passthrough, dev-empty-base.

## For the fixer

- fix: `.dockerignore` `**/`-prefix (or `backend/`-prefix) depth patterns + rebuild.
- fix: pin Modal image to `backend/requirements.txt`.
- fix: bind `modal.App` at module scope; decorate a module-level asgi function.
- narrow: document `USE_FAKE_ADAPTERS` as inspect-only (README + config comment).
- fix: README one-liner creating `probe.png` (or "substitute any PNG/JPG").
- fix: `.env.example` `USE_FAKE_ADAPTERS=false` + one-line comment.
- fix: `Settings()` env-binding test; `modal_app` stub tests; vitest + URL-join spec.

## For the user

None — no ruling needs a new product rule or special case.

## For the PR's open findings

- leave open: prod frontend built without `VITE_API_URL` silently points at itself (impact review).
- leave open: `resolveFileUrl` only rewrites server-relative URLs (impact review).
- leave open: `USE_FAKE_ADAPTERS=true` left on in a real deployment serves fakes (impact review).
- leave open: README push path is documented-not-run (impact review).

## Dismissed

None — every must-fix reproduced with a real run; no defensive-check guard in the diff fails the reproduction+harm test.

## Fix outcome (fix step, 2026-10-27)

All 8 fix + 1 narrow items implemented; no new rules, settings, or flags added. Leave-open/dismissed items untouched.

- `.dockerignore`: added `backend/`-prefix + `**/` depth patterns (venv, caches, `tests/`, `.env*`). Rebuilt image: 1.04GB → 570MB; probe `ls /srv/backend/.venv`, `/srv/backend/tests`, `/srv/backend/.pytest_cache` all fail (exit 2).
- `modal_app.py`: `modal.App("zeroshot-qc")` + `modal_image` bound at module scope; image pins `backend/requirements.txt`; module-level `asgi_app` decorated via `@modal_app.function(image=...)` + `@modal.asgi_app()`; `build_modal_asgi` keeps the `RuntimeError` guard. Not live-runnable (AC5 human creds); proven by stub-`modal` tests.
- Narrow: `USE_FAKE_ADAPTERS` documented as inspect-only in README + `config.py` comment; no rewiring.
- README: stdlib-only `python3` one-liner creates `/tmp/zqc-data/probe.png` (+ "substitute any PNG/JPG"); fresh-dir run produces a CRC-valid 8x8 PNG, and the live container inspect of that exact file returns detections (`mask_rle.size [8,8]`).
- `.env.example`: `USE_FAKE_ADAPTERS=false` + one-line comment.
- Tests: `test_env_var_binds_to_settings` (setenv true/false/default), `backend/tests/test_modal_app.py` (4 stub tests; 3 fail on pre-fix code), `frontend/src/url-join.test.ts` via new `vitest run` script (7 tests; `normalizeApiBase` exported for it).
- Gates: `cd backend && .venv/bin/python -m pytest -q` → 171 passed; `npm run build` (tsc + vite) clean; `npm test` 7 passed; `npx oxlint` 0 errors (6 warnings pre-exist on base).
