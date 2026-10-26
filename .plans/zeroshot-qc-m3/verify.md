# Verify — ZeroShot QC M3 (Judge)

Date: 2026-10-26. Branch: `feat/zeroshot-qc-m3`. Single pass, no re-runs.

## 1. Full suite (run once)

`cd backend && .venv/bin/python -m pytest -q`

```text
113 passed, 2 warnings in 0.76s
```

Warnings are pre-existing RLE size-mismatch `UserWarning`s from `measure.py` in unrelated tests.

## 2. Live CLI runs (placeholder image, `--fake` adapters)

Image: 200x200 gray PNG written to `/tmp/verify-m3.png`.

`backend/.venv/bin/python cli.py inspect /tmp/verify-m3.png --profile bottle --fake`

```text
d1 broken bottle glass score=0.93 area_px=352 length_px=87.0 area_mm2=3.52 length_mm=8.70
d2 contamination stain score=0.59 area_px=1274 length_px=48.0 area_mm2=12.74 length_mm=4.80
d3 chip on bottle score=0.59 area_px=3564 length_px=98.0 area_mm2=35.64 length_mm=9.80
verdict: FAIL confidence=0.90
ruling d1: real_defect=True ... reason=Fake judge: scripted strict-mode failure of the first candidate.
ruling d2: real_defect=False ... / ruling d3: real_defect=False ...
summary: Fake judge: first candidate violates the rules, part fails.
```

Valid `Verdict` printed: verdict + confidence + per-ruling reasons + summary. PASS on
criterion 1 (fake proves the pipeline; real-model behavior stays manual per criterion 5).

Rerun with `--rules "lenient: pass everything"` (no other change):

```text
verdict: PASS confidence=0.90
summary: Fake judge: all candidates dismissed, part passes.
```

FAIL flips to PASS. PASS on criterion 2 (mechanical half).

`--no-judge` rerun prints the 3 detection lines plus the overlay line only — no
`verdict:`/`ruling`/`summary` lines. Detections-only path unchanged.

## 3. Smoke `--fake` shape

`cd backend && .venv/bin/python scripts/smoke.py --fake`

```text
placeholder_1: scratch=1, crack=1, dent=1
placeholder_2: scratch=1, crack=1, dent=1
placeholder_3: scratch=1, crack=1, dent=1
verdict: {"verdict":"PASS","confidence":0.9,"rulings":[...],"missed_defects":[],"summary":"Fake judge: all candidates dismissed, part passes."}
```

Count lines plus one `verdict:` JSON line — shape kept. PASS on criterion 3 (with §1).

## 4. Grep guard (criterion 4)

Changed source vs `main`: `backend/app/adapters/{fakes,muse_spark}.py`,
`backend/app/pipeline/{inspect,wiring}.py`, `backend/app/prompts/{__init__.py,judge.md}`,
`cli.py`. Added lines contain no model ID, endpoint, URL, key, secret, or token:
strict grep over added lines returns zero matches (only false positive excluded was
the `+++ b/...muse_spark.py` diff header). `muse_spark.py` reads `judge_model_id`
and `meta_api_base_url` from settings (env); `judge.md` has zero secret-like matches.
PASS on criterion 4.

## 5. RECORD.md check — DISCREPANCY, not a failure

`.plans/zeroshot-qc-m3/plan.md` contains **no verbatim record entries** — no
`- (...)` lines anywhere in `.plans/zeroshot-qc-m3/`, and `tasks.md` already
records that nothing was appended because RECORD.md edits need human approval.
So there are no "3 judge entries from plan.md" to confirm; `.agents/RECORD.md`
is byte-identical to `main` (empty diff). Nothing was written: unattended run,
no human to approve, per the RECORD editing rule. The 3 judge facts a human may
want to approve later (judge prompt §7, code-level FAIL forcing, call-only rules
override) are proposed in the parent summary, not applied here.

## Verdict

All runnable criteria (1–4) PASS. Nothing failed, so no `fix(m3)` commit was made.
Manual criterion 5 (real model + keys + MVTec) remains open by design.
