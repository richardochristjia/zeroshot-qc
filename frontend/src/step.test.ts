import { describe, expect, it } from 'vitest'
import { stepIndex } from './step.ts'

describe('stepIndex', () => {
  it('steps forward and back', () => {
    expect(stepIndex(2, 1, 5)).toBe(3)
    expect(stepIndex(2, -1, 5)).toBe(1)
  })
  it('clamps at both ends', () => {
    expect(stepIndex(4, 1, 5)).toBe(4)
    expect(stepIndex(0, -1, 5)).toBe(0)
  })
  it('returns -1 for an empty list', () => {
    expect(stepIndex(0, 1, 0)).toBe(-1)
  })
})
