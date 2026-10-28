# Eval failure popup and metric tooltips (Tier M)

## Problem

On the Eval page, clicking a failure example renders its image inline below the whole failure list (`frontend/src/pages/Eval.tsx:310-326`), so with many failures the user scrolls to the bottom to see it and back up to pick the next. The page also uses unexplained jargon (AUROC, F1, Precision, Recall, Accuracy, IoU, Ablation, True fail / True pass / False fail / Missed, confidence). The app has no modal or tooltip component today.

## Solution

- Clicking a failure row opens the existing `FailureDetail` content in a modal built on native `<dialog>` + `showModal()` (top layer, focus trap, Esc, `::backdrop` for free). Close via Esc, backdrop click, or a close button. Focus returns to the clicked row (native `<dialog>` behaviour).
- Popup has Prev / Next buttons plus ← / → keys to step through failures without closing. Prev disabled on first, Next on last.
- Switching runs (`selectRun`) resets `selectedFailure` to -1, which closes the dialog.
- Remove the inline detail block and the "Select a failure above to view its image." placeholder.
- New reusable `InfoTip`: a small ⓘ `<button type="button">` with `aria-label` "About <term>" and `aria-describedby` pointing at the tip text. Opens on hover, focus and click/tap; closes on mouse leave, blur, Esc. Tip renders `position: fixed`, placed from the button's `getBoundingClientRect()`, so the per-category table's `overflow-x-auto` wrapper (`Eval.tsx:63`) cannot clip it. Do not use the native `title` attribute (not touch/keyboard accessible).
- Term definitions live in one `GLOSSARY` record in `Eval.tsx` (plain one/two-sentence text, QC framing: "FAIL = flagged as defective").
- InfoTips on: KPI labels (F1, Precision, Recall, AUROC, Accuracy), per-category table headers (same five minus Accuracy), confusion line terms (True fail, True pass, False fail, Missed), Ablation panel header, and IoU + confidence in the popup.
- Each panel (run detail metrics, Ablation, Failure examples) gets a one-line muted description under its header. The Ablation description explains the three modes (SAM only / + judge / + reference).
- Styling uses existing tokens only (`bg-surface`, `border-line`, `text-ink-2`, etc.) so light/dark both work. Any open animation is skipped under `prefers-reduced-motion` (existing global rule in `frontend/src/index.css:101`).

## Files

- `frontend/src/components/Icon.tsx` — add `info` to `IconName` and an `i-info` symbol (circle + "i"), same stroke style.
- `frontend/src/components/InfoTip.tsx` — new: ⓘ button + fixed-position tip as above.
- `frontend/src/components/Dialog.tsx` — new: thin wrapper; `open` prop drives `showModal()`/`close()` in an effect; `onClose` wired to the dialog `close` event; backdrop click (click target === dialog element) closes; header with title + a text "Close" button (existing `x` icon is an octagon error glyph, not a close mark).
- `frontend/src/step.ts` — new: `stepIndex(index, delta, length)` clamps to `[0, length-1]`; returns -1 when `length === 0`.
- `frontend/src/step.test.ts` — new: vitest cases below.
- `frontend/src/pages/Eval.tsx` — `GLOSSARY`, InfoTips, panel descriptions, dialog wiring, Prev/Next + arrow keys (keydown listener on the dialog, only while open), drop inline detail + placeholder.

## Acceptance criteria

1. `npm run build`, `npm run lint`, `npm test` pass in `frontend/` (check: run them).
2. Clicking a failure row opens the dialog without scrolling the page; Esc, backdrop click and the close button each close it; focus returns to the row (check: code review of native `<dialog>` usage; manual below).
3. Prev / Next and ← / → move through failures; Prev disabled at first, Next disabled at last (check: `step.test.ts` + code review).
4. Every term listed in Solution has an InfoTip that opens on hover, focus and tap; tips on table headers are not clipped by the table scroll box (check: fixed positioning in code review; manual below).
5. Switching runs while the dialog is open closes it (check: `selectRun` resets `selectedFailure`).
6. Dialog and tips use existing colour tokens only, and no animation runs under reduced motion (check: grep for raw colours; review).
7. manual: with real runs under `data/runs/`, start the app, open Eval, click a failure low in the list, step with ←/→, close with Esc, then hover/tap the AUROC header and the ⓘ in the KPI row in both themes. Expected: image visible without scrolling, tips fully visible, focus returns to the row.

## Risks

- `showModal()` called on an already-open dialog throws `InvalidStateError` — guard with `dialog.open` checks in the effect.
- React strict-mode double effects could open/close twice — the guard above covers it.
- Arrow keys while a tip or button inside the dialog has focus still step — acceptable; no text inputs in the dialog.
- Fixed tip goes stale if the page scrolls while open — close the tip on scroll (`window` scroll listener while open, capture phase).
- Tip near viewport right/bottom edge can overflow — clamp left to `[8, innerWidth - tipWidth - 8]`, flip above when no room below.
- No jsdom/testing-library in the repo, so DOM behaviour is not unit tested; covered by review and the manual check.

## Test plan

`frontend/src/step.test.ts` (run with `cd frontend && npm test`):

| Case | Input | Expected |
|---|---|---|
| step forward | `stepIndex(2, 1, 5)` | 3 |
| step back | `stepIndex(2, -1, 5)` | 1 |
| clamp end | `stepIndex(4, 1, 5)` | 4 |
| clamp start | `stepIndex(0, -1, 5)` | 0 |
| empty | `stepIndex(0, 1, 0)` | -1 |

Not unit tested (no DOM test infra): missing image row (`imageUrl === null`) keeps showing the existing "No image for this row" empty state inside the dialog; zero failures shows no dialog and no Prev/Next.

## Record Updates

- (frontend) The Eval page currently opens a failure example's image in a modal dialog with previous and next navigation.
