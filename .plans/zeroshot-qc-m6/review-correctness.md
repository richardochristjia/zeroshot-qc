# M6 correctness review — branch `feat/zeroshot-qc-m6`

Sources: [.plans/zeroshot-qc-m6/context-pack.md](.plans/zeroshot-qc-m6/context-pack.md) (claims cited as CP §n by its headings) and
plan.md acceptance criteria AC1–AC5. Suite: `cd backend && .venv/bin/python -m pytest -q` → **157 passed**;
`cd frontend && npm run build` (`tsc -b && vite build`) → exit 0; secrets grep clean (only hit is the
"No secrets here" comment in `frontend/src/api.ts`). Probes below ran against `TestClient` with isolated
tmp `data/`/`profiles/` (scripts in `/tmp/probe_m6.py`, `/tmp/probe_m6b.py`, not committed).

## Must-fix

### 1. `POST /api/synth/generate` `defect` traverses — arbitrary PNG write outside `data/synth/` (even outside `data/`)
- Contract: pairs land under `data/synth/{profile}/{defect}/` (CP "Files", plan step 4).
- Code: `_GenerateBody.defect: str` unconstrained (`backend/app/routers/synth.py:32-37`); `generate_pairs`
  does `root / profile_id / defect` + `mkdir(parents=True)` (`backend/app/synth/generate.py:104-106`) with no guard.
- Proof (real runs, fake generator, isolated tmp data dir):
  - `defect="../escape-probe"` → 200; files land at `data/synth/escape-probe/000.png` (outside the profile dir)
    and are **invisible to the gallery** (gallery needs `category/defect/file` depth) — orphaned writes.
  - `defect="../../evil-x"` → 200; `data/evil-x/` created — escaped `data/synth/`.
  - `defect="../../../../OUTSIDE"` → 200; `<TMPDIR>/OUTSIDE/000.png` + `000_mask.png` written —
    **escaped `data_dir` entirely** (canary cleaned up after).
- Failing test now (would pass with fix): `POST {"profile_id":"screw","defect":"../x","n":1}` → expect 4xx
  and no new files under `data/`; currently 200 + writes.
- Fix: validate `defect` (and `profile_id`) against the existing `[A-Za-z0-9_-]+` guard
  (`pipeline/inspect.py:_PROFILE_NAME_RE`) in the router (422/404) and/or `generate_pairs`; the gallery and
  `/files` readers already assume that shape.

## Consider

### 2. Whitespace-only `rules` judges with blank rules instead of falling back to profile rules
- CP ("Do not re-derive") claims clearing rules restores profile rules via falsy→`None`
  (`routers/inspect.py:129`: `rules if rules else None`) — but `"   "` is truthy, and `run_inspection`
  applies any non-`None` rules (`pipeline/inspect.py:212-213`).
- Proof: same image, no-rules vs `rules="   "` → `rule_violated` is the profile text vs `'   '`
  (judge ran with a blank rulebook). Frontend never sends this (trims first), so raw-API-only impact.
- Fix: `rules.strip() or None` server-side. Failing test now: post `rules=" "` → rulings cite profile rules.

### 3. Frontend maps every non-decode 422 on inspect to `InspectJudgeError` — including missing-field validation
- Proof: `POST /api/inspect` without `image` → 422 `{"detail":[{"type":"missing","loc":["body","image"],…}]}`;
  `api.ts:547-553` throws `InspectJudgeError` for anything not starting with `"could not decode image"`.
- Unreachable from the UI (Inspect button disabled without a file); only error-label accuracy.
- Fix: route array-shaped `detail` to `RequestValidationError`.

### 4. One malformed `summary.json` breaks the whole Eval list *and* detail views
- Proof: `data/runs/legacy/summary.json` = `{}` → `GET /api/eval/runs` 200 `[{}]`; `GET …/legacy` 200.
  `parseEvalRunSummary` requires `run_id` (`api.ts:444`), so the single bad entry throws for the entire list —
  backend skips unreadable JSON but not wrong-shaped dicts.
- The writer always emits `run_id`; only hand-placed/legacy files trigger it.
- Fix (either): backend skips summaries that aren't dicts with a string `run_id` (extends the existing
  "skip dirs lacking summary.json" rule); or frontend skips unparseable entries per-row.

## Noted (verified, no change)

- **PUT atomicity**: 422s fire before the handler (untouched file covered by suite); `save_profile` temp +
  `os.replace` with cleanup; `PUT /api/profiles/bad%20id` → 404, no stray file (probed). Matches CP/AC.
- **Gallery grouping**: suite asserts exact `[{category, defect, image_url, mask_url}]`, `_reference.png` skip,
  mask-absent→null; passing.
- **`/files` traversal**: `..`, absolute, backslash, `%2e`, `..%2f`, double-encoded `%252E` all 404 (probed);
  resolve-containment backstop intact.
- **Inspect 422/404 paths**: double-judge-failure 422, undecodable-bytes 422, unknown-profile 404 — all in suite.
- **Judge-only rerun**: suite asserts second POST with new rules leaves segment calls at 1. CP construction claim holds.
- **CLI parity**: suite asserts identical verdict word + detection count CLI-vs-route; passing.
- **Eval read-only**: `Eval.tsx` calls only `listEvalRuns`/`getEvalRun`; no page except Profiles/Inspect mutates,
  and Synthetic has no generate button. Matches plan decision.
- **Inspect debounce + stale abort**: single `abortRef` serializes submit + debounced re-posts; keystroke aborts
  in-flight, cleanup aborts on change/unmount, `AbortError` swallowed (`Inspect.tsx:90-155`). Verified by reading
  (no jsdom suite per plan decision).
- **SOP save-as-new confirm**: draft never saves (suite); page GET-checks existence and requires explicit overwrite
  arming before PUT (`Profiles.tsx:134-195`). Residual check-then-act TOCTOU vs a concurrent writer is inherent to
  the pinned page-side design; single-user demo scope.
- **FakeJudge vs real judge SOP ids**: real `_slugify_category` sanitizes; `FakeJudge.sop_to_profile` uses
  `category_name` verbatim, so a multi-word category in fake/dev mode drafts an unsavable id (PUT → 404). Pre-M6
  fake code, dev-only; flag for M7, not this branch.
- **Dismissed (investigated, not a bug)**: feared `auroc: null` crash in `parseCategoryMetrics` — `summarize()`
  always emits numeric `auroc` (0.5 single-class, `metrics.py:58-67`) and records always carry every row key
  (`run.py:179-190`); parsers are safe for all writer outputs.
- **AC5** (`manual:` second-device walkthrough) is human-only; not verifiable here.
