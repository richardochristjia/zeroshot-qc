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

describe('parseInspectionResult judge fields', () => {
  it('defaults source to sam and parses missed defects, legacy strings included', () => {
    const det = { id: 'j1', label: 'judge', score: 0.5, bbox: [1, 2, 3, 4], mask_rle: { size: [1, 1], counts: '0' }, area_px: 1, length_px: 1 }
    const out = parseInspectionResult({
      ...base,
      detections: [det, { ...det, id: 'j2', source: 'judge' }],
      verdict: { ...base.verdict, missed_defects: [{ description: 'crack', box: [0, 0, 5, 5] }, 'old'] },
    })
    expect(out.detections.map((d) => d.source)).toEqual(['sam', 'judge'])
    expect(out.verdict.missedDefects).toEqual([{ description: 'crack', box: [0, 0, 5, 5] }, { description: 'old', box: null }])
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
