## Helpers
- [x] Create `frontend/src/eval-view.ts` (pickDefaultRun, failureKind, filterFailures, bestOtherDelta, shadeLevel, runTag) and `frontend/src/eval-view.test.ts`

## Metrics visuals
- [x] Create `frontend/src/components/ConfusionMatrix.tsx` and replace the confusion sentence in Eval.tsx
- [x] Per-category table: remove duplicate F1 bar column, add token-based cell shading via `shadeLevel`

## Page structure
- [x] Select default run with `pickDefaultRun`
- [x] Add KPI deltas (▲/▼ + sign) from `bestOtherDelta`
- [x] Move Ablation panel to top of detail column with "Best" badge
- [x] Run list: `runTag` + thin F1 bar per row

## Failure grid
- [x] Create `frontend/src/components/FailureGrid.tsx` (kind + category chips with counts, grouped lazy image cards, kind badges with icon + text, shortcut comment on image weight)
- [x] Wire grid into Eval.tsx; dialog Prev/Next over filtered list; reset selection on filter/run change; remove text list

## Verification
- [x] AC1: `npm run build`, `npm run lint`, `npm test` pass in `frontend/`
- [x] AC2: highest-F1 run selected on load
- [x] AC3: lazy cards grouped by category; chips filter kind + category with counts; Prev/Next follow filtered list
- [x] AC4: every coloured state carries icon or text
- [x] AC5: 2×2 confusion grid; exactly one F1 column
- [x] AC6: KPI deltas only when non-null
- [x] AC7: no new raw colour literals in `frontend/src` diff
- [ ] Record Updates: (1) review the complete implementation; (2a) if it matches plan.md's Record Updates, append those exact entries to `.agents/RECORD.md`; (2b) if it diverged, do not write a wrong entry — surface the divergence in the final summary

## Manual checks
- [ ] manual: with real runs, open `/eval` in light, dark and 390px width; best run selected, grid visible, chips filter, card opens dialog with ←/→ over filtered set, weak categories shaded lighter
