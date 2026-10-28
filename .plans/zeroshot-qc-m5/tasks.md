# ZeroShot QC — M5 Tasks

Spec: `plan.md` in this folder. Tier: `tier.md` in this folder. Base: `main` (M4 PR #4 merged).

Durable-test rule: `test_synth.py` and `test_sop.py` are deliverables in the repo's pytest layout — keep the smallest focused tests with the project, prove each fix with a failing-first test, and run the full suite once at the end (not after every edit).

## Generator
- [x] Upgrade the fake image generator to paint seeded visible shapes with exact masks; keep the real mapping isolated with `TODO(meta-docs)`
- [x] Implement `synth/generate.py` (`--profile --defect --n [--fake]`, diff-mask fallback, empty-diff logging, `data/synth/` layout)
- [x] Create `test_synth.py` (determinism, verbatim masks, diff fallback, empty-diff behavior, layout paths)

## SOP import
- [x] Create `sop_to_profile.md` and implement `sop_to_profile` with retry-once validation, reusing the judge's error type
- [x] Add `POST /api/profiles/from-sop` (draft only, never saved; 422 on double failure)
- [x] Create `test_sop.py` (valid draft unsaved, garbage-twice 422, retry path, unconfigured-adapter guard)

## Eval on synthetic
- [x] Add `--data synth|mvtec` to the eval runner with a synth layout reader reusing sampler/metrics/ablations
- [x] Append the synthetic section to `docs/EVAL_NOTES.md`

## Verification
- [x] Fake generate writes 10 deterministic image+mask pairs; eval `--data synth` completes 3 modes with `summary.json`
- [x] `from-sop` returns a valid unsaved draft via TestClient; garbage twice gives 422
- [x] `pytest` green; `data/` outputs gitignored; grep guard clean on new source
- [x] Record Updates: append the 3 synth/profiles entries from the approved plan — first (1) review the complete implementation; (2a) if it matches, write those exact entries into `.agents/RECORD.md`; (2b) if it diverged, write nothing and surface the divergence in the final summary instead. (Note: Tier M spec format has no Record section by rule — the entries live in the approved chat plan: the data/synth pairs entry, the diff-mask entry, the from-sop draft entry.)

## Manual checks
- [ ] manual: with keys and docs, generate with the real image model and eyeball quality; paste a real SOP paragraph and judge the draft profile
