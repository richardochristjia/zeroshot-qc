# Handoff — carried-open items (M1–M6 → post-M7)

Source: `.plans/zeroshot-qc-m7/check-3.md` inventory. Location choice: no
handoff list existed in the repo (no `ROADMAP.md`; `docs/` held only
`EVAL_NOTES.md`; no file matched handoff/carry/future-work), so the carry
list lives here in `docs/HANDOFF.md`.

Already settled, not carried: M1-LO1 (subsumed by M6-St3, no new fix),
M1 gap Next #1 / corrected Record entry (done, `.agents/RECORD.md:44`),
M5 `n_defective` per-type semantics (docs fix in `docs/EVAL_NOTES.md`),
M3/M4 (nothing carried).

## Code debt (owner: future-work unless noted)

- M1-LO2 — cache-key/model-ID divergence (`pipeline/cache.py:157-159,185-187`
  snapshot at wiring while adapters re-read live settings). Owner:
  future-work. Next: constructor injection only if a
  settings-mutation-mid-run path ever appears (unreachable today).
- M2-F2 — CLI same-stem overlay overwrite (`cli.py:107` plain
  `{stem}_overlay.png` vs smoke's collision scheme). Owner: user (naming
  call). Next: user picks the convention; suggested: smoke's suffix scheme
  (`backend/scripts/smoke.py:183-206`). Do not fix without that call (M7
  AC3: config/wiring only). Live 2026-10-27: all three manual CLI runs
  saved `000_overlay.png`, so each erased the last (only the screw overlay
  survived); smoke discovery also picked `ground_truth/*_mask.png` and
  synth `_reference.png` instead of photos on a full MVTec tree. Fix covers
  both: skip masks/reference in discovery and use unique per-input overlay
  names.
- M2-LO — `inspect_image`/CLI unification: disk-loader
  (`pipeline/inspect.py:216`) has no production caller while the router
  (`routers/inspect.py:96`) hand-rolls the same path. Owner: future-work.
  Next: unify only with a failing test that justifies touching the
  composition root.
- M6-St2 — `errorDetail` triplicated across pages (`Eval.tsx:13`,
  `Synthetic.tsx:6`, `Profiles.tsx:15` + inline ternaries
  `Inspect.tsx:74,113`). Owner: future-work. Next: dedup into a shared
  helper once a jsdom suite exists to prove it (zero runtime harm today).
- M6-St3 — lazy router→`app.main` import (`routers/profiles.py:43-47`).
  Owner: future-work. Next: hoist the factory into `pipeline/wiring.py`
  only for a behavioral gain (runtime-benign today).
- M6-St4 — untyped gallery/eval route dicts (`routers/synth.py:41`
  `-> list[dict]`). Owner: future-work. Next: add Pydantic response models
  when the output shape diverges from the dicts.
- M6-I1 — PUT silently overwrites existing profiles (`os.replace` in
  `put_profile`, `routers/profiles.py:72-89`; intended-replace semantics).
  Owner: user (rule call). Next: user decides the rule (409 / no-create
  flag); the run must not invent it.
- M6-I2 — overlay `bbox` assumed to be original-image pixels. Owner:
  future-work. Next: re-probe overlay placement when the first non-pixel
  segmenter lands (hypothetical today; failure is visual-only).
- M6-I3 — eval `image_url` null when dataset files are absent (degraded,
  not wrong, rendering on fresh checkouts). Owner: future-work. Next:
  improve the empty state if the harm grows.
- M5/M3-consider leftovers — evaluated, never promoted to open findings;
  all need app-behavior change (M7-AC3-blocked). Owner: future-work. Next:
  promote any of these only with a failing test plus behavior-change
  approval: M3-C1 JSON-decode retry (`adapters/muse_spark.py:44-63`),
  M3-C2 empty-string consistency (`pipeline/inspect.py:108-111`), M5
  whitespace-only SOP validation, M5 `_validate_profile` name clobber on
  empty-id backfill, M5 `_`-prefixed defect-dir discovery mismatch
  (`dataset.py:159` vs `191-193`).

## Manual checks (owner: user — keyless/in-run unsettlable)

- M1-AC6 — real-keys smoke readout (Meta docs + keys + MVTec dataset was
  never run). Next: human runs `cd backend && python scripts/smoke.py`
  with keys + dataset before submission.
- M2-AC5 — CLI on 3 real MVTec images (never run). Next: human runs the
  CLI against 3 real MVTec images.
- M6-G0 — second-device walkthrough (upload, rule flip, SOP import,
  gallery from another device on the LAN). Next: human walkthrough before
  submission.
