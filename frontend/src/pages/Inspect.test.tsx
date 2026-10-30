// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as api from '../api.ts'
import Inspect from './Inspect.tsx'

vi.mock('../api.ts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api.ts')>()),
  listProfiles: vi.fn(),
  listSamples: vi.fn(),
  inspectImage: vi.fn(),
}))

const profile = { id: 'p1', name: 'P1', defectPrompts: [], rules: '', mmPerPx: null, minScore: 0.1, referenceImage: null }
const sample = { id: 's1', label: 'Sample one', profileId: 'p1', imageUrl: '/files/samples/s1.png' }
const result: api.InspectionResult = {
  id: 'r1',
  profileId: 'p1',
  detections: [],
  verdict: { verdict: 'FAIL', confidence: 0.9, rulings: [], missedDefects: [], partMatches: true, summary: 'ok' },
  overlayUrl: '',
  timingsMs: { segment: 1, judge: 1, total: 2 },
  demo: false,
}

beforeEach(() => {
  vi.mocked(api.listProfiles).mockResolvedValue([profile])
  vi.mocked(api.listSamples).mockResolvedValue([sample])
  vi.mocked(api.inspectImage).mockResolvedValue(result)
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, blob: async () => new Blob(['x'], { type: 'image/png' }) })))
  URL.createObjectURL = vi.fn(() => `blob:${Math.random()}`)
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

test('clicking a sample starts an inspection that is not aborted by the new preview', async () => {
  render(<MemoryRouter><Inspect /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /Sample one/ }))
  await waitFor(() => expect(api.inspectImage).toHaveBeenCalled())
  expect(vi.mocked(api.inspectImage).mock.calls[0][0].signal?.aborted).toBe(false)
  expect(await screen.findByText('FAIL')).toBeTruthy()
})

test('the run is aborted on unmount', async () => {
  vi.mocked(api.inspectImage).mockReturnValue(new Promise(() => {}))
  const { unmount } = render(<MemoryRouter><Inspect /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /Sample one/ }))
  await waitFor(() => expect(api.inspectImage).toHaveBeenCalled())
  const { signal } = vi.mocked(api.inspectImage).mock.calls[0][0]
  unmount()
  expect(signal?.aborted).toBe(true)
})
