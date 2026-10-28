import type { JSX, ReactNode } from 'react'

interface Counts {
  tp: number
  tn: number
  fp: number
  fn: number
}

/** 2x2 grid: rows are the actual label, columns the verdict. `term` renders a cell name (with its InfoTip). */
export function ConfusionMatrix({ counts, term }: { counts: Counts; term: (name: string) => ReactNode }): JSX.Element {
  const head = 'text-center text-xs font-medium text-ink-3'
  const side = 'flex items-center text-xs font-medium text-ink-3'
  const cell = (name: string, n: number, good: boolean): JSX.Element => (
    <div className={`rounded-sm px-3 py-2.5 ${good ? 'bg-pass-tint' : 'bg-fail-tint'}`}>
      <div className="num text-[22px] font-medium leading-tight">{n}</div>
      <div className={`text-[13px] ${good ? 'text-pass' : 'text-fail'}`}>{term(name)}</div>
    </div>
  )
  return (
    <div className="grid max-w-md grid-cols-[4.5rem_1fr_1fr] gap-1.5" role="group" aria-label="Confusion matrix">
      <span />
      <span className={head}>Verdict FAIL</span>
      <span className={head}>Verdict PASS</span>
      <span className={side}>Defective</span>
      {cell('True fail', counts.tp, true)}
      {cell('Missed', counts.fn, false)}
      <span className={side}>Good</span>
      {cell('False fail', counts.fp, false)}
      {cell('True pass', counts.tn, true)}
    </div>
  )
}
