# ZeroShot QC — M3 Tasks

Spec: `plan.md` in this folder. Tier: `tier.md` in this folder. Base: `main` (M2 PR #2 merged).

## Prompt + adapter
- [x] Create `backend/app/prompts/judge.md` (§7 verbatim, `{schema}`/`{rules}`/`{detections_table}` slots) plus a render helper and detections-table builder
- [x] Implement retry-once with appended validation error plus typed `JudgeValidationError` in `MuseSparkJudge.judge`, keeping the Meta mapping isolated

## Orchestrator
- [x] Add `rules` override (call-only, never persisted), reference override, judge step, and code-level FAIL-forcing consistency rule to `run_inspection`

## CLI + fakes
- [x] Add `--rules` (inline text) and `--reference` flags plus verdict/rulings printing to `cli.py`; keep `--no-judge` unchanged
- [x] Add deterministic scripted mode to `FakeJudge` keyed off rules text
- [x] Create `backend/tests/test_judge.py` (flip, retry-then-valid, double-failure error, both consistency cases, reference present/absent, cache hit/miss on rules)

## Verification
- [x] CLI without `--no-judge` prints a valid `Verdict`; a `--rules` edit flips it on a borderline image
- [x] `pytest` green; `scripts/smoke.py --fake` keeps its count/verdict line shape; grep guard clean on new source
- [x] Record Updates: reviewed implementation vs `plan.md` — it matches, but `plan.md` contains no verbatim record entries to append, and RECORD.md edits need human approval, so nothing was written (surfaced in final summary)

## Manual checks
- [ ] manual: with keys, official docs, and MVTec present, run the CLI twice (strict then lenient `--rules`) against the real model and confirm the verdict flips
