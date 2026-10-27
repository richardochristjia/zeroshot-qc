# M6 tests review — `backend/tests/test_routers.py` vs plan

Sources: [context-pack.md](.plans/zeroshot-qc-m6/context-pack.md) ("Test entry points", "API contracts");
[plan.md](.plans/zeroshot-qc-m6/plan.md) "Test Strategies" (8-item table), "Edge Cases & Gotchas".
Branch: `feat/zeroshot-qc-m6`. Suite: 12 passed (`cd backend && .venv/bin/python -m pytest -q`).
Frontend: `npm run build` clean (tsc + vite, 128ms); secrets grep hits only the
`No secrets here` comment in `frontend/src/api.ts` (false positive, fine).
No test asserts nothing — every `test_*` has real assertions. No jsdom suite is a plan decision (walkthrough only), not a gap.

Coverage check (plan table → test): inspect happy+overlay ✓, judge-only cache hit ✓,
double-judge 422 ✓, unknown profile 404 ✓, invalid PUT 422 + file untouched ✓,
from-sop-save-only-on-confirm ✓, missing run 404 ✓, `/files/../` blocked ✓, CLI parity ✓,
gallery grouping ✓ (divergence endpoint, beyond plan table).

## must-fix

1. `POST /api/synth/generate` has zero tests — happy path, `n<1`→422, unknown profile→404
   all untested (`grep -c synth/generate tests/test_routers.py` → 0). Probed live: 200/422/404
   all behave correctly, so this is pure regression risk on a whole route
   (`backend/app/routers/synth.py:83-122`).
2. Undecodable image → 422 untested. Contract in context-pack ("422 ... undecodable image"),
   code at `backend/app/routers/inspect.py:112-118`; probed `b"not-an-image"` → 422. One POST away.
3. `PUT /api/profiles/{id}` with invalid path id → 404 untested (router
   `backend/app/routers/profiles.py:73-77`, contract in context-pack). Probed → 404. The
   round-trip test covers 422s only, never the 404 branch.
4. `POST /api/profiles/from-sop` 422 paths untested: empty body (FastAPI `min_length=1`) and
   double judge failure → 422 (`backend/app/routers/profiles.py:88-91`). Probed empty → 422.
   Only the happy draft+confirm flow is tested.
5. `GET /files/...` beyond traversal untested: missing file, backslash, absolute path all 404
   per `backend/app/main.py:42-66` but only `..`/`%2E%2E` are asserted. Probed missing → 404,
   backslash → 404. Missing-file 404 is the most-hit branch in production.

## consider

- Eval traversal test uses only encoded `%2E%2E`, not a literal `..` segment (TestClient may
  normalize the latter); either assert both or comment why one suffices.
- CLI parity asserts verdict + detection count only, not overlay URL fetchability or
  `timings_ms` keys — cheap to extend `test_cli_parity_identical_verdicts` since the route
  already returns them.
- Gallery ordering relies on `sorted()` but the test seeds one category; a second category
  would lock the cross-category order the Synthetic page depends on.
- `test_files_traversal_blocked` takes unused `tmp_path` and writes a canary outside
  `data_dir` without asserting data-dir containment directly — harmless, could drop the fixture.

## noted

- Frontend has no unit suite by plan decision (plan.md Test Strategies: "no jsdom suite in M6");
  `tsc` + `vite build` + walkthrough is the agreed gate, both green here.
- Judge-only cache-hit test pins behavior via `inner.calls == 1` and a verdict flip — good;
  it depends on FakeJudge leniency-string sensitivity, so a fake change breaks it loudly (intended).
- Isolation fixture (tmp `data_dir` + `PROFILES_DIR` monkeypatch) means `data/` writes never
  escape; verified `git status` shows no `data/` writes from the suite.
