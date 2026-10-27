# Structure review — M7 (branch feat/zeroshot-qc-m7)

Source: [.plans/zeroshot-qc-m7/context-pack.md](.plans/zeroshot-qc-m7/context-pack.md).
Scope: structure only (flag placement, wrapper thinness, URL normalization,
README organization, carry-list placement). Behavior/security/correctness are
covered by the sibling reviews.

## Must-fix

1. `modal_app.py:33` — Modal image is bare `debian_slim()` with no
   requirements. Why it costs: the deployed function imports the full
   backend (`app.main` → SAM/Muse adapters, FastAPI, pydantic); with no
   `pip_install_from_requirements` (or equivalent) the Modal cold start
   dies on `ImportError`, so the M7-AC5 push path (README "Push to a public
   URL") deploys a dead backend. Fix: pin the image to
   `backend/requirements.txt` (same file the `Dockerfile` installs).
2. `modal_app.py:32-38` — the `modal.App("zeroshot-qc")` object is created
   inside `build_modal_asgi` and never bound at module scope; only the
   wrapped function escapes as `asgi_app`. Why it costs: `modal deploy
   modal_app.py` discovers module-level App objects — with the App hidden
   in a closure the deploy entrypoint may find nothing to deploy, failing
   the one human push command M7 exists to enable. Fix: bind
   `modal_app = modal.App(...)` at module scope (guarded like the import)
   and decorate a module-level asgi function.
3. `backend/app/routers/inspect.py:38,50` vs `backend/app/routers/profiles.py`,
   `backend/app/routers/synth.py:29`, `backend/app/eval/run.py:77-79` —
   `USE_FAKE_ADAPTERS` is honored only by the inspect router although the
   name (and `backend/app/config.py:27` global placement) promises
   container-wide fake mode. Why it costs: a probe/run with
   `USE_FAKE_ADAPTERS=true` still routes from-sop/eval/synth through real
   (or separately-faked) adapters, so "fake container" means different
   things per endpoint and the next prober debugs per-route 500s. Fix:
   either scope the name/docs to inspect (`FAKE_INSPECT_ADAPTERS`) or read
   the flag in the shared layer (`pipeline/wiring.py`) so all routers
   inherit it.
4. `.env.example` (no `USE_FAKE_ADAPTERS` line) vs
   `backend/app/config.py:27` — the flag is missing from the canonical env
   catalog. Why it costs: `.env.example` is the stranger's only complete
   key list (README "Setup" points there); an undocumented 9th key is
   undiscoverable and its default-real guarantee is unverifiable from
   setup docs. Fix: add `USE_FAKE_ADAPTERS=false` with a one-line comment.

## Consider

5. `frontend/src/api.ts:505` duplicates the join (`${API_BASE}${url}`)
   instead of delegating to `apiUrl` (`api.ts:486-488`). Why it costs: two
   join sites today; a future fix (leading-slash guarantee, runtime
   override) must land in both or images and fetches diverge by origin.
   Fix: `return apiUrl(url)` after the passthrough guard.
6. `modal_app.py:14` unconditionally mutates `sys.path`, unlike the guarded
   insert in `cli.py`. Why it costs: importing the wrapper (e.g. from
   tooling/tests) prepends unconditionally and can shadow an installed
   `app` package; the repo already has the guarded pattern to copy.
7. `README.md:128-139` keeps the submission checklist and the verbatim
   reader-test log in the user-facing README. Why it costs: process meta
   rots faster than instructions (checkbox states age on every milestone)
   and buries the clone-to-run path; the next milestone edits history,
   not docs. Fix: move checklist state + reader test to
   `docs/HANDOFF.md` (or the plan dir), keep README to run/deploy only.

## Noted (no action)

- Flag default-real guarantee holds end to end: `config.py:27` defaults
  `False`, the `Dockerfile` sets no `USE_FAKE_ADAPTERS` (image is real by
  default), and `wiring.py:18,31` keeps pure `bool` params so
  `cli.py:83,89` / `smoke.py:42` / `eval/run.py:77-79` are unaffected.
  Router reads global `settings` per request (`inspect.py:38,50`) — couples
  the request path to mutable global state, but the test seam
  (`test_fake_flag.py:54,70`) covers it; acceptable.
- `api.ts:478-483` single normalization point (`normalizeApiBase` strips
  trailing slashes once, `API_BASE` const, dev-empty → proxy fallback) is
  the right shape; all four `fetch` sites and all four `img src` sites go
  through it. Untested directly (no jsdom suite — see HANDOFF M6-St2), but
  that is a test gap, not a structure gap.
- Carry list in `docs/HANDOFF.md` is correctly placed: it documents why
  (`HANDOFF.md:3-6`, no prior list existed), `.dockerignore` excludes
  `docs/` from the image so it ships zero bytes, and roles vs
  `.agents/RECORD.md` (decisions log) do not overlap.
- README missing architecture diagram + metrics table is already recorded
  as PARTIAL in the context pack — not re-raised here.
