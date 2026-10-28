# ZeroShot QC — M3: Judge (Muse Spark rules engine)

Tier M (6 files, no sensitive paths, no auth). Loop and steps are in `tier.md` next to this file.

## Problem

`cli.py inspect` without `--no-judge` still has no judge: M2's smoke calls the judge directly with a hardcoded smoke profile, and nothing builds the HANDOFF §7 prompt (part image plus labeled overlay plus reference plus detections table plus verbatim rules), validates the model's JSON against `Verdict` with one retry, or enforces the consistency rule (any real defect with a violated rule, or any missed defect, forces FAIL) in code rather than trusting the model.

## Solution

- New `backend/app/prompts/judge.md`: the HANDOFF §7 prompt verbatim with `{schema}`, `{rules}`, `{detections_table}` slots.
- `MuseSparkJudge.judge` renders the prompt, sends image plus overlay plus optional reference through the existing isolated Meta mapping, validates the response as `Verdict`, retries once with the validation error appended, and raises a typed `JudgeValidationError` on the second failure.
- `run_inspection` gains `rules: str | None` (replaces `profile.rules` for that call only), an optional reference override, and a judge step: segment, measure, overlay, judge, then force FAIL in code when any ruling cites a violated rule or `missed_defects` is non-empty.
- CLI gains `--rules "..."` (inline text) and `--reference path` (else `profile.reference_image`); it prints the verdict plus per-ruling reasons. The `--no-judge` path is unchanged.
- `FakeJudge` gains a deterministic scripted mode driven by rules text (e.g. lenient wording passes, anything else fails the first candidate) so the borderline-flip test runs offline.

## Files

- `backend/app/prompts/judge.md` — new; §7 prompt with `{schema}`, `{rules}`, `{detections_table}` slots.
- `backend/app/adapters/muse_spark.py` — render prompt, retry once with the validation error appended, raise `JudgeValidationError` on second failure; mapping stays in the isolated function.
- `backend/app/pipeline/inspect.py` — `rules` and reference-override params, judge step, code-level consistency rule forcing FAIL.
- `backend/app/adapters/fakes.py` — scripted `FakeJudge` mode keyed off rules text; deterministic, no network.
- `cli.py` — `--rules` inline-text flag, `--reference` flag, verdict plus rulings printing.
- `backend/tests/test_judge.py` — new; retry path, consistency forcing, rules flip, cache behavior on rule change.

## Acceptance criteria

1. `python cli.py inspect <image> --profile bottle` prints a valid `Verdict` (verdict, confidence, per-detection rulings, summary). Check: CLI run in Verification.
2. A `--rules` edit flips the verdict on a borderline image with no other change. Check: `test_judge.py` flip case plus CLI run.
3. `pytest` is green and `scripts/smoke.py --fake` keeps its count/verdict line shape. Check: full suite plus smoke run.
4. No model ID, endpoint, or key in new source; prompt file carries no secrets. Check: grep guard in Verification.
5. `manual:` the same flip against the real Muse Spark model with keys plus official docs. Human steps: paste docs, set `.env`, download MVTec, run the CLI twice with strict then lenient rules.

## Risks

- Real-model prompt behavior is unproven without keys and docs; the fake proves the pipeline, not the model's judgment. Kept as the manual criterion.
- Retry doubles judge cost on malformed output; bounded to one retry, then a typed error instead of an infinite loop.
- `JudgeValidationError` is a new exception type; CLI must catch it to exit 1 with a clean message, and the M6 router will map it to HTTP 422 (router work stays out of M3).

## Test plan

- `test_judge.py`: scripted-rules flip (same image and detections, verdict changes); malformed-first JSON retries once then validates; malformed-twice raises `JudgeValidationError`; real-defect ruling with model-side PASS forces FAIL; non-empty `missed_defects` with PASS forces FAIL; reference present versus absent both validate; changed rules cause a cache miss, identical rules a hit.
- CLI and smoke stay in Verification (live runs, not unit tests); existing `test_inspect.py` guards the unchanged `--no-judge` path.
- Run command: `cd backend && .venv/bin/python -m pytest -q` (project venv, never the host global interpreter).

## Divergence notes

- Supporting change (not a behavior divergence): `backend/app/pipeline/wiring.py` gained `build_judge` alongside `build_segmenter` so the CLI's fake/real judge selection and `"fake-judge"` cache id share one definition instead of drifting; `backend/scripts/smoke.py` now also catches `JudgeValidationError` so its real-mode validation-failure exit stays a clean `error:` line. Both follow the plan's intent; no acceptance criterion changed.
