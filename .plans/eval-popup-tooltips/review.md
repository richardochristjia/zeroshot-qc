# Correctness review: feat/eval-popup-tooltips vs main

Sources: .plans/eval-popup-tooltips/context-pack.md (ACs, "Do not re-derive"), plan.md, risks.md; code read in Dialog.tsx, InfoTip.tsx, step.ts, pages/Eval.tsx. No browser run (no DOM test infra); proof is code-path reading. Critical findings: none.

| id | verdict | finding |
|---|---|---|
| a | consider | InfoTip.tsx:20-24 calls `e.stopPropagation()` on a document capture keydown. That does not stop the native dialog Esc: the browser's cancel/close-watcher action keys off the keydown's default being prevented (not propagation). Add `e.preventDefault()` there. Effect: Esc with a tip open (hover or focus) closes tip and dialog together. Matches risks.md known risk; the stopPropagation comment is misleading. Low impact. Not run in a browser. |
| b | dismissed (nit) | Dialog.tsx:32 `backdrop:bg-black/50`. index.css defines no scrim token (only stone/night/etc and semantic ones); a neutral scrim is conventional and theme-safe. Only other raw colour is pre-existing Inspect.tsx:22. AC6 is met for "existing tokens" in spirit; optionally add a `--scrim` token. |
| c | dismissed | `GLOSSARY[term]` has no fallback, but every Term/Kpi caller passes a key that exists (F1, Precision, Recall, AUROC, Accuracy, True fail, True pass, False fail, Missed, IoU, confidence; Ablation uses `.Ablation`). A typo would render an empty tip silently; low risk. |
| d | dismissed | Dialog.tsx:15-20 guards on `d.open` both ways, so showModal never throws on re-run or strict mode. |
| e | consider | Arrow keys are a React `onKeyDown` prop (Eval.tsx:367), so no listener to leak, and `stepIndex` clamps (step.ts, matches test table). Caveat: after Next reaches the last item the focused Next button becomes `disabled`; browsers may drop focus to body, after which keydown no longer targets the dialog and arrows stop working until re-click (Chrome behaviour, not run here). Fix if confirmed: move focus to the dialog/Prev button when the focused one disables. |
| f | dismissed (caveat) | Native `showModal()` restores focus to the previously focused element; rows are stable-keyed buttons, so Chrome/Firefox return to the clicked row. Safari does not focus buttons on click, so it returns to body there; not a code bug. |
| g | dismissed | Eval.tsx:207-209 `selectRun` sets selectedFailure -1, so `activeFailure` null, `open` false, effect closes dialog. Also `failures` is derived from `current`, so a stale index is bounds-checked at :217. |

Must-fix: none. Consider: a, e.
