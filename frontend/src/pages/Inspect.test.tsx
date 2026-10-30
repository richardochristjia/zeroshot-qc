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

test('picking a new file mid-run aborts the old run and drops its verdict', async () => {
  let resolve: (value: api.InspectionResult) => void = () => {}
  // Like real fetch: rejects with AbortError once its signal aborts.
  vi.mocked(api.inspectImage).mockImplementation(({ signal }) => new Promise((r, reject) => {
    resolve = r
    signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
  }))
  render(<MemoryRouter><Inspect /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /Sample one/ }))
  await waitFor(() => expect(api.inspectImage).toHaveBeenCalled())
  const { signal } = vi.mocked(api.inspectImage).mock.calls[0][0]
  const next = new File(['y'], 'other.png', { type: 'image/png' })
  fireEvent.change(screen.getByLabelText('Image file'), { target: { files: { item: () => next } } })
  expect(signal?.aborted).toBe(true)
  resolve(result)
  await new Promise((r) => setTimeout(r, 0))
  expect(screen.queryByText('FAIL')).toBeNull()
  expect((screen.getByRole('button', { name: 'Inspect' }) as HTMLButtonElement).disabled).toBe(false)
})

test('picking a new file cancels a pending rules re-run', async () => {
  render(<MemoryRouter><Inspect /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /Sample one/ }))
  await screen.findByText('FAIL')
  fireEvent.change(screen.getByPlaceholderText(/Edit rules/), { target: { value: 'stricter' } })
  const next = new File(['y'], 'other.png', { type: 'image/png' })
  fireEvent.change(screen.getByLabelText('Image file'), { target: { files: { item: () => next } } })
  await new Promise((r) => setTimeout(r, 700))
  expect(api.inspectImage).toHaveBeenCalledTimes(1)
})

test('a rules edit re-runs the inspection and a newer keystroke aborts the stale request', async () => {
  render(<MemoryRouter><Inspect /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /Sample one/ }))
  await screen.findByText('FAIL')
  vi.mocked(api.inspectImage).mockImplementation(({ signal }) => new Promise((_, reject) => {
    signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
  }))
  const box = screen.getByPlaceholderText(/Edit rules/)
  fireEvent.change(box, { target: { value: 'a' } })
  await waitFor(() => expect(api.inspectImage).toHaveBeenCalledTimes(2), { timeout: 1500 })
  const first = vi.mocked(api.inspectImage).mock.calls[1][0]
  expect(first.rules).toBe('a')
  fireEvent.change(box, { target: { value: 'ab' } })
  expect(first.signal?.aborted).toBe(true)
  await waitFor(() => expect(api.inspectImage).toHaveBeenCalledTimes(3), { timeout: 1500 })
  expect(vi.mocked(api.inspectImage).mock.calls[2][0].rules).toBe('ab')
})
