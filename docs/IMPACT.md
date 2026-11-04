# Impact: who this is for, and where it does not fit

Every external number links to its source (all opened 2026-11-04). "Our measurement" is this repo's own result and is not independent. "Our arithmetic" is derived here. Where no usable source was found, no number is given. Background: the research report in `.plans/rubric-scores/reports/`.

## The problem

Small and high-mix manufacturers rarely have a vision engineer, and every new product would need a pile of defect photos before an automated system could inspect it, so inspection stays manual. In a vendor-sponsored survey, 40% of manufacturers called visual inspection completely or mostly manual and 62% named scarce defect images as the top barrier to AI vision. The manual baseline is poor: in a Sandia study of 82 qualified inspectors, they caught 85% of defects but rejected 35% of good parts, at 56 s per part. The cost floor of escaped defects is US warranty claims of 1.30% of sales.

## Numbers

| Number | Source | Strength |
|---|---|---|
| 1.8% of US firms used machine vision in 2017 (5.6% employment-weighted) | [NBER w28290](https://www.nber.org/system/files/working_papers/w28290/w28290.pdf) | Primary |
| 40% of 110 manufacturers: inspection completely or mostly manual; 62%: scarce defect data is the top barrier | [Machine Design](https://www.machinedesign.com/automation-iiot/article/21148375/survey-four-findings-show-manufacturings-opinion-on-ai-vision-inspection) | Weak: vendor co-sponsored, small sample |
| Inspectors: 85% hits, 35% false rejects, 56 s per part (82 inspectors, 140 parts) | [See 2015, Sandia](https://www.osti.gov/servlets/purl/1236203) | Primary; specialised parts |
| Typical human miss rate 20-30% | [See 2012, Sandia](https://www.osti.gov/servlets/purl/1055636) | Primary review |
| Search errors 7% at 50% prevalence, 30% at 1% | [Wolfe et al. 2005](https://pmc.ncbi.nlm.nih.gov/articles/PMC4224304) | Primary (lab) |
| Warranty claims 1.30% of sales in 2025, over $30B paid | [Warranty Week](https://www.warrantyweek.com/archive/ww20260416.html) | Industry; skewed to large listed firms |
| Scrap and rework about 1.4% of sales at the average US metal fabricator | [Reliamag citing FMA](https://reliamag.com/articles/cost-of-poor-quality-scrap-rework-returns/) | Weak: secondhand |
| "Cost of poor quality is 15-20% of sales" | [Reliamag](https://reliamag.com/articles/cost-of-poor-quality-scrap-rework-returns/) | Weak: a rule of thumb, not used in any claim here |
| Integrator rate $150-250 per hour; complex re-programming for a new variant 4-6 weeks | [SmartDev](https://smartdev.com/computer-vision-cost-manufacturing-complete-cv-system-pricing-breakdown/), [Datature](https://datature.io/blog/why-your-machine-vision-system-breaks-every-time-the-line-changes-and-how-to-fix-it) | Weak: vendor and blog |
| Supervised minimum 10 anomalous + 20 normal images (AWS Lookout for Vision, end of support 31 Oct 2025) | [AWS docs](https://docs.aws.amazon.com/lookout-for-vision/latest/developer-guide/model-create-dataset.html) | Vendor docs |
| PatchCore 99.6% image AUROC on MVTec AD (15 categories, good images only) | [arXiv 2106.08265](https://arxiv.org/abs/2106.08265) | Academic |
| WinCLIP 91.8% zero-shot, 93.1% one-shot AUROC on MVTec AD | [arXiv 2303.14814](https://arxiv.org/abs/2303.14814) | Academic |
| Pharma line at 300 bottles/min leaves 0.2 s per bottle | [Powder & Bulk Solids](https://www.powderbulksolids.com/packaging-systems/pharma-tech-introduces-high-speed-bottling-line) | Trade press, 2016 |
| Lot of 501-1,200 parts: sample 80 (General Level II) | [MetricGate](https://metricgate.com/docs/acceptance-sampling-mil-std-105/) | Weak: secondary |
| Lot of 1,201-3,200 parts: sample 125 | [Scribd table](https://www.scribd.com/document/399986729/Sampling-Plan) | Weak: uploaded copy |
| Median inspector wage $23.35 per hour (597,370 US inspectors, testers, sorters) | [BLS OEWS](https://api.bls.gov/publicAPI/v2/timeseries/data/OEUN000000000000051906101) | Primary |
| Time per part: median 25.1 s, p90 36.0 s; cost $0.0171 per part (about $17 per 1,000); profile draft from an SOP 15.0 s | [`docs/timing-20261104.json`](timing-20261104.json) | Our measurement: 20 images, one machine, sequential |
| F1 0.869 (0.826-0.904), AUROC 0.944 (0.920-0.966), 210 images, 7 of 15 categories | [README Results](../README.md#results) | Our measurement |
| 144 parts per hour per stream (100 at p90); about 125x too slow for 300 per min | 3,600 / 25.1; 25 s / 0.2 s | Our arithmetic |
| 80-sample lot: about 33 min, $1.36; 125-sample lot: about 52 min, $2.13 | 80 or 125 x 25 s and x $0.0171 | Our arithmetic |

Our run: 20 MVTec AD test images (bottle, cable, capsule, carpet, grid; none in the eval sample), live calls through an empty cache, grounded mode with part crop. Script: [`backend/scripts/time_inspect.py`](../backend/scripts/time_inspect.py). Calls per part: 2.5 SAM 3.1 plus 1.0 Muse Spark. Prices ([Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits), opened 2026-11-04): SAM 3.1 $2.50 per 1,000 images; Muse Spark 1.3 $1.25 per 1M input and $4.25 per 1M output tokens. Percentiles over 20 parts are rough.

## Onboarding a new part

A written SOP paragraph (a draft profile in 15 s, our measurement) and one good photo. No defect photos and no training, by design. Optional rule tuning gained in 1 of 6 runs (see README).

## Where it fits

- **Acceptance sampling.** Judged one at a time, an 80-sample lot takes about 33 min and costs $1.36, and a 125-sample lot about 52 min and $2.13 (our arithmetic).
- **Incoming and audit inspection.** Many part numbers, small samples, no conveyor, and a written reason to send back to the supplier.
- **High-mix shops.** Setup is one paragraph and one photo per product, where rivals charge engineer weeks or defect photos per product.
- **Human second opinion.** A tireless extra check where a person confirms every reject. Humans trade misses for false rejects (85% / 35%), and the tool is not a replacement for that judgment.

It replaces the judging, not the handling: someone still presents and photographs each part.

## Where it does not fit

- **Fast lines.** At 25 s per part it is about 125x too slow for 300 bottles per minute (our arithmetic). Parallel calls raise throughput, not latency.
- **Inline gating.** The verdict arrives long after the reject point has passed. At most, an asynchronous check.
- **Sole check on safety-critical parts.** An F1 of 0.869 on a public benchmark is not the measured reliability that work demands.
- **Accuracy against trained models.** PatchCore scores 99.6% and WinCLIP 91.8% zero-shot AUROC on all 15 MVTec categories; we score 0.944 on 7 of 15. The test sets differ, so this is a rough comparison. We sit near WinCLIP and below PatchCore. On a stable, high-volume product with hundreds of good images, a trained good-only model is the better choice. Our edge is setup cost, not accuracy.
- **Real defect rates.** Our eval sample is two-thirds defective (140 of 210 images). Production defect rates are usually 1-10% or lower, where false alarms on good parts pull precision down, so real-plant F1 will be lower than 0.869. It has not been measured at realistic prevalence.
- **Repeatability.** Not measured. The judge runs at temperature 0, but a cloud model can change version.

Not claimed: no source measures how many small firms inspect by hand, no SME-specific warranty cost was found, and no number is given for how many plants forbid images leaving the site.
