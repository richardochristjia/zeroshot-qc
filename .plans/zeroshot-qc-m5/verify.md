# M5 verify (taste-test, throwaway dirs under /tmp/zqc-m5; real `data/` untouched, `DATA_DIR=/tmp/zqc-m5/data`)

Setup: `cd backend`; all outputs routed to /tmp via `--synth-dir`/`--out-dir`; SOP checks via TestClient HTTP POSTs (`/tmp/zqc-m5/sop_check.py`, stub judge at app boundary so no network/keys; every assertion through real HTTP).

1. `cd backend && .venv/bin/python -m pytest -q` → `145 passed, 2 warnings in 1.59s`.
2. `.venv/bin/python -m app.synth.generate --profile bottle --defect scratch --n 10 --fake --synth-dir /tmp/zqc-m5/synth1` → `wrote 10 pairs`, 20 files (10 png + 10 mask, `mask=exact`); rerun to `/tmp/zqc-m5/synth2` + `diff -r -q` → identical, `DETERMINISTIC`.
3. `.venv/bin/python -m app.eval.run --data synth --mode {sam_only,sam_judge,sam_judge_ref} --categories bottle --adapter fake --synth-dir /tmp/zqc-m5/synth1 --out-dir /tmp/zqc-m5/eval-<mode>` → each wrote `results.jsonl and summary.json` (n=10, P/R/F1 1.000).
4. `.venv/bin/python /tmp/zqc-m5/sop_check.py` → valid draft `200`, id `bottle`, defects `['scratch', 'contamination stain']`, `profiles-dir untouched: True (16 files)`; garbage twice → `422`.
5. Secrets guard over new/changed M5 source (`synth/`, `muse_image.py`, `sop_to_profile.md`, `muse_spark.py`, `eval/dataset.py`, `eval/run.py`, `test_synth.py`, `test_sop.py`) → `SECRETS-GREP CLEAN`; `git check-ignore -q data` → ignored; `git status` shows no `data/` writes.
6. Criterion 5 is `manual:` (real keys + eyeball) — not tried, for the user.

Verdicts:

- pass: fake generate 10 pairs + deterministic rerun (20 files, diff identical).
- pass: eval `--data synth` all three modes with summary.json.
- pass: from-sop valid draft unsaved (profiles dir 16 files before/after) + garbage twice 422.
- pass: pytest green (145 passed); data/ gitignored; secrets grep clean.
- manual (for the user): real-model generate + SOP draft + docs eyeball with keys.
