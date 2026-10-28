import { describe, expect, it } from 'vitest'
import { boxPercent } from './geometry.ts'

describe('boxPercent', () => {
  it('converts pixels to percentages', () => {
    expect(boxPercent([50, 25, 100, 50], 200, 100)).toEqual({ left: 25, top: 25, width: 50, height: 50 })
  })
  it('returns null until the natural size is known', () => {
    expect(boxPercent([1, 2, 3, 4], 0, 100)).toBeNull()
    expect(boxPercent([1, 2, 3, 4], 100, 0)).toBeNull()
    expect(boxPercent([1, 2, 3, 4], -1, -1)).toBeNull()
  })
})
