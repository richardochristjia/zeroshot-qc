// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../api.ts'
import { diffRules } from '../tune-view.ts'
import Tune from './Tune.tsx'

vi.mock('../api.ts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api.ts')>()),
  listTuneRuns: vi.fn(),
  getTuneRun: vi.fn(),
}))

// Shape of backend `tune.json`, parsed by the real parser.
const record = {
  run_id: '20261101T000000Z-bottle',
  category: 'bottle',
  adapter: 'scripted',
  seed: 0,
  counts: {},
  initial_rules: 'FAIL any scratch. PASS otherwise.',
  final_rules: 'FAIL any scratch. Ignore reflections. PASS otherwise.',
  rounds: [
    { round: 1, rules: 'x', rationale: 'Added a reflection rule.', metrics: { f1: 0.8 }, accepted: true },
    { round: 2, rules: 'y', rationale: 'Too strict.', metrics: { f1: 0.7 }, accepted: false },
  ],
  heldout: { before: { f1: 0.6 }, after: { f1: 0.75 } },
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

test('renders KPIs, rounds and the rules diff', async () => {
  vi.mocked(api.listTuneRuns).mockResolvedValue([
    { runId: record.run_id, category: 'bottle', adapter: 'scripted', beforeF1: 0.6, afterF1: 0.75, roundsAccepted: 1 },
  ])
  vi.mocked(api.getTuneRun).mockResolvedValue(api.parseTuneRunDetail(record))
  render(<Tune />)
  await waitFor(() => expect(screen.getByText('0.750')).toBeTruthy())
  expect(screen.getByText('Held-out F1 before')).toBeTruthy()
  expect(screen.getByText('Accepted')).toBeTruthy()
  expect(screen.getByText('Rejected')).toBeTruthy()
  expect(screen.getByText('Too strict.')).toBeTruthy()
  expect(screen.getByText(/\+ Ignore reflections\./)).toBeTruthy()
})

test('shows an empty state without runs', async () => {
  vi.mocked(api.listTuneRuns).mockResolvedValue([])
  render(<Tune />)
  await waitFor(() => expect(screen.getByText('No tune runs yet')).toBeTruthy())
})

test('diffRules marks added and removed lines', () => {
  expect(diffRules('A. B.', 'A. C.')).toEqual([
    { kind: 'same', text: 'A.' },
    { kind: 'removed', text: 'B.' },
    { kind: 'added', text: 'C.' },
  ])
})
