# Falsify rulings — M6 (`feat/zeroshot-qc-m6`)

Scope: all 12 must-fix findings in `review-correctness.md` (C), `review-security.md` (S),
`review-structure.md` (St), `review-tests.md` (T), plus the 3 kept risks in
`review-impact.md` (I) as leave-open candidates. Every reproduction below is a real run
from this session (TestClient against the real app with isolated tmp `data_dir`, or
repo-wide grep for static claims); probe scripts were throwaway (`/tmp`, not committed).
Principle applied throughout: a **fix** must name a test that fails now and passes with
the fix; pure-structure findings with no such test cannot earn **fix**.

## Rulings (worst harm first)

fix: `POST /api/synth/generate` `defect` traverses out of `data/synth/` (C1). Reproduced: `{"profile_id":"screw","defect":"../escape-probe","n":1}` → 200 with PNGs written outside the profile dir; deep traversal → 200 escaping `data_dir`; `defect:"/abs"` → 500.
fix: synth `defect` → arbitrary file write, same bug as C1 (S1). Reproduced as above; write happens before `/files` containment matters, so the unfetchable URL is no mitigation.
fix: `PUT /api/profiles/{id}` accepts absolute `reference_image`, read off-disk and forwarded to the external judge (S2). Reproduced: full valid body with `"reference_image":"/etc/passwd"` → 200; `synth/generate.py:62-68` loads absolute paths. Security finding with a plausible path → fix per skill Limits.
fix: `POST /api/synth/generate` has zero tests (T1). Reproduced: `grep -c synth/generate test_routers.py` → 0; the route just proved to harbor a real traversal bug, so the regression pin (happy + `n<1` 422 + unknown-profile 404 + traversal 4xx) earns its keep.
fix: `PUT` invalid path id → 404 untested (T3). Reproduced: no such test in the suite (only body-id-mismatch 422); the branch pins the `save_profile` name-regex traversal guard, so a regression would be a wrong-state write, not just a label.
fix: `GET /files/...` missing-file/backslash/absolute branches untested (T5). Reproduced: only `..`/`%2E%2E` asserted; missing-file 404 probed live and is the hottest branch of the endpoint — one GET each.
fix: `from-sop` 422 paths untested (T4). Reproduced: only the happy draft flow is tested; the double-judge-failure → 422 `except` clause is app code with zero coverage (the empty-body half is framework `min_length` and needs no pin).
fix: undecodable image → 422 untested (T2). Reproduced: `grep` → 0; the `Image.open` failure branch is app code, one POST away.
cut: dead exports `generateSynthetic` + `toProfileBody` in `api.ts` (St1). Reproduced: each defined once, zero call sites repo-wide; ships an untested POST path nobody exercises — delete both (no UI implies them).
leave-open: PUT silently overwrites existing profiles, page-side confirm only (I1). Real (`os.replace`; page check bypassed by direct PUT) but low-likelihood (hand-crafted API calls only) and PUT-replace is intended semantics — a guard would need a new rule (e.g. 409/no-create flag).
leave-open: `errorDetail` triplicated across pages plus two inline copies (St2). Reproduced (3 defs + 2 inline ternaries) but zero runtime harm and no test can prove the dedup (no jsdom suite by plan decision), so it cannot earn fix.
leave-open: `profiles.py` lazily imports the SOP-judge factory from `app.main` (St3). Reproduced (real smell) but runtime-benign today; moving the factory touches the composition root for no behavioral gain and no failing-now test.
leave-open: gallery/eval routes return untyped `dict`s (St4). Reproduced (`-> list[dict]`, `-> dict`) but no failing-now test exists (current output already matches any model you'd add), so it cannot earn fix.
leave-open: overlay `bbox` assumed to be original-image pixels (I2). Hypothetical with current segmenters (all return pixels); failure mode is visual-only misplacement.
leave-open: eval `image_url` null when dataset files are absent (I3). Real degraded-but-not-wrong rendering on fresh checkouts; low harm.

## For the fixer

- cut: St1 — delete `generateSynthetic` + `toProfileBody` from `frontend/src/api.ts`.
- fix: C1/S1 (same bug, one fix) — validate `defect` (and `profile_id`) against `[A-Za-z0-9_-]+` in the router and/or `generate_pairs`; failing test now: `POST {"profile_id":"screw","defect":"../x","n":1}` → expect 4xx + no new files, currently 200 + writes.
- fix: S2 — constrain `reference_image` to a relative path under `data/` (resolve + containment) or reject absolute paths; failing test now: PUT absolute path → expect 4xx, currently 200.
- fix: T1, T2, T3, T4 (double-judge branch only), T5 — one POST/PUT/GET each; each test fails now (does not exist) and passes with the coverage.

## For the user

None — no finding requires a new rule or special case (I1's overwrite guard would, but it is ruled leave-open, not your-call).

## For the PR's open findings

- leave-open: PUT silently overwrites existing profiles (I1).
- leave-open: `errorDetail` triplicated across pages (St2).
- leave-open: router imports app entry for the SOP-judge factory (St3).
- leave-open: gallery/eval routes return untyped `dict`s (St4).
- leave-open: overlay `bbox` assumed to be original-image pixels (I2).
- leave-open: eval `image_url` null without dataset files (I3).

## Dismissed

None — every must-fix finding reproduced as claimed; nothing was wrong or already handled.

## Fix outcome

All 8 fix items + 1 cut item implemented; leave-open/dismissed untouched; no new rules, settings, or flags added.

- C1/S1: `routers/synth.py` rejects `profile_id`/`defect` outside `[A-Za-z0-9_-]+` with 422 before any write. Test `test_synth_generate_traversal_rejected_without_writes` fails on old code (200 + writes), passes now.
- S2: `put_profile` rejects absolute/`..`/backslash `reference_image` with 422; file untouched. Test `test_put_absolute_reference_image_rejected` fails on old code (200), passes now. Load paths (`run_inspection`, `load_good_image`) intentionally unchanged — existing judge tests use absolute tmp paths.
- T1/T2/T3/T4/T5: 7 new tests in `tests/test_routers.py` (synth happy + n<1 422 + unknown 404; undecodable image 422; invalid path id 404; from-sop double-judge 422; files missing/backslash/absolute 404). New coverage did not exist before; passes now.
- St1 (cut): deleted `generateSynthetic`, `toProfileBody`, plus the now-orphaned `SynthPair`/`SynthGenerateResponse`/`SynthGenerateRequest`/`parseSynthGenerateResponse` (required by `noUnusedLocals`) from `frontend/src/api.ts`. No call sites existed.

Verification: `cd backend && .venv/bin/python -m pytest -q` → 164 passed; `cd frontend && npm run build` (tsc -b + vite) → exit 0.
