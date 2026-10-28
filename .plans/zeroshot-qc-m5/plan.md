# ZeroShot QC — M5: Synthetic defects + SOP import

Tier M (8 files, no sensitive paths; the one new endpoint is additive, unauthenticated, saves nothing). Loop and steps are in `tier.md` next to this file.

## Problem

Two gaps block the project's proof and its onboarding story: no test images exist (`data/mvtec/` is empty, so M4's harness only ever ran on the fixture), and creating a profile for a new product means hand-writing JSON. Muse Image can supply the first; Muse Spark's `sop_to_profile` stub (raising `NotImplementedError` since M1) can supply the second.

## Solution

- `synth/generate.py`: `--profile NAME --defect TEXT --n K [--fake]` loads a good image (profile reference or fixture), calls the image generator per item, derives masks by image-diff threshold when the generator returns none, writes image+mask pairs to `data/synth/{profile}/{defect}/`.
- `muse_image.py`: real call through the existing isolated mapping (still `TODO(meta-docs)`); fake paints seeded visible shapes and returns exact masks, so offline generation and eval-on-synthetic stay meaningful.
- `sop_to_profile.md` plus `sop_to_profile` with the judge's retry-once validation pattern; `POST /api/profiles/from-sop` returns the draft and saves nothing; double failure returns 422 like the judge's error shape.
- Eval `--data synth` reads `data/synth/` through the existing sampler, metrics, and ablations; `EVAL_NOTES.md` gains a synthetic section.

## Files

- `backend/app/synth/__init__.py`, `generate.py` — new; generation CLI, diff-mask fallback, `data/synth/` layout.
- `backend/app/adapters/muse_image.py` — change; real mapping stays isolated, fake paints seeded shapes with exact masks.
- `backend/app/prompts/sop_to_profile.md` — new; SOP-to-profile prompt templatized like `judge.md`.
- `backend/app/adapters/muse_spark.py` — change; implement `sop_to_profile` with retry-once validation, reusing the judge's error type.
- `backend/app/main.py` — change; add `POST /api/profiles/from-sop` (draft only, never saved).
- `backend/app/eval/dataset.py`, `run.py` — change; `--data synth|mvtec` source selection, synth layout reader.
- `backend/tests/test_synth.py`, `test_sop.py` — new; generation determinism, mask fallback, draft validation, 422 path.
- `docs/EVAL_NOTES.md` — change; synthetic section.

## Acceptance criteria

1. `python -m app.synth.generate --profile bottle --defect scratch --n 10` in fake mode writes 10 image+mask pairs; rerun is deterministic. Check: CLI runs in Verification.
2. Eval `--data synth` completes all three modes with a `summary.json`. Check: eval run in Verification.
3. `POST /api/profiles/from-sop` returns a valid draft and saves nothing; garbage twice returns 422. Check: TestClient calls in Verification.
4. `pytest` green; `data/` outputs gitignored; no secrets in new source. Check: suite plus grep guard.
5. `manual:` the same three against the real models with keys plus docs. Human steps: set `.env`, generate with the real image model and eyeball quality, paste a real SOP paragraph and judge the draft.

## Risks

- Diff-derived masks are approximate: threshold choice trades mask noise against missed faint defects; logged per image, and exact-mask generators bypass the diff entirely.
- The fake's painted shapes prove the pipeline, not real image-model quality; real generation quality needs human eyes (manual criterion).
- Real Muse Image edit/inpainting support is still unknown until docs arrive; the mapping stays isolated behind `TODO(meta-docs)` so the correction is one function.

## Test plan

- `test_synth.py`: same-seed determinism (byte-identical pairs); returned masks used verbatim; missing mask triggers diff fallback (non-empty for painted shapes); empty diff keeps the image, omits the mask, logs; layout paths exact.
- `test_sop.py`: valid paragraph drafts a `ProductProfile` without touching `backend/profiles/`; garbage twice gives 422; retry-once on first validation failure; unconfigured real adapter errors without network.
- Eval-on-synth runs in Verification (live run, not a unit test); existing eval tests guard the unchanged mvtec path.
- Run command: `cd backend && .venv/bin/python -m pytest -q` (project venv, never the host global interpreter).
