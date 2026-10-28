## Components
- [x] Add `info` icon symbol to `frontend/src/components/Icon.tsx`
- [x] Create `frontend/src/components/InfoTip.tsx` (hover/focus/tap, fixed-position, viewport clamp, closes on Esc/blur/scroll)
- [x] Create `frontend/src/components/Dialog.tsx` (native `<dialog>` + `showModal()`, guarded open/close, backdrop click, close button)

## Eval tooltips and descriptions
- [x] Add `GLOSSARY` to `frontend/src/pages/Eval.tsx` and InfoTips on KPIs, table headers, confusion line, Ablation header
- [x] Add one-line descriptions under the metrics, Ablation and Failure examples panel headers

## Eval failure popup
- [x] Create `frontend/src/step.ts` with `stepIndex` and `frontend/src/step.test.ts`
- [x] Render `FailureDetail` inside `Dialog`, with InfoTips for IoU and confidence
- [x] Add Prev/Next buttons and ←/→ keys; remove inline detail and placeholder

## Verification
- [x] AC1: `npm run build`, `npm run lint`, `npm test` pass in `frontend/`
- [x] AC2: dialog opens without scrolling; Esc, backdrop, close button close it; focus returns to row (code-reviewed only; browser unverified)
- [x] AC3: Prev/Next and ←/→ step through failures, disabled at ends
- [x] AC4: every listed term has an InfoTip opening on hover, focus, tap; table-header tips not clipped (code-reviewed only; browser unverified)
- [x] AC5: switching runs closes the dialog
- [x] AC6: only existing colour tokens used; no animation under reduced motion
- [x] Record Updates: (1) review the complete implementation; (2a) if it matches the planned Record Updates in plan.md, write that exact entry into `.agents/RECORD.md`; (2b) if it diverged, do not write a wrong entry — surface the divergence in the final summary

## Manual checks
- [ ] manual: with real runs under `data/runs/`, open Eval, click a failure low in the list, step with ←/→, close with Esc, hover/tap AUROC header and KPI ⓘ in both themes; image visible without scrolling, tips fully visible, focus returns to row
