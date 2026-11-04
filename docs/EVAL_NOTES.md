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
- Rules steerability (cable `cut_outer_insulation/000`, same photo):
  placeholder draft rule PASS (0.95); strict wording FAIL (0.95) via missed
  defect with a precise cut description; lenient wording FAIL (0.90), calling
  the cut large and obvious. Verdict follows wording; the earlier PASS was the
  rule's fault.

## Real MVTec eval (2026-10-27, 5 categories x 30, real adapters, seed 0)

- `sam_only`: F1 0.000 everywhere. No boxes, no catches.
- `sam_judge`: F1 0.872 overall (carpet/grid 1.000, cable 0.625 on recall 0.500).
- `sam_judge_ref`: F1 0.919 overall (capsule 0.976, cable 0.778, recall 0.910).
- Reading: the judge carries the system through the missed-defect path; the
  reference adds recall; the segmenter adds nothing on these categories.
  IoU 0.000 throughout (no masks proposed).
- Real synth (bottle/scratch x5, real Muse Image): 4 of 5 carry visible
  scratches with aligned masks; 1 returned clean (empty-diff path keeps the
  image, omits the mask). Real SOP draft for bottle returns usable prompts
  and rules, unsaved.

## Grounded mode and rule tuning (commands)


- Grounded eval: SAM finds the part, the judge sees the padded crop and returns
  0-1000 boxes for missed defects, which become `j1..` detections. Adds
  `localization.hit_rate` (a box covers at least 50% of the true defect) and
  `box_iou` per category.
  `cd backend && .venv/bin/python -m app.eval.run --mode grounded --adapter real --categories bottle cable capsule carpet grid --seed 0`
  (`--adapter scripted` runs the committed fixture with no API calls).
- Rule tuning: revises the rules from the judge's errors on train/good plus
  Muse Image synthetic defects (accept only on a strict tune-set F1 gain, at
  most `--rounds` rounds), then scores initial and final rules once on held-out
  test images. Writes `data/tune/<run_id>/tune.json`, shown on the Tune page.
  `cd backend && .venv/bin/python -m app.tune.run --category bottle --adapter real --rounds 3 --seed 0`
  (`--adapter scripted` or `fake` makes no API calls).


## Real grounded eval and tuning (2026-11-02, real adapters, seed 0)

- Grounded run `20261102T083055Z-grounded` (same 150 images as above):
  F1 0.918 overall (bottle 0.850, cable 0.743, capsule 0.976, carpet and grid
  1.000). Hit rate 0.630, box IoU 0.409, pixel IoU 0.296. Carpet locates best
  (hit 0.900); bottle worst (0.400). Pass/fail accuracy matches
  `sam_judge_ref` (0.919), so asking for boxes did not cost verdict quality.
- Before this run, the SAM segment cache was moved to
  `data/cache-stale-sam-20261102/`. Judge entries were kept.
- Tune `20261102T092832Z-cable`: round 1 accepted (tune-set F1 0.952), round 2
  rejected (0.824). Held-out F1 0.743 to 0.842 (recall 0.650 to 0.800,
  precision 0.867 to 0.889).
- Tune `20261102T100501Z-bottle`: round 1 rejected (tune-set F1 0.571), rules
  unchanged, held-out 0.850 both ways.
- Caveat: the held-out set is the eval's own sample (seed 0, 10 good + 20
  defective). Tuning never reads it, but there is one seed and one accepted
  revision.
- Demo re-record: screw scratch_head is still a silent PASS. metal_nut bent
  flipped from FAIL to PASS under part crop. Both are single images.

## Pipeline fixes and wider eval (2026-11-03, real adapters, seed 0)

- Why the demo's two defective parts passed. Metal nut bent/000: the judge
  sampled differently per run (fresh runs gave FAIL at 512 and 1024 px).
  Screw scratch_head/000: SAM answered "deformed screw" with a box around the
  whole screw; the judge ruled it a false alarm and missed the head scratch.
  Removing that candidate, or clearer rules, each flipped it to FAIL.
  Resolution was not the cause.
- Fixes: judge at temperature 0 (part of the cache key; the API rejects
  `seed`); SAM candidates covering at least half the part box are dropped
  when part crop is on; "PLACEHOLDER ... Draft:" wrappers and calibration
  notes removed from every profile's rules.
- Reasoning effort: low and medium both missed the two defects and were not
  reliably faster. The default (high) stays.
- Latency per live inspection: SAM 2-4 s per call, judge 25-42 s. The part
  lookup now runs alongside the defect call. The reference's part lookup is
  a cache hit after the first call.
- Run `20261103T030057Z-grounded` (7 categories): F1 0.869, hit 0.600.
  First five categories: F1 0.913 against 0.918 before (7 of 150 verdicts
  flipped, both directions). metal_nut 0.727 (bent missed 6 of 8, flip 2 of
  4), screw 0.750 (recall 0.600).
- Profile rules instead of the shared string
  (`20261103-grounded-profile-rules-*`): metal_nut 0.824 (bent missed 2,
  flip 4), screw 0.750 (hit 0.35 to 0.55). Precision 1.000 on both.
- Tuning, six more runs: cable seeds 1 and 2, screw, metal_nut with generic
  synthetic defects all rejected their first revision. metal_nut from its
  profile rules with matched synthetic defects (bent lobe, flipped, scratch,
  discolored): accepted round 1, held-out 0.824 to 0.878 (recall 0.70 to
  0.90, precision 1.000 to 0.857).
- Two transient API errors (a 400 from /images/edits, a 503 from
  /responses) each ended a tune run. Calls now retry 429/5xx and network
  errors; a failed synth image is skipped.
- Demo re-record: screw scratch_head replays FAIL. metal_nut bent replays
  PASS, also under the tuned rules (it is not in the tune run's held-out set).
- Bent nut follow-ups. A rule describing a bent tab from above ("4 wide, flat
  tabs; FAIL if any looks narrow, dark, sliver-shaped or missing",
  `20261103-grounded-tab-rule-metal_nut`) cut misses (bent 2 to 1, flip 4 to
  2) but failed 6 of 10 good nuts: F1 0.791 against 0.824. Not adopted.
  SAM 3.1 returns no masks for "tab", "metal tab" or "prong", and its
  "metal nut" mask is box-shaped (or absent on 6 of 13 nuts), so tab
  geometry cannot be measured from it.
- A per-tab rule (compare each of the 4 tabs with the other three on the same
  nut, `20261103-grounded-per-tab-metal_nut`) missed 1 bent and 4 flipped
  nuts and failed 3 of 10 good ones: F1 0.789. Not adopted. The profile rule
  stays (F1 0.824, no false fails); a bend toward a top-down camera is a 3D
  change the photo barely shows, and a side view is the real fix.
- Cable seed 0 rerun with the current pipeline (`20261103T090240Z-cable`):
  revision rejected, held-out 0.686 both ways. The earlier 0.743 to 0.842
  gain (temperature-default judge) did not reproduce. That record and the
  old bottle record moved to `data/tune-stale-20261102/` and out of the demo.
  With the current pipeline, tuning gained in 1 of 6 runs: metal_nut with
  matched synthetic defects.

## SAM box masks, error bars and a reference-diff baseline (2026-11-04)

SAM outlines of judge boxes (live run `20261104T020000Z-grounded`):
- Probe 1 sent 10 crops around judge boxes to SAM 3.1 with the judge's defect noun as a concept prompt ("stain", "scratch", "chip"). All 10 replies were empty, so concept prompts do not find MVTec defects.
- Probe 2 sent the same 10 judge boxes as box prompts on the full image. Every call returned a mask. Mean pixel IoU against ground truth: judge box 0.303, SAM mask 0.503, SAM mask clipped to the judge box 0.482. Two cases got worse when clipped (0.258 to 0.242, 0.241 to 0.211). 1.4 to 4.4 s per call.
- Method: after the judge, each judge box goes to SAM as a box prompt (`<0f>1<|box;x1;y1;x2;y2;w;h|>`, at most 16 per request), the reply is decoded with Meta's `meta-sam-parser`, and the mask is clipped to the box. The detection's bbox stays the judge box, so F1, hit rate and box IoU cannot move; only pixel IoU does. Refinement is best effort: any failure keeps the box mask. Clipping was chosen before the eval and is not tuned on it.
- Cache-only dry run of the 7-category grounded eval (`python -m scripts.dry_run_box_calls`, inner adapters raise on call): F1 0.869 reproduced with 0 judge misses and 0 part/candidate misses, and 114 SAM box calls to make. - Live re-eval (`python -m app.eval.run --mode grounded --adapter real`, 7 categories, seed 0, judge and part/candidate SAM calls replayed from cache): exactly 114 SAM box calls, 0 judge misses. Per-image verdicts, confidence, fail score, hit and box IoU are identical to `20261103T030057Z-grounded`; only pixel IoU moved.
- Pixel IoU, judge box to SAM outline (mean over 20 defective images per category): bottle 0.300 to 0.423, cable 0.213 to 0.338, capsule 0.299 to 0.333, carpet 0.438 to 0.569, grid 0.300 to 0.567, metal nut 0.288 to 0.406, screw 0.155 to 0.185; overall 0.285 to 0.403.
- Losses: no category lost on average, but per image SAM was worse on 27 of 140 defective images (better on 78, unchanged on 35, where SAM returned nothing or its mask matched the box). Carpet split 10 better and 10 worse; the mean still rose because the gains were larger.
- Caveats: the probe that motivated this was 10 images (mean 0.303 to 0.482 clipped), and the live gain (+0.12) is of similar size but is a single seed. Clip-to-box was chosen a priori from CoreSight's leak observation, not tuned on the eval; the 10-image probe even favoured unclipped (0.503), so clipping likely costs some IoU on large defects. The pixel-IoU metric credits only overlap with the true mask, so it says nothing about whether the outline is cleaner to look at. The 5-category numbers in the README (pixel IoU 0.296) predate box outlines.
- Demo bundle: 2 further box calls for the FAIL samples (bottle broken, screw scratched head); the other samples PASS and need none. Probe scripts and raw replies: `.plans/rubric-scores/probe/` (probe_sam, probe_box).

Error bars (`python -m app.eval.stats RUN_DIR [--vs RUN_DIR]`), seed 0, 2,000 bootstrap draws resampled within category:
- Overall F1 (95% CI): SAM + judge 0.872 (0.825 to 0.916); + reference 0.919 (0.882 to 0.953); grounded, 5 categories 0.918 (0.880 to 0.951); grounded, 7 categories 0.869 (0.826 to 0.904).
- Single categories are wide: bottle 0.829 (0.686 to 0.939) and cable 0.778 (0.606 to 0.909) with the reference.
- McNemar (exact, two-sided): judge vs judge + reference 10 vs 2 discordant, p = 0.039; judge + reference vs grounded 4 vs 4, p = 1.0.

Reference-diff baseline (`--mode ref_diff`, run `20261104T000000Z-ref_diff`, 7 categories, seed 0, no model call):
- Per image: grayscale, 5x5 Gaussian blur, resize to the reference, absolute difference with the blurred reference. Score is the 99.5th percentile. The threshold is the largest score over ten `train/good` images other than the reference. The mask is the difference above the 99.9th percentile of those images' pooled differences. No defect labels and no eval images are used to set either value.
- Result: F1 0.358 (0.270 to 0.442), AUROC 0.593 (0.516 to 0.670), precision 0.821, recall 0.229, pixel IoU 0.021. Per category F1: bottle 0.533, cable 0.667, capsule 0.400, carpet 0.000, grid 0.182, metal nut 0.148, screw 0.400.
- Grounded (0.869 on the same images) wins by 97 images to 16 (McNemar p < 0.001).
- `fail_score` is score / (score + threshold) so AUROC pools across categories; `confidence` follows from it.
- Not tuned after seeing results. The baseline is unaligned: parts that move or rotate against the reference raise every score.
