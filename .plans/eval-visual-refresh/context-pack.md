# Context pack

BASE: feat/eval-popup-tooltips (stacked on PR #10)
CHANGED: 5 source files in `frontend/src` (+409/-65 incl. tests), plus 4 plan docs

## What this change does
Redesigns the `/eval` page: default-selects the best-F1 run, shows failures as a lazy-image card grid with kind/category filter chips, a 2x2 confusion matrix, one F1 column with shaded weak categories, and KPI deltas versus other runs. Pure helpers live in `eval-view.ts`.

## Files
- `frontend/src/eval-view.ts` (new) — pure helpers: `pickDefaultRun:8`, `failureKind:21`, `filterFailures:28`, `bestOtherDelta:36`, `shadeLevel:45`, `runTag:50`
- `frontend/src/eval-view.test.ts` (new) — vitest cases for those helpers
- `frontend/src/components/FailureGrid.tsx` (new, 118 lines) — grouped failure cards, chips, lazy `<img>`
- `frontend/src/components/ConfusionMatrix.tsx` (new, 33 lines) — 2x2 count grid
- `frontend/src/pages/Eval.tsx` (+167 changed) — page wiring: run selection, filters, dialog index, KPIs, table
- `.plans/eval-visual-refresh/{plan,risks,tasks,tier}.md` — plan docs, not code

## API contracts
- No new endpoints. Page uses `listEvalRuns` (`frontend/src/api.ts:684`) and `getEvalRun` (`:692`), unchanged.
- Row shape `EvalResultRow` at `frontend/src/api.ts:81` (`label`, `verdict`, `category`, `imageUrl`); `CategoryMetrics:94`, `EvalMetrics:108`, `EvalRunSummary:116`, `EvalRunDetail:129`.

## Test entry points
- `frontend/src/eval-view.test.ts` — `cd frontend && npx vitest run src/eval-view.test.ts`
- All gates: `cd frontend && npm run build && npm run lint && npm test`
- No DOM test infra: the components and `Eval.tsx` have no tests.

## Acceptance criteria
1. `npm run build`, `npm run lint`, `npm test` pass in `frontend/` (run them).
2. Page loads with the highest-F1 run selected (`pickDefaultRun` test + Eval wiring review).
3. Failures render as lazy image cards grouped by category; chips filter by kind and category with counts; dialog Prev/Next follow the filtered list (`filterFailures` test + code review).
4. Every coloured state also carries an icon or text: kind badges, KPI arrows, matrix cell names, "Best" badge (code review).
5. Confusion counts render as a 2x2 grid; the per-category table has exactly one F1 column (code review).
6. KPI deltas render only when `bestOtherDelta` is non-null (`bestOtherDelta` test + review).
7. No new raw colours: `git diff` of `frontend/src` adds no hex/`rgb(`/`black`/`white` literals; only tokens and `color-mix` of tokens (grep).
8. manual: with real runs in `data/runs/`, run backend + `cd frontend && npm run dev`, open `/eval` in light, dark and at 390px width (needs real runs and a browser; outside automated verification).

## Do not re-derive
- Failure kind: `good`+`FAIL` is `false-fail`; `defective`+`PASS` is `missed`; else `null` (`eval-view.ts:21`).
- The dialog index now refers to the filtered list; plan risk says selection must reset when filters or run change (check in `Eval.tsx`).
- Known and accepted: full-size 900x900 PNGs are used as thumbnails (~780 KB each), `loading="lazy"` is the only mitigation; plan wants a `// shortcut:` comment in `FailureGrid.tsx`.
- Shading max mix is meant to be <=40% with `text-ink` text (dark-theme contrast).
- Untracked files in the working tree (`.plans/*`, `frontend/README.md`, `.oxlintrc.json`, etc.) are not part of this branch.

## Diff
Complete for `eval-view.ts`, its test and `ConfusionMatrix.tsx`. Omitted for budget (open the file): `frontend/src/components/FailureGrid.tsx` (all new) and `frontend/src/pages/Eval.tsx`. Get them with `git diff feat/eval-popup-tooltips...HEAD -- <path>`.

```diff
diff --git a/frontend/src/components/ConfusionMatrix.tsx b/frontend/src/components/ConfusionMatrix.tsx
new file mode 100644
index 0000000..f12a436
--- /dev/null
+++ b/frontend/src/components/ConfusionMatrix.tsx
@@ -0,0 +1,33 @@
+import type { JSX, ReactNode } from 'react'
+
+interface Counts {
+  tp: number
+  tn: number
+  fp: number
+  fn: number
+}
+
+/** 2x2 grid: rows are the actual label, columns the verdict. `term` renders a cell name (with its InfoTip). */
+export function ConfusionMatrix({ counts, term }: { counts: Counts; term: (name: string) => ReactNode }): JSX.Element {
+  const head = 'text-center text-xs font-medium text-ink-3'
+  const side = 'flex items-center text-xs font-medium text-ink-3'
+  const cell = (name: string, n: number, good: boolean): JSX.Element => (
+    <div className={`rounded-sm px-3 py-2.5 ${good ? 'bg-pass-tint' : 'bg-fail-tint'}`}>
+      <div className="num text-[22px] font-medium leading-tight">{n}</div>
+      <div className={`text-[13px] ${good ? 'text-pass' : 'text-fail'}`}>{term(name)}</div>
+    </div>
+  )
+  return (
+    <div className="grid max-w-md grid-cols-[4.5rem_1fr_1fr] gap-1.5" role="group" aria-label="Confusion matrix">
+      <span />
+      <span className={head}>Verdict FAIL</span>
+      <span className={head}>Verdict PASS</span>
+      <span className={side}>Defective</span>
+      {cell('True fail', counts.tp, true)}
+      {cell('Missed', counts.fn, false)}
+      <span className={side}>Good</span>
+      {cell('False fail', counts.fp, false)}
+      {cell('True pass', counts.tn, true)}
+    </div>
+  )
+}
diff --git a/frontend/src/eval-view.test.ts b/frontend/src/eval-view.test.ts
new file mode 100644
index 0000000..1539410
--- /dev/null
+++ b/frontend/src/eval-view.test.ts
@@ -0,0 +1,38 @@
+import { describe, expect, it } from 'vitest'
+import type { EvalMetrics, EvalResultRow } from './api.ts'
+import { bestOtherDelta, failureKind, filterFailures, pickDefaultRun, runTag, shadeLevel } from './eval-view.ts'
+
+const run = (runId: string, f1: number | null) => ({
+  runId,
+  metrics: f1 === null ? null : ({ overall: { f1 } } as unknown as EvalMetrics),
+})
+const row = (category: string, label: 'good' | 'defective', verdict: 'PASS' | 'FAIL') =>
+  ({ category, label, verdict }) as EvalResultRow
+
+describe('eval-view', () => {
+  it('picks default run', () => {
+    expect(pickDefaultRun([run('a', 0), run('b', 0.919), run('c', 0.872)])).toBe('b')
+    expect(pickDefaultRun([run('a', null), run('b', null)])).toBe('a')
+    expect(pickDefaultRun([])).toBe('')
+  })
+  it('classifies and filters failures', () => {
+    expect(failureKind(row('x', 'good', 'FAIL'))).toBe('false-fail')
+    expect(failureKind(row('x', 'defective', 'PASS'))).toBe('missed')
+    expect(failureKind(row('x', 'good', 'PASS'))).toBeNull()
+    const rows = [row('bottle', 'defective', 'PASS'), row('cable', 'defective', 'PASS'), row('bottle', 'good', 'FAIL')]
+    expect(filterFailures(rows, 'missed', 'bottle')).toEqual([rows[0]])
+    expect(filterFailures(rows, '', '')).toHaveLength(3)
+  })
+  it('computes delta', () => {
+    const cur = run('c', 0.872)
+    expect(bestOtherDelta(cur, [run('a', 0.919), run('b', 0), cur])).toBeCloseTo(-0.047)
+    expect(bestOtherDelta(cur, [cur])).toBeNull()
+  })
+  it('tags runs', () => {
+    expect(runTag('m5verify-sam_judge', 'sam_judge')).toBe('m5verify')
+    expect(runTag('smoke', 'sam_only')).toBe('smoke')
+  })
+  it('shades', () => {
+    expect([0, 0.5, 1, 1.4, null].map(shadeLevel)).toEqual([0, 2, 4, 4, null])
+  })
+})
diff --git a/frontend/src/eval-view.ts b/frontend/src/eval-view.ts
new file mode 100644
index 0000000..f1a7fae
--- /dev/null
+++ b/frontend/src/eval-view.ts
@@ -0,0 +1,53 @@
+import type { EvalMetrics, EvalResultRow } from './api.ts'
+
+export type FailureKind = 'false-fail' | 'missed'
+type RunLike = { runId: string; metrics: EvalMetrics | null }
+type MetricKey = 'f1' | 'precision' | 'recall' | 'auroc' | 'accuracy'
+
+/** Run with the highest overall F1; ties and null metrics keep list order. */
+export function pickDefaultRun(runs: RunLike[]): string {
+  let best = -1
+  let id = ''
+  for (const run of runs) {
+    const f1 = run.metrics?.overall.f1 ?? -1
+    if (id === '' || f1 > best) {
+      best = f1
+      id = run.runId
+    }
+  }
+  return id
+}
+
+export function failureKind(row: Pick<EvalResultRow, 'label' | 'verdict'>): FailureKind | null {
+  if (row.label === 'good' && row.verdict === 'FAIL') return 'false-fail'
+  if (row.label === 'defective' && row.verdict === 'PASS') return 'missed'
+  return null
+}
+
+/** Rows matching kind and category; '' means any. */
+export function filterFailures(rows: EvalResultRow[], kind: FailureKind | '', category: string): EvalResultRow[] {
+  return rows.filter((r) => {
+    const k = failureKind(r)
+    return k !== null && (kind === '' || k === kind) && (category === '' || r.category === category)
+  })
+}
+
+/** current minus the best other run's value; null when no other run has metrics. */
+export function bestOtherDelta(current: RunLike, group: RunLike[], key: MetricKey = 'f1'): number | null {
+  const mine = current.metrics?.overall[key]
+  if (mine == null) return null
+  const others = group.filter((r) => r.runId !== current.runId).map((r) => r.metrics?.overall[key])
+  const valid = others.filter((v): v is number => v != null)
+  return valid.length === 0 ? null : mine - Math.max(...valid)
+}
+
+/** 0-4 bucket of a 0-1 value. */
+export function shadeLevel(value: number | null): number | null {
+  if (value === null) return null
+  return Math.min(4, Math.max(0, Math.round(value * 4)))
+}
+
+export function runTag(runId: string, mode: string): string {
+  const suffix = `-${mode}`
+  return runId.endsWith(suffix) && runId.length > suffix.length ? runId.slice(0, -suffix.length) : runId
+}
```
