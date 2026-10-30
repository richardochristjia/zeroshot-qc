import { afterEach, describe, expect, it, vi } from 'vitest'
import { listSamples, parseInspectionResult } from './api.ts'

afterEach(() => vi.unstubAllGlobals())

const base = {
  id: 'i1',
  profile_id: 'bottle',
  detections: [],
  verdict: { verdict: 'PASS', confidence: 0.9, summary: 's', rulings: [], missed_defects: [], part_matches: true },
  overlay_url: '/files/x.png',
  timings_ms: { segment: 1, judge: 2, total: 3 },
}

describe('parseInspectionResult demo flag', () => {
  it('treats a missing demo as false', () => {
    expect(parseInspectionResult(base).demo).toBe(false)
  })
  it('reads demo true', () => {
    expect(parseInspectionResult({ ...base, demo: true }).demo).toBe(true)
  })
})

describe('listSamples', () => {
  it('maps entries and swallows failures', async () => {
    const body = [{ id: 'a', label: 'A', profile_id: 'bottle', image_url: '/files/samples/a.png' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }))
    expect(await listSamples()).toEqual([{ id: 'a', label: 'A', profileId: 'bottle', imageUrl: '/files/samples/a.png' }])
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    expect(await listSamples()).toEqual([])
  })
})
