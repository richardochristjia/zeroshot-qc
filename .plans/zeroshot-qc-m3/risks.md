# ZeroShot QC — M3 Risks

- Real-model prompt behavior is unproven without keys and docs; the fake proves the pipeline, not the model's judgment (`backend/app/prompts/judge.md`, `backend/app/adapters/muse_spark.py`). Check: manual criterion — run the CLI twice with strict then lenient rules against the real model.
- Retry doubles judge cost on malformed output; bounded to one retry then `JudgeValidationError` (`backend/app/adapters/muse_spark.py`). Check: stub double-malformed responses and confirm exactly 2 HTTP calls (covered in `backend/tests/test_judge.py`).
- `smoke.py` now also catches `JudgeValidationError` alongside `ValidationError`; a future adapter error type would exit via traceback instead of the clean `error:` line (`backend/scripts/smoke.py`). Check: stub a new error type in a real-mode smoke run.
- Missing `profile.reference_image` file fails the whole inspection with `ValueError` instead of judging without a reference (`backend/app/pipeline/inspect.py`). Check: point a profile at an absent path and run the CLI.
