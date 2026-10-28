# Context pack

BASE: main (branch feat/eval-popup-tooltips)
CHANGED: 6 frontend source files (+~265/-20, incl. test) plus plan docs in `.plans/eval-popup-tooltips/` (omitted from diff)

## What this change does
Eval page failure examples open in a native `<dialog>` modal (Prev/Next + arrow keys) instead of an inline block; new `InfoTip` tooltips explain metric jargon from one `GLOSSARY`. Frontend only; no backend or API change.

## Files
- `frontend/src/components/Dialog.tsx` — new; wrapper over `<dialog>`, `open` drives showModal()/close() (:15-20), backdrop click and Close button close it
- `frontend/src/components/InfoTip.tsx` — new; ⓘ button + `position: fixed` tooltip; closes on scroll/Esc/blur/leave; flips above near bottom (:46-52)
- `frontend/src/components/Icon.tsx` — adds `info` icon name and `i-info` symbol
- `frontend/src/step.ts` / `step.test.ts` — new; `stepIndex` clamp helper and its vitest cases
- `frontend/src/pages/Eval.tsx` — `GLOSSARY` (:14), `Term` (:29), InfoTips in KPIs/table/confusion line/Ablation/FailureDetail, panel blurbs, Dialog wiring (:363-390), inline detail + placeholder removed

## API contracts
None crossed. Rows come from `getEvalRun` (`frontend/src/api.ts:692`) as `EvalResultRow` (`api.ts:81`); `imageUrl === null` shows the "No image" empty state inside the dialog.

## Test entry points
- `frontend/src/step.test.ts` — `cd frontend && npx vitest run src/step.test.ts`
- Full gate: `cd frontend && npm run build && npm run lint && npm test`
- No jsdom/testing-library: Dialog, InfoTip and Eval have no automated tests.

## Acceptance criteria (verbatim from plan.md)
1. `npm run build`, `npm run lint`, `npm test` pass in `frontend/` (check: run them).
2. Clicking a failure row opens the dialog without scrolling the page; Esc, backdrop click and the close button each close it; focus returns to the row (check: code review of native `<dialog>` usage; manual below).
3. Prev / Next and ← / → move through failures; Prev disabled at first, Next disabled at last (check: `step.test.ts` + code review).
4. Every term listed in Solution has an InfoTip that opens on hover, focus and tap; tips on table headers are not clipped by the table scroll box (check: fixed positioning in code review; manual below).
5. Switching runs while the dialog is open closes it (check: `selectRun` resets `selectedFailure`).
6. Dialog and tips use existing colour tokens only, and no animation runs under reduced motion (check: grep for raw colours; review).
7. manual: with real runs under `data/runs/`, start the app, open Eval, click a failure low in the list, step with ←/→, close with Esc, then hover/tap the AUROC header and the ⓘ in the KPI row in both themes. (outside automated verification)

## Do not re-derive
- `selectedFailure` (-1 = none) alone decides dialog open: `activeFailure` at `Eval.tsx:217`; `selectRun` (:207) resets it.
- Dialog `onClose` fires on any close (Esc, button, backdrop) and sets selectedFailure to -1; native `<dialog>` handles focus return.
- Pre-existing, not this change: `MetricsTable` header has two "F1" columns (`Eval.tsx:~94-95`; the first is a bar column). Both now carry an InfoTip.
- Known plan risk (`risks.md`): Esc inside an open InfoTip may still close the dialog on some browsers; only `black/50` backdrop is a raw colour (`Dialog.tsx:36`).
- `Term` indexes `GLOSSARY[term]` with no fallback (type is `Record<string,string>`, so unknown keys give undefined silently).

## Diff
```diff
diff --git a/frontend/src/components/Dialog.tsx b/frontend/src/components/Dialog.tsx
new file mode 100644
index 0000000..5f7d77f
--- /dev/null
+++ b/frontend/src/components/Dialog.tsx
@@ -0,0 +1,47 @@
+import { useEffect, useRef } from 'react'
+import type { JSX, KeyboardEvent, ReactNode } from 'react'
+import { Button } from './Button.tsx'
+
+type Props = {
+  open: boolean
+  title: string
+  onClose: () => void
+  onKeyDown?: (e: KeyboardEvent<HTMLDialogElement>) => void
+  children: ReactNode
+}
+
+export function Dialog({ open, title, onClose, onKeyDown, children }: Props): JSX.Element {
+  const ref = useRef<HTMLDialogElement>(null)
+
+  useEffect(() => {
+    const d = ref.current
+    if (d === null) return
+    if (open && !d.open) d.showModal()
+    else if (!open && d.open) d.close()
+  }, [open])
+
+  return (
+    <dialog
+      ref={ref}
+      aria-label={title}
+      onClose={onClose}
+      onKeyDown={onKeyDown}
+      onClick={(e) => {
+        if (e.target === ref.current) ref.current?.close()
+      }}
+      className="m-auto max-h-[92vh] w-[min(720px,calc(100vw-32px))] rounded-md border border-line bg-surface p-0 text-ink backdrop:bg-black/50"
+    >
+      {open && (
+        <>
+          <div className="flex items-center justify-between gap-3 border-b border-line px-3.5 py-2.5">
+            <h2 className="min-w-0 truncate">{title}</h2>
+            <Button variant="ghost" onClick={() => ref.current?.close()}>
+              Close
+            </Button>
+          </div>
+          {children}
+        </>
+      )}
+    </dialog>
+  )
+}
diff --git a/frontend/src/components/Icon.tsx b/frontend/src/components/Icon.tsx
index 3715bdf..07e1737 100644
--- a/frontend/src/components/Icon.tsx
+++ b/frontend/src/components/Icon.tsx
@@ -1,4 +1,4 @@
-export type IconName = 'scan' | 'sliders' | 'chart' | 'sparkles' | 'check' | 'x' | 'alert' | 'clock' | 'pencil' | 'upload' | 'save' | 'file' | 'refresh' | 'sun' | 'moon' | 'monitor' | 'layers' | 'list' | 'eye' | 'gauge'
+export type IconName = 'scan' | 'sliders' | 'chart' | 'sparkles' | 'check' | 'x' | 'alert' | 'clock' | 'pencil' | 'upload' | 'save' | 'file' | 'refresh' | 'sun' | 'moon' | 'monitor' | 'layers' | 'list' | 'eye' | 'gauge' | 'info'
 
 /** Mount once near the app root; <Icon> references these symbols. */
 export function IconSprite() {
@@ -24,6 +24,7 @@ export function IconSprite() {
       <symbol id="i-list" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6h12M9 12h12M9 18h12M4 6h.01M4 12h.01M4 18h.01"/></symbol>
       <symbol id="i-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></symbol>
       <symbol id="i-gauge" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 14l4-4"/><path d="M3.3 19a10 10 0 1 1 17.4 0z"/></symbol>
+      <symbol id="i-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></symbol>
     </svg>
   )
 }
diff --git a/frontend/src/components/InfoTip.tsx b/frontend/src/components/InfoTip.tsx
new file mode 100644
index 0000000..d9e63e2
--- /dev/null
+++ b/frontend/src/components/InfoTip.tsx
@@ -0,0 +1,76 @@
+import { useEffect, useId, useRef, useState } from 'react'
+import type { JSX } from 'react'
+import { Icon } from './Icon.tsx'
+
+const TIP_W = 256
+
+export function InfoTip({ term, text }: { term: string; text: string }): JSX.Element {
+  const id = useId()
+  const btn = useRef<HTMLButtonElement>(null)
+  const tip = useRef<HTMLSpanElement>(null)
+  const [open, setOpen] = useState<boolean>(false)
+  const [pos, setPos] = useState<{ left: number; top: number }>({ left: 0, top: 0 })
+
+  useEffect(() => {
+    if (!open) return
+    const close = (): void => setOpen(false)
+    const onKey = (e: KeyboardEvent): void => {
+      if (e.key === 'Escape') {
+        e.stopPropagation() // keep Esc from also closing a surrounding dialog
+        close()
+      }
+    }
+    window.addEventListener('scroll', close, true)
+    document.addEventListener('keydown', onKey, true)
+    return () => {
+      window.removeEventListener('scroll', close, true)
+      document.removeEventListener('keydown', onKey, true)
+    }
+  }, [open])
+
+  const show = (): void => {
+    const r = btn.current?.getBoundingClientRect()
+    if (r === undefined) return
+    const left = Math.max(8, Math.min(r.left + r.width / 2 - TIP_W / 2, window.innerWidth - TIP_W - 8))
+    setPos({ left, top: r.bottom + 6 })
+    setOpen(true)
+  }
+
+  // Flip above when the tip would run off the bottom (measured after render).
+  useEffect(() => {
+    const r = btn.current?.getBoundingClientRect()
+    const h = tip.current?.offsetHeight
+    if (!open || r === undefined || h === undefined) return
+    if (r.bottom + 6 + h > window.innerHeight - 8 && r.top - 6 - h >= 8) {
+      setPos((p) => ({ ...p, top: r.top - 6 - h }))
+    }
+  }, [open])
+
+  return (
+    <span className="inline-flex" onMouseEnter={show} onMouseLeave={() => setOpen(false)}>
+      <button
+        ref={btn}
+        type="button"
+        aria-label={`About ${term}`}
+        aria-describedby={open ? id : undefined}
+        onFocus={show}
+        onBlur={() => setOpen(false)}
+        onClick={() => (open ? setOpen(false) : show())}
+        className="inline-flex items-center text-ink-3 hover:text-ink"
+      >
+        <Icon name="info" />
+      </button>
+      {open && (
+        <span
+          ref={tip}
+          id={id}
+          role="tooltip"
+          style={{ position: 'fixed', left: pos.left, top: pos.top, width: TIP_W }}
+          className="z-50 rounded-md border border-line-strong bg-surface p-2.5 text-left text-xs font-normal leading-snug text-ink-2"
+        >
+          {text}
+        </span>
+      )}
+    </span>
+  )
+}
diff --git a/frontend/src/pages/Eval.tsx b/frontend/src/pages/Eval.tsx
index e1bc1ce..3bcac70 100644
--- a/frontend/src/pages/Eval.tsx
+++ b/frontend/src/pages/Eval.tsx
@@ -2,11 +2,39 @@ import { useEffect, useState } from 'react'
 import type { JSX } from 'react'
 import { ApiError, getEvalRun, listEvalRuns, resolveFileUrl } from '../api.ts'
 import type { CategoryMetrics, EvalResultRow, EvalRunDetail, EvalRunSummary } from '../api.ts'
+import { Dialog } from '../components/Dialog.tsx'
+import { InfoTip } from '../components/InfoTip.tsx'
+import { Button } from '../components/Button.tsx'
+import { stepIndex } from '../step.ts'
 import { Alert } from '../components/Alert.tsx'
 import { EmptyState } from '../components/EmptyState.tsx'
 import { PageHeader } from '../components/PageHeader.tsx'
 import { Panel, PanelHeader } from '../components/Panel.tsx'
 
+const GLOSSARY: Record<string, string> = {
+  F1: 'Balance of precision and recall in one number, from 0 to 1. Higher is better.',
+  Precision: 'Of the images flagged FAIL (defective), the share that really were defective.',
+  Recall: 'Of the truly defective images, the share that were flagged FAIL.',
+  AUROC: 'How well the confidence score ranks defective images above good ones. 0.5 is chance, 1 is perfect.',
+  Accuracy: 'Share of all images where the verdict matched the label.',
+  'True fail': 'Defective image correctly flagged FAIL.',
+  'True pass': 'Good image correctly passed.',
+  'False fail': 'Good image wrongly flagged FAIL (false alarm).',
+  Missed: 'Defective image wrongly passed (a defect that slipped through).',
+  Ablation: 'Same images scored three ways: SAM only (segmentation alone), + judge (a model reviews each detection), + reference (the judge also compares against a known-good image).',
+  IoU: 'Overlap between the detected region and the true defect mask, from 0 to 1.',
+  confidence: 'How sure the system is that the image is defective.',
+}
+
+function Term({ term, children }: { term: string; children?: string }): JSX.Element {
+  return (
+    <span className="inline-flex items-center gap-1">
+      {children ?? term}
+      <InfoTip term={term} text={GLOSSARY[term]} />
+    </span>
+  )
+}
+
 function errorDetail(err: unknown, fallback: string): string {
   if (err instanceof ApiError) return err.detail
   return fallback
@@ -47,7 +75,7 @@ function Bar({ value, height, tone }: { value: number | null; height: number; to
 function Kpi({ label, value, accent = false }: { label: string; value: number | null; accent?: boolean }): JSX.Element {
   return (
     <div>
-      <dt className="text-xs text-ink-3">{label}</dt>
+      <dt className="text-xs text-ink-3"><Term term={label} /></dt>
       <dd className="mt-0.5 text-[26px] font-medium leading-tight">
         <Metric value={value} className={accent ? 'text-data' : ''} />
       </dd>
@@ -64,11 +92,11 @@ function MetricsTable({ perCategory }: { perCategory: Record<string, CategoryMet
         <thead>
           <tr className="border-b border-line-strong text-xs text-ink-3">
             <th className="py-2 pr-3 text-left font-medium">Category</th>
-            <th className="w-[28%] px-3 py-2 text-left font-medium min-[641px]:w-[32%]">F1</th>
-            <th className={`${th} pl-3`}>F1</th>
-            <th className={`${th} pl-3`}>Precision</th>
-            <th className={`${th} pl-3`}>Recall</th>
-            <th className={`${th} pl-3`}>AUROC</th>
+            <th className="w-[28%] px-3 py-2 text-left font-medium min-[641px]:w-[32%]"><Term term="F1" /></th>
+            <th className={`${th} pl-3`}><Term term="F1" /></th>
+            <th className={`${th} pl-3`}><Term term="Precision" /></th>
+            <th className={`${th} pl-3`}><Term term="Recall" /></th>
+            <th className={`${th} pl-3`}><Term term="AUROC" /></th>
           </tr>
         </thead>
         <tbody>
@@ -99,15 +127,21 @@ function FailureDetail({ row }: { row: EvalResultRow }): JSX.Element {
   // Parent keys this component by row, so the broken flag resets per row.
   const [imgBroken, setImgBroken] = useState<boolean>(false)
   return (
-    <div className="border-t border-line p-3.5">
+    <div className="p-3.5">
       <p className="text-sm font-medium">
         {row.category} · {row.image}
       </p>
       <p className="mt-1 text-[13px] text-ink-2">
         Label {row.label}, verdict {row.verdict}
         {row.defectType !== '' && `, defect ${row.defectType}`}
-        {` · confidence ${(row.confidence * 100).toFixed(1)}% · ${row.nDetections} detections`}
-        {row.iou !== null && ` · IoU ${row.iou.toFixed(3)}`}
+        {' · '}
+        <Term term="confidence" /> {(row.confidence * 100).toFixed(1)}% · {row.nDetections} detections
+        {row.iou !== null && (
+          <>
+            {' · '}
+            <Term term="IoU" /> {row.iou.toFixed(3)}
+          </>
+        )}
       </p>
       {row.imageUrl === null ? (
         <EmptyState icon="file" title="No image for this row" className="mt-3">
@@ -260,6 +294,9 @@ export default function Eval(): JSX.Element {
                     </div>
                   ) : (
                     <div className="flex flex-col gap-4 p-3.5">
+                      <p className="text-[13px] text-ink-3">
+                        How well this run separated good from defective images. FAIL means flagged as defective.
+                      </p>
                       <dl className="grid grid-cols-3 gap-4 min-[1001px]:grid-cols-5">
                         <Kpi label="F1" value={metrics.overall.f1} accent />
                         <Kpi label="Precision" value={metrics.overall.precision} />
@@ -268,8 +305,8 @@ export default function Eval(): JSX.Element {
                         <Kpi label="Accuracy" value={metrics.overall.accuracy} />
                       </dl>
                       <p className="num text-[13px] text-ink-2">
-                        True fail {metrics.overall.tp} · True pass {metrics.overall.tn} · False fail {metrics.overall.fp} ·
-                        Missed {metrics.overall.fn}
+                        <Term term="True fail" /> {metrics.overall.tp} · <Term term="True pass" /> {metrics.overall.tn} ·{' '}
+                        <Term term="False fail" /> {metrics.overall.fp} · <Term term="Missed" /> {metrics.overall.fn}
                       </p>
                       <MetricsTable perCategory={metrics.perCategory} />
                     </div>
@@ -278,7 +315,10 @@ export default function Eval(): JSX.Element {
 
                 {ablation.length >= 2 && (
                   <Panel>
-                    <PanelHeader title="Ablation · same seed, same N images" />
+                    <PanelHeader title={<>Ablation · same seed, same N images <InfoTip term="Ablation" text={GLOSSARY.Ablation} /></>} />
+                    <p className="px-3.5 pt-3 text-[13px] text-ink-3">
+                      F1 for the same images under SAM only, + judge and + reference.
+                    </p>
                     <ul className="flex flex-col gap-2.5 p-3.5">
                       {ablation.map((run) => {
                         const f1 = run.metrics?.overall.f1 ?? null
@@ -296,6 +336,9 @@ export default function Eval(): JSX.Element {
 
                 <Panel>
                   <PanelHeader title={`Failure examples (${failures.length})`} />
+                  <p className="px-3.5 pt-3 text-[13px] text-ink-3">
+                    Images where the verdict disagreed with the label. Select one to open it.
+                  </p>
                   {failures.length === 0 ? (
                     <div className="p-3.5">
                       <EmptyState icon="check" title="No failures in this run — every verdict matches its label." />
@@ -317,13 +360,32 @@ export default function Eval(): JSX.Element {
                           </li>
                         ))}
                       </ul>
-                      {activeFailure !== null ? (
-                        <FailureDetail key={`${activeFailure.category}-${activeFailure.image}`} row={activeFailure} />
-                      ) : (
-                        <div className="border-t border-line p-3.5">
-                          <EmptyState icon="eye" title="Select a failure above to view its image." />
-                        </div>
-                      )}
+                      <Dialog
+                        open={activeFailure !== null}
+                        title={activeFailure === null ? '' : `Failure ${selectedFailure + 1} of ${failures.length}`}
+                        onClose={() => setSelectedFailure(-1)}
+                        onKeyDown={(e) => {
+                          if (e.key === 'ArrowLeft') setSelectedFailure(stepIndex(selectedFailure, -1, failures.length))
+                          else if (e.key === 'ArrowRight') setSelectedFailure(stepIndex(selectedFailure, 1, failures.length))
+                        }}
+                      >
+                        {activeFailure !== null && (
+                          <>
+                            <FailureDetail key={`${activeFailure.category}-${activeFailure.image}`} row={activeFailure} />
+                            <div className="flex justify-between border-t border-line px-3.5 py-2.5">
+                              <Button disabled={selectedFailure <= 0} onClick={() => setSelectedFailure(selectedFailure - 1)}>
+                                Prev
+                              </Button>
+                              <Button
+                                disabled={selectedFailure >= failures.length - 1}
+                                onClick={() => setSelectedFailure(selectedFailure + 1)}
+                              >
+                                Next
+                              </Button>
+                            </div>
+                          </>
+                        )}
+                      </Dialog>
                     </>
                   )}
                 </Panel>
diff --git a/frontend/src/step.test.ts b/frontend/src/step.test.ts
new file mode 100644
index 0000000..64bdb35
--- /dev/null
+++ b/frontend/src/step.test.ts
@@ -0,0 +1,16 @@
+import { describe, expect, it } from 'vitest'
+import { stepIndex } from './step.ts'
+
+describe('stepIndex', () => {
+  it('steps forward and back', () => {
+    expect(stepIndex(2, 1, 5)).toBe(3)
+    expect(stepIndex(2, -1, 5)).toBe(1)
+  })
+  it('clamps at both ends', () => {
+    expect(stepIndex(4, 1, 5)).toBe(4)
+    expect(stepIndex(0, -1, 5)).toBe(0)
+  })
+  it('returns -1 for an empty list', () => {
+    expect(stepIndex(0, 1, 0)).toBe(-1)
+  })
+})
diff --git a/frontend/src/step.ts b/frontend/src/step.ts
new file mode 100644
index 0000000..f8384f7
--- /dev/null
+++ b/frontend/src/step.ts
@@ -0,0 +1,5 @@
+/** Move `index` by `delta`, clamped to the list; -1 when the list is empty. */
+export function stepIndex(index: number, delta: number, length: number): number {
+  if (length === 0) return -1
+  return Math.min(length - 1, Math.max(0, index + delta))
+}
```
