import type { EvalMetrics, EvalResultRow } from './api.ts'

export type FailureKind = 'false-fail' | 'missed'
type RunLike = { runId: string; metrics: EvalMetrics | null }
type MetricKey = 'f1' | 'precision' | 'recall' | 'auroc' | 'accuracy'

/** Run with the highest overall F1; ties and null metrics keep list order. */
export function pickDefaultRun(runs: RunLike[]): string {
  let best = -1
  let id = ''
  for (const run of runs) {
    const f1 = run.metrics?.overall.f1 ?? -1
    if (id === '' || f1 > best) {
      best = f1
      id = run.runId
    }
  }
  return id
}

export function failureKind(row: Pick<EvalResultRow, 'label' | 'verdict'>): FailureKind | null {
  if (row.label === 'good' && row.verdict === 'FAIL') return 'false-fail'
  if (row.label === 'defective' && row.verdict === 'PASS') return 'missed'
  return null
}

/** Rows matching kind and category; '' means any. */
export function filterFailures(rows: EvalResultRow[], kind: FailureKind | '', category: string): EvalResultRow[] {
  return rows.filter((r) => {
    const k = failureKind(r)
    return k !== null && (kind === '' || k === kind) && (category === '' || r.category === category)
  })
}

/** current minus the best other run's value; null when no other run has metrics. */
export function bestOtherDelta(current: RunLike, group: RunLike[], key: MetricKey = 'f1'): number | null {
  const mine = current.metrics?.overall[key]
  if (mine == null) return null
  const others = group.filter((r) => r.runId !== current.runId).map((r) => r.metrics?.overall[key])
  const valid = others.filter((v): v is number => v != null)
  return valid.length === 0 ? null : mine - Math.max(...valid)
}

/** 0-4 bucket of a 0-1 value. */
export function shadeLevel(value: number | null): number | null {
  if (value === null) return null
  return Math.min(4, Math.max(0, Math.round(value * 4)))
}

export function runTag(runId: string, mode: string): string {
  const suffix = `-${mode}`
  return runId.endsWith(suffix) && runId.length > suffix.length ? runId.slice(0, -suffix.length) : runId
}
