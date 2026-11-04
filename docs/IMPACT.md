# Impact: what it costs and how long it takes

Every number has a source or is marked as ours. Where no usable source was found, no number is given. All links opened 2026-11-04.

## Our measurements

20 MVTec AD test images (bottle, cable, capsule, carpet, grid; 2 good and 2 defective each, none in the eval sample), inspected one at a time with real adapters through an empty cache, so every call was live. Grounded mode with part crop. Raw rows: [`docs/timing-20261104.json`](timing-20261104.json); script: [`backend/scripts/time_inspect.py`](../backend/scripts/time_inspect.py).

| Quantity | Value | Source |
|---|---|---|
| Time per part, median | 25.1 s | Ours (20 images, one machine, one network, sequential) |
| Time per part, p90 | 36.0 s | Ours (same) |
| Calls per part | 2.5 SAM 3.1 (0.45 of them box-prompt outlines) + 1.0 Muse Spark | Ours |
| Cost per part, mean | $0.0171 | Ours: calls and tokens from the run, priced with the rows below |
| Cost per 1,000 parts | about $17 | Ours: arithmetic (0.0171 x 1,000) |
| SOP-to-profile draft | 15.0 s, 1 Muse Spark call | Ours (one run) |

Prices used ([Meta pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits), opened 2026-11-04): SAM 3.1 $2.50 per 1,000 images; Muse Spark 1.3 $1.25 per 1M input tokens and $4.25 per 1M output tokens; Muse Voice Transcribe $0.18 per hour of audio (a spoken rule edit of a few seconds costs well under a cent: ours, arithmetic).

Reading these honestly: 25 seconds a part is a review-station speed, not a conveyor-line speed. Roughly 1.5k output tokens per call is most of the Muse Spark bill. These are 20 parts of five categories, so the percentiles are rough. Accuracy is a separate question: see the [README Results](../README.md#results) (grounded F1 0.869 on 7 categories, with intervals).

## Onboarding a new part

| Step | What it needs | Source |
|---|---|---|
| Draft a profile from a written SOP | one SOP paragraph, 15 s | Ours (the SOP-to-profile line above) |
| Reference image | 1 good photo | By design: the judge compares against it |
| Defect photos | none | By design: the judge takes the rules as text |
| Training | none; no model is trained | By design |

The rules can be tuned afterwards from good photos plus synthetic defects, but that is optional and gained in 1 of 6 runs (see README).

## Manual visual inspection (comparison)

| Claim | Figure | Source | Strength |
|---|---|---|---|
| Inspectors in a nuclear-security manufacturing study correctly rejected defective precision parts | 85% (so 15% of defective parts passed) | [See, Sandia National Laboratories, "Visual inspection reliability for precision manufactured parts" (2015)](https://www.osti.gov/pages/biblio/1236203-visual-inspection-reliability-precision-manufactured-parts) | Primary, peer-reviewed; 82 inspectors, 140 parts, 8 defect types. Specialised parts, not consumer goods |
| Same study: acceptable parts wrongly rejected | 35% | Same | Same |
| Same study, companion slides: no defect was caught by every inspector, and detection was not stable over time | qualitative | [Sandia, signal-detection analysis of a visual inspection task (2014 slides)](https://www.osti.gov/servlets/purl/1142011) | Primary but slides |
| Vendor pages put manual miss rates at roughly 15 to 40% | 15 to 40% | e.g. [oxmaint](https://oxmaint.com/industries/steel-plant/computer-vision-vs-manual-inspection-in-manufacturing) | Weak: marketing pages from AI-inspection vendors, no primary source given. Not used in any claim here |
| How fast a person inspects a part | not stated | none found | No source, no number |

Our system's own error rates are on MVTec AD, not on that study's parts, so the two are not a like-for-like comparison. The point is only that manual inspection is not error-free either.

## Supervised defect models (comparison)

| Claim | Figure | Source | Strength |
|---|---|---|---|
| Fully supervised surface-defect models need annotated defect data, and the annotation requirement raises the cost; a handful of fully annotated images added to weak image-level labels can approach full supervision | qualitative | [Bozic et al., "Mixed supervision for surface-defect detection" (2021)](https://arxiv.org/abs/2104.06064) | Primary (abstract) |
| A public supervised benchmark from the same authors, KolektorSDD2, has over 3,000 images | 3,000+ images | Same authors, cited via [aggregated summary](https://www.emergentmind.com/topics/data-efficient-defect-detection) | Weak: this is a dataset size, not a minimum requirement |
| Labelling cost per image, or the number of defect photos a new part needs | not stated | none found | No source, no number |

What we can say without inventing a figure: a supervised detector needs defect photos with labels collected and annotated per part, and a part with a rare defect may have none yet. This system needs a rules text and one good photo to start, with the accuracy trade-offs in the README.
