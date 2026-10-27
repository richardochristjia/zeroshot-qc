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
