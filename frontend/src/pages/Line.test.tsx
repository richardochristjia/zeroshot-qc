// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as api from '../api.ts'
import Line from './Line.tsx'

vi.mock('../api.ts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api.ts')>()),
  listProfiles: vi.fn(),
  inspectImage: vi.fn(),
}))

const profile = { id: 'p1', name: 'P1', defectPrompts: [], rules: 'FAIL any scratch', mmPerPx: null, minScore: 0.1, referenceImage: null }
const result: api.InspectionResult = {
  id: 'r1',
  profileId: 'p1',
  detections: [],
  verdict: { verdict: 'PASS', confidence: 0.9, rulings: [], missedDefects: [], partMatches: true, summary: 'ok' },
  overlayUrl: '',
  timingsMs: { segment: 1, judge: 1, total: 2 },
  demo: false,
}

beforeEach(() => {
  vi.mocked(api.listProfiles).mockResolvedValue([profile])
  vi.mocked(api.inspectImage).mockResolvedValue(result)
  Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })
  Object.defineProperty(navigator, 'mediaDevices', {
    value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [] })) },
    configurable: true,
  })
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
  Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', { value: 640, configurable: true })
  Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', { value: 480, configurable: true })
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage: vi.fn() } as never)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb) => cb(new Blob(['x'], { type: 'image/jpeg' })))
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

async function captureAndGetRules(): Promise<string | undefined> {
  const before = vi.mocked(api.inspectImage).mock.calls.length
  const button = screen.getByRole('button', { name: 'Capture now' })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(button)
  await waitFor(() => expect(api.inspectImage).toHaveBeenCalledTimes(before + 1))
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  return vi.mocked(api.inspectImage).mock.calls[before][0].rules
}

test('Apply sends the textarea rules on the next inspect and Clear omits them', async () => {
  render(<MemoryRouter><Line /></MemoryRouter>)
  const box = (await screen.findByLabelText('Rules for this session')) as HTMLTextAreaElement
  await waitFor(() => expect(box.value).toBe('FAIL any scratch'))
  expect(await captureAndGetRules()).toBeUndefined()

  fireEvent.change(box, { target: { value: 'FAIL any scratch\nalso fail any dent' } })
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
  expect(await captureAndGetRules()).toBe('FAIL any scratch\nalso fail any dent')

  fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
  expect(await captureAndGetRules()).toBeUndefined()
})
