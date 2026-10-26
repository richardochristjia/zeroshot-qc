# Correctness review — M3 (branch `feat/zeroshot-qc-m3`)

Tier M, correctness only. Sources: [context-pack.md](.plans/zeroshot-qc-m3/context-pack.md)
(base `main`, 9 files +737/-40) and [plan.md](.plans/zeroshot-qc-m3/plan.md) acceptance
criteria. Every finding below is backed by a real run on this branch
(`cd backend && .venv/bin/python -m pytest -q` → **112 passed**).

## Must-fix (1)

### 1. Rules containing `{detections_table}` are silently rewritten — not verbatim
- Location: `backend/app/prompts/__init__.py:44-48` (`render_judge_prompt`).
- Contract: `ProductProfile.rules` is "shown to the judge verbatim"
  (`backend/app/schemas.py:30`); review scope requires "rules verbatim".
- Cause: three sequential `.replace` calls run schema → rules → table, so the
  last pass also rewrites any literal `{detections_table}` inside the already
  inserted rules text.
- Proof (real run):
  - `render_judge_prompt("Rule: ... {detections_table} ...", [])` →
    `verbatim-kept: False`.
  - Only that marker is affected: `{schema}`/`{rules}` inside rules survive
    (`True`/`True`), JSON-brace rules survive (`True`).
- Failing-now test (fails today, passes with the fix):
  `assert rules in render_judge_prompt(rules, [])` with
  `rules = "reject if {detections_table} appears"`.
- Suggested fix: single-pass substitution (e.g. replace against the template
  with placeholders substituted in one pass, or render table/schema first into
  locals and use a placeholder unlikely to collide — simplest is one regex
  pass over the three slots).

## Consider (2)

### 1. Syntactically-invalid JSON body skips retry and raises an untyped error
- Location: `backend/app/adapters/muse_spark.py:44-63` (catches only pydantic
  `ValidationError`; `response.json()` raising `JSONDecodeError` inside
  `_judge_via_meta_api` bypasses both the retry and `JudgeValidationError`).
- Proof: stubbed `httpx.post` returning a body whose `.json()` raises →
  `UNtyped JSONDecodeError calls=1` (no retry). Wrong-shape-but-valid JSON
  (a list) correctly retries and raises typed after 2 calls.
- Why only consider: the CLI still exits 1 cleanly (`JSONDecodeError` is a
  `ValueError`, caught in `cli.py:101`); the plan's "malformed JSON" test case
  is implemented as schema-invalid (covered); the real-model path is the
  manual criterion and `_judge_via_meta_api` is placeholder. The gap matters
  most for the future M6 422 mapping (typed error expected). Fix if cheap:
  treat body-decode failure as a validation failure inside the retry window.

### 2. Consistency rule treats empty strings inconsistently across its two arms
- Location: `backend/app/pipeline/inspect.py:108-111`.
- Proof: real-defect ruling with `rule_violated=""` keeps PASS (empty string is
  falsy), while `missed_defects=[""]` forces FAIL (non-empty list).
- Why only consider: the schema contract says "quote the exact rule, or null",
  so `""` is out-of-contract input from either the model or a caller; no test
  or acceptance criterion pins it. If tightened, prefer one rule for both arms
  (e.g. `rule_violated is not None` plus blank-check, or `min_length` on the
  schema) and add a test.

## Noted (verified correct, no action)

- **Retry-once semantics**: exactly 2 HTTP calls on first-malformed
  (`test_malformed_first_response_retries_once_then_validates`,
  `test_malformed_twice_raises_judge_validation_error`); retry prompt is the
  FULL prompt plus the validation error (probe: rules and `"verdict"` schema
  still present); second failure raises typed `JudgeValidationError`.
- **Consistency rule**: violation+PASS→FAIL and missed+PASS→FAIL both forced;
  real-defect-without-rule keeps PASS (no over-forcing); FAIL verdicts are
  stable (probe). All in-code, never trusted from the model.
- **Rules-override scoping**: call-only via `model_copy`; profile object never
  mutated (`rules=None` keeps profile rules, `rules=""` overrides with `""`,
  profile intact — probe). Cache key covers full profile JSON, so any rules
  edit is a miss (`test_identical_rules_hit_changed_rules_miss` passes).
- **Reference handling**: absent→None, explicit override wins over
  `profile.reference_image`, disk load works, missing file raises `ValueError`
  (all four tests pass); CLI `--reference` run exits 0, bad reference exits 1.
- **CLI exits**: bad profile / bad image / bad reference → exit 1 with `error:`
  lines; injected `JudgeValidationError` → exit 1 (probe); `--no-judge` output
  unchanged (no verdict block). Flip verified live: strict `--rules` → FAIL,
  lenient `--rules` → PASS, same image (acceptance criteria 1–2).
- **Prompt slots / table**: no leftover `{schema}`/`{rules}`/`{detections_table}`
  markers; table header and per-candidate rows accurate; empty detections →
  `(no candidates)`; `None` mm values → `-` (tests + CLI runs).
- **Smoke**: `scripts/smoke.py --fake` keeps count/verdict line shape, exit 0
  (acceptance criterion 3; suite green covers the rest).
- **Out of scope per context-pack** (not findings): real-model prompt behavior
  (manual criterion 5), placeholder Meta mapping, M6 422 mapping, M5
  `sop_to_profile`.
