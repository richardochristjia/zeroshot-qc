# Correctness review: feat/eval-visual-refresh vs feat/eval-popup-tooltips

Basis: context-pack.md (acceptance criteria 1-7), plan.md, risks.md, diff of FailureGrid.tsx and Eval.tsx.
Gates run in frontend/: build, lint, test (24 tests) all pass. Raw-colour grep on the diff: no hex/rgb/black/white added.
Criterion 8 (browser, 390px, light/dark) not run.

No critical findings.

## Findings

1. consider (not critical): grid and dialog sort differently. Eval.tsx sorts failures with `localeCompare`; FailureGrid groups with default `.sort()`. Click N still opens card N (the index is into the filtered list), so the main criterion holds. Prev/Next order across groups can diverge from the visual order when category names mix case or punctuation. Proof: `['metal_nut','metallic','Zed','alpha']` sorts to Zed,alpha,metal_nut,metallic by default and alpha,metal_nut,metallic,Zed by localeCompare. Real MVTec names are lowercase and sort the same, so no live impact. Fix: use the same comparator in both places.
2. consider (not critical): chip counts ignore the other filter. FailureGrid.tsx:77,101 count from all rows. With Missed on, a category chip still shows the all-kind count, and the grid can be empty ("No failures match"). Accepted by the plan ("with counts") but misleading when combined.
3. consider (not critical): the ablation list drops the current run when another run with the same mode and the same groupKey exists (Eval.tsx dedupes by mode, first wins). groupKey ignores nGood and nDefective. Then the selected run has no highlighted bar and no Best badge, and `bestOtherDelta` compares against the same-mode sibling. Proof: node run with the real helper gave delta -0.4, currentInAblation false. Not hit by the current data/runs (one run per mode per group).
4. dismissed: selection reset. Run change (`selectRun`), kind chip and category chip all reset `selectedFailure` and the filters. The dialog is modal, so filters cannot change while it is open.
5. dismissed: pickDefaultRun wiring. It is called once on load over all runs; the tests cover ties, null and empty. With the live runs it picks sam_judge_ref at 0.919 (the 1.0 bottle-only runs are a different group but win globally; the plan says max F1 overall, so this follows the plan).
6. dismissed: `bestOtherDelta` excludes the current run by runId and uses `ablation`, which is built from the same groupKey. Correct apart from finding 3.
7. dismissed: shading. Max 38% (<=40%) with `text-ink` on the cells; level 0 has no background. Fine.
8. dismissed: images. `row.imageUrl === null` and `onError` both fall back to the icon, and `loading="lazy"` is set. Card keys `${image}-${index}` are unique. The key changes when a filter shifts the index, which only remounts the thumb. No stale-state bug found.
