import { describe, expect, it } from 'vitest'
import type { EvalMetrics, EvalResultRow } from './api.ts'
import { bestOtherDelta, failureKind, filterFailures, pickDefaultRun, runTag, shadeLevel } from './eval-view.ts'

const run = (runId: string, f1: number | null) => ({
  runId,
  metrics: f1 === null ? null : ({ overall: { f1 } } as unknown as EvalMetrics),
})
const row = (category: string, label: 'good' | 'defective', verdict: 'PASS' | 'FAIL') =>
  ({ category, label, verdict }) as EvalResultRow

describe('eval-view', () => {
  it('picks default run', () => {
    expect(pickDefaultRun([run('a', 0), run('b', 0.919), run('c', 0.872)])).toBe('b')
    expect(pickDefaultRun([run('a', null), run('b', null)])).toBe('a')
    expect(pickDefaultRun([])).toBe('')
  })
  it('classifies and filters failures', () => {
    expect(failureKind(row('x', 'good', 'FAIL'))).toBe('false-fail')
    expect(failureKind(row('x', 'defective', 'PASS'))).toBe('missed')
    expect(failureKind(row('x', 'good', 'PASS'))).toBeNull()
    const rows = [row('bottle', 'defective', 'PASS'), row('cable', 'defective', 'PASS'), row('bottle', 'good', 'FAIL')]
    expect(filterFailures(rows, 'missed', 'bottle')).toEqual([rows[0]])
    expect(filterFailures(rows, '', '')).toHaveLength(3)
  })
  it('computes delta', () => {
    const cur = run('c', 0.872)
    expect(bestOtherDelta(cur, [run('a', 0.919), run('b', 0), cur])).toBeCloseTo(-0.047)
    expect(bestOtherDelta(cur, [cur])).toBeNull()
  })
  it('tags runs', () => {
    expect(runTag('m5verify-sam_judge', 'sam_judge')).toBe('m5verify')
    expect(runTag('smoke', 'sam_only')).toBe('smoke')
  })
  it('shades', () => {
    expect([0, 0.5, 1, 1.4, null].map(shadeLevel)).toEqual([0, 2, 4, 4, null])
  })
})
