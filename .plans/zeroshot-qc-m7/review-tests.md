# Tests review — M7 (`feat/zeroshot-qc-m7`)

Sources: [context-pack.md](.plans/zeroshot-qc-m7/context-pack.md) ("Test entry points", "Acceptance criteria",
"Do not re-derive") and `plan.md` "Test Strategies" (container probes, bundle grep, regression, README check).
Suite run for this review: `cd backend && .venv/bin/python -m pytest -q` → **166 passed**.
`grep -rln "modal\|resolveFileUrl\|normalizeApiBase\|cors_origins\|vercel\|dockerfile" backend/tests/`
→ **no hits**: all M7 deploy/wiring surface outside `test_fake_flag.py` is untested in-suite.

## must-fix

1. **`USE_FAKE_ADAPTERS` env→settings binding is untested.** `backend/tests/test_fake_flag.py`
   flips the flag with `monkeypatch.setattr(settings, "use_fake_adapters", …)` and no test in the
   repo calls `monkeypatch.setenv("USE_FAKE_ADAPTERS", …)`. The container probe path depends
   entirely on pydantic-settings parsing that env name, so the exact mechanism M7 added is proven
   only by the one-off manual container run. Add a test constructing `Settings` (or reloading
   config) with the env var set/unset.
2. **`modal_app.py` has zero committed tests.** No test covers the import-without-`modal` guard or
   the `build_modal_asgi` `RuntimeError` path — `plan.md` claimed "validated by import + config
   check", but that validation lives only in the phase-2 commit message, not in the suite, so any
   edit to the wrapper's branching regresses silently. Add a no-`modal`-stub import test plus the
   error-path test (both need no credentials).
3. **Frontend `normalizeApiBase`/`resolveFileUrl` have zero tests and no runner.**
   `frontend/package.json` has no `test` script and there are no `*.test.*` files, yet M7 added the
   trailing-slash normalization `plan.md` calls out as an edge case ("joins never double-slash").
   A build succeeding does not prove the join logic. Add a minimal runner (e.g. vitest) with one
   spec for slash variants, `blob:`/`data:`/absolute passthrough, and dev-empty-base behavior.

## consider

- **Container probe sequence is hand-typed, not scripted.** Health 200, fake inspect + overlay
  fetch, `/files/../` 404, unknown-profile 404, `Origin` CORS echo (plan Test Strategies, AC1)
  were proven live in phase 2 but no `scripts/verify-container.sh` preserves the sequence; the
  next re-prove starts from scratch. Consider committing the probe script (still run manually —
  it needs Docker, which is fine).
- **`test_flag_on_serves_fake_inspect` under-asserts.** It checks the fake-judge summary string
  and overlay fetch, but not unknown-profile 404 under flag-on, nor that the segmenter is the
  fake (only the judge is implied). `test_routers.py:143,249-254` covers 404/traversal in-process
  with real construction — consider one flag-on 404 case to close the combination.
- **`test_flag_off_default_is_real_construction` reaches into privates** (`_inner`, `_model_id`).
  It asserts real behavior today but will break on any adapter refactor that renames internals.
  Consider asserting via public surface (model-id property / non-`fake-` prefix) instead.

## noted

- Container probes, bundle grep, CORS `Origin` proof, and the README reader test are
  Verification-by-design (manual/live per `plan.md` Test Strategies), not pytest gaps — correctly
  out of suite. AC5 (human `modal deploy` / `vercel --prod` with human logins) is never automatable.
- No vacuous tests: an AST scan flagged 5 assert-less tests (`test_inspect.py:244`,
  `test_judge.py:358`, `test_schemas.py:25,41,46`), but all use `pytest.raises` — each asserts.
  Both `test_fake_flag.py` tests assert.
- `test_routers.py` already covers `/files` traversal 404 and unknown-profile 404 in-process;
  M7 did not regress them (suite green). What is missing is only those paths *under the flag* and
  *against the container*.
- `modal_app.py` push commands are documented-not-run (no creds in this environment) — accepted
  per plan Anti-Goals; the must-fix above asks only for the credential-free import/error paths.
