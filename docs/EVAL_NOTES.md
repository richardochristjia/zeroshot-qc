# Eval notes (M4)

How the harness is proven without real data, what the fixture shows,
and what the manual MVTec rerun must cover.

## Fixture (committed, `backend/tests/fixtures/mvtec/`)

Two synthetic categories (`widget`, `gizmo`), 48x48 flat-gray parts
with pure-red painted defects and exact masks, in MVTec layout.
`fixture.py` next to the PNGs regenerates them deterministically.
Per category: 2 train-good, 10 test-good, 20 test `scratch` defects
(16 large 6–12px rects, 4 tiny 2x2 ones).

## Failure patterns on the fixture (by construction)

- `sam_only` fails every image: the scripted segmenter always emits a
  fixed 2x2 false-positive box, so any-detection-means-FAIL has
  precision == prevalence and recall 1.0. This is the no-judge floor.
- `sam_judge` (no reference) fixes all good images — the tiny box is
  dropped by the size filter — but misses the 4 tiny real defects,
  which are indistinguishable from the hallucinated box by size alone.
  Expect precision 1.0, recall ~0.8 per category.
- `sam_judge_ref` recovers the tiny defects: their pixels differ from
  the reference while the hallucinated box matches it, so recall
  returns to 1.0 with precision intact.
- Measured fixture run (seed 0, `--adapter scripted`, 60 images):
  overall F1 `sam_only` 0.800 < `sam_judge` 0.889 < `sam_judge_ref`
  1.000 (asserted in `test_eval_run.py`); AUROC 0.500 / 0.900 / 1.000.
  Pixel IoU ~0.86 identical across modes — segmentation is shared, so
  IoU measures the segmenter while F1 measures the judge wiring. The
  gap from 1.0 is the scripted 2x2 false-positive box counted in the
  union plus the 4 tiny defects at half overlap.

## Prompt/profile changes made

- None from fixture evidence: the scripted fakes react to geometry,
  not wording, so the fixture cannot judge prompt quality. Eval
  profiles are in-memory (`build_eval_profile`) with fixed strict
  rules; the 10 new preliminary `backend/profiles/*.json` files are
  unvalidated drafts until real data lands.

## Risks and non-transfer warnings

- The fixture proves the harness plumbing (sampling, caching,
  metrics, ablation wiring), not real-world accuracy. Fixture F1
  numbers say nothing about MVTec performance.
- Scripted fakes separate the modes by construction; a real wiring
  bug that preserved the same call pattern could hide behind them.
  Mitigation: the runner test asserts per mode whether the judge ran
  through `run_inspection`, not just that the numbers differ.
- The loader assumes the documented MVTec archive layout
  (`train/good`, `test/<defect>`, `ground_truth/<defect>/*_mask.png`).
  A layout mismatch surfaces as the guidance error; fix the loader
  when real data lands.

## Synthetic images (M5, `data/synth/`)

`python -m app.synth.generate --profile bottle --defect scratch --n 10`
writes `data/synth/{profile}/_reference.png` plus
`data/synth/{profile}/{defect}/{i:03d}.png` and `{i:03d}_mask.png`
pairs (gitignored, never commit). `--fake` (the default) paints seeded
shapes offline with exact masks; `--no-fake` calls the real Muse Image
adapter. Generators without exact masks fall back to a grayscale
image-diff threshold (logged per image); an empty diff keeps the image
and omits the mask.

`python -m app.eval.run --data synth` reads that layout through the
same sampler, metrics, and ablations (`--mode`, `--adapter`,
`--seed` unchanged; `--synth-dir` selects the root). Every synth item
is defective, so expect recall near 1.0 and precision set by the
false-positive rate — AUROC is uninformative single-class (0.5 by
construction) and IoU measures mask overlap against the stored masks.
Sampling note: synth `n_defective` is per defect type (up to N images
from each `{profile}/{defect}/` dir), unlike MVTec `n_defective`
which caps the total defective images per category.

## Manual rerun (real MVTec — human steps)

1. Download MVTec AD (CC BY-NC-SA 4.0, non-commercial) into `data/`
   (gitignored, never commit) and set the model keys in `.env`.
2. Run all three modes on 5 categories, then all 15, e.g.
   `python -m app.eval.run --mode sam_judge_ref --adapter real
   --categories bottle cable capsule carpet grid` (from `backend/`).
3. Append the real failure patterns here: top confused defect types
   per category, reference-vs-no-reference deltas, and every
   prompt/profile change they motivate. Real-data patterns go below
   this line; do not edit the fixture section above.

## Real MVTec patterns (2026-10-27, single-image probes, real SAM 3.1 + Muse Spark)

- Bottle `broken_large/000`: SAM proposed nothing; judge FAIL (0.99) via
  missed defects, citing broken glass on the mouth rim. Safety net worked.
- Cable `cut_outer_insulation/000`: SAM proposed nothing; judge PASS (0.95).
  Owner confirms the PASS was correct under the rule (sheath notch, not a
  wire defect) — the test pick, not the judge, was wrong for wire coverage.
- Screw `scratch_head/000` (major visible head scratch, human-confirmed):
  SAM returned one whole-screw box, no localized box; judge PASS (0.85).
  Recorded as a silent pass on a defective part.
- Segmenter habit across all three: object-level boxes or silence, never
  defect-level localization (first-draft prompt wrapper, unoptimized).
