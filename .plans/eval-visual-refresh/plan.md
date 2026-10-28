# Eval visual refresh (Tier M)

Branch `feat/eval-visual-refresh` is stacked on `feat/eval-popup-tooltips` (PR #10, open). Its PR targets `feat/eval-popup-tooltips` so the diff shows only this work.

## Problem

The Eval page (`frontend/src/pages/Eval.tsx`) is plain numbers in one blue (`--data`) plus greys; the existing semantic tokens `--pass`, `--fail`, `--detect`, `--pass-tint`, `--fail-tint` (`frontend/src/index.css`) go unused. The failure list is about 70% of page height: 100 identical text rows, no images, no false-fail vs missed distinction, category repeated (`bottle · bottle/test/...`). The page opens on the alphabetically-first run (backend sorts dir names, `backend/app/routers/eval.py:34`), often the worst one (all 0.000). KPIs have no good/bad context. Confusion counts are a sentence. The per-category table has a duplicate F1 column (a bar column and a number column both headed "F1") and uniform cells. The ablation panel sits mid-page in grey. The run list repeats three mode names with full run IDs.

## Solution

- **Pure helpers** in new `frontend/src/eval-view.ts` (unit-tested), imported by Eval.tsx:
  - `pickDefaultRun(runs)` → runId with max `metrics.overall.f1`; ties and null metrics: first in list order; empty list → `''`.
  - `failureKind(row)` → `'false-fail'` (label good, verdict FAIL) | `'missed'` (label defective, verdict PASS) | `null`.
  - `filterFailures(rows, kind, category)` → rows matching (`''` = any).
  - `bestOtherDelta(current, group)` → `current.f1 - max(f1 of other runs in the same ablation group)`; `null` when no other run with metrics.
  - `shadeLevel(value)` → integer 0–4 bucket of a 0–1 value (clamped), `null` for null.
  - `runTag(runId, mode)` → runId with trailing `-${mode}` stripped; unchanged if no such suffix.
- **Default run**: on load select `pickDefaultRun(loaded)` instead of `loaded[0]`. Backend order unchanged.
- **Failure thumbnail grid** replaces the text list: chips row (reuse the chip look/`aria-pressed` pattern from `frontend/src/pages/Synthetic.tsx:120-161`): All · False fail · Missed (with counts), then one chip per category (with counts); kind and category filters combine. Cards in a responsive grid (2 cols phone, 4–6 desktop), grouped under category subheadings. Card: square `<img loading="lazy" decoding="async">` with `object-cover`, broken/null image falls back to an icon placeholder; a badge with icon + text ("False fail" in `text-fail` on `bg-fail-tint` with `x` icon, "Missed" in `text-detect` with `alert` icon); file name with the category prefix removed (`row.image` minus leading `${category}/`), confidence %. Card is a `<button>` opening the existing dialog; Prev/Next step through the **filtered** list. Changing filters or run closes the dialog.
- **KPI deltas**: under F1 (and the other KPIs, using the same per-metric logic) show `▲ +0.047` in `text-pass` or `▼ −0.047` in `text-fail` (arrow glyph + sign, never colour alone), vs the best other mode in the same ablation group (`groupKey`). Hidden when `null`. Zero delta shows `= 0.000` in `text-ink-3`.
- **Confusion matrix**: new `frontend/src/components/ConfusionMatrix.tsx`, 2×2 grid, rows = actual (Defective, Good), cols = predicted (FAIL, PASS). Correct cells (TP, TN) `bg-pass-tint`, wrong cells (FP, FN) `bg-fail-tint`; each cell shows count (large) + name (True fail / Missed / False fail / True pass) with the existing InfoTips. Replaces the confusion sentence.
- **Per-category table**: drop the bar column (keeps one F1 column). Metric cells get a background `color-mix(in srgb, var(--data) X%, transparent)` with X from `shadeLevel` (e.g. 0, 8, 16, 26, 38%); the number stays printed. Text stays `text-ink` for contrast.
- **Ablation** panel moves to the top of the detail column (before the metrics panel); the top-F1 mode gets a "Best" text badge; bars use `bg-data` for the selected run and `bg-line-strong` for others (as today).
- **Run list**: each row shows mode name, `runTag` (mono, small) instead of full runId, and a thin F1 bar (`bg-data`) under the name; F1 number stays.
- Only existing tokens or `color-mix` of them; no raw hex/rgb. Respect existing reduced-motion rule; add no new animation.

## Files

- `frontend/src/eval-view.ts` — new helpers above.
- `frontend/src/eval-view.test.ts` — vitest for helpers.
- `frontend/src/components/ConfusionMatrix.tsx` — new 2×2 matrix.
- `frontend/src/components/FailureGrid.tsx` — new chips + grouped card grid, emits selected index into the filtered list.
- `frontend/src/pages/Eval.tsx` — default run, ablation move + Best, KPI deltas, matrix, table shading + duplicate column removal, run list tag + bar, grid wiring with dialog over filtered list.

## Acceptance criteria

1. `npm run build`, `npm run lint`, `npm test` pass in `frontend/` (run them).
2. Page loads with the highest-F1 run selected (`pickDefaultRun` test + Eval wiring review).
3. Failures render as lazy image cards grouped by category; chips filter by kind and category with counts; dialog Prev/Next follow the filtered list (`filterFailures` test + code review).
4. Every coloured state also carries an icon or text: kind badges, KPI arrows, matrix cell names, "Best" badge (code review).
5. Confusion counts render as a 2×2 grid; the per-category table has exactly one F1 column (code review).
6. KPI deltas render only when `bestOtherDelta` is non-null (`bestOtherDelta` test + review).
7. No new raw colours: `git diff` of `frontend/src` adds no hex/`rgb(`/`black`/`white` literals; only tokens and `color-mix` of tokens (grep).
8. manual: with real runs in `data/runs/`, run backend + `cd frontend && npm run dev`, open `/eval` in light, dark and at 390px width. Expect: best run selected on load; grid visible without long text scroll; chips filter; clicking a card opens the dialog and ←/→ follow the filtered set; weak categories visibly shaded lighter in the table.

## Risks

- Image weight: dataset PNGs are 900×900, ~780 KB average (probe on `data/mvtec`); 100 cards ≈ 78 MB if all load. `loading="lazy"` + filters limit it; add `// shortcut: full-size images as thumbnails, add a backend thumbnail endpoint if served over a slow network` in FailureGrid.
- Stacked branch: if PR #10 changes before merge, this branch needs a rebase.
- No DOM test infra (no jsdom/testing-library): components are checked by review and the manual check only.
- Shading alone could fail contrast in dark theme: keep max mix ≤ 40% and text `text-ink`.
- Dialog index now refers to the filtered list: reset selection when filters or run change to avoid pointing at a wrong row.

## Test plan

`frontend/src/eval-view.test.ts`, run with `cd frontend && npm test`:

| Case | Input | Expected |
|---|---|---|
| default run | F1 0, 0.919, 0.872 | 0.919 run |
| default, no metrics | all `metrics: null` | first runId |
| default, empty | `[]` | `''` |
| failure kind | good+FAIL / defective+PASS / good+PASS | `false-fail` / `missed` / `null` |
| filter | kind `missed`, category `bottle` | only bottle misses |
| delta | 0.872 vs others 0.919, 0 | ≈ −0.047 |
| delta, alone | group of one | `null` |
| run tag | `m5verify-sam_judge`, `sam_judge` | `m5verify` |
| run tag, no suffix | `smoke`, `sam_only` | `smoke` |
| shade | 0, 0.5, 1, 1.4, null | 0, 2, 4, 4, null |

## Record Updates

- (frontend) The Eval page currently selects the run with the highest overall F1 when it loads.
- (frontend) The Eval page currently shows failure examples as a thumbnail grid filterable by failure kind and category.
