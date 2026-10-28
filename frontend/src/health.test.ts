import { afterEach, describe, expect, it, vi } from 'vitest'
import { getHealth } from './api.ts'

afterEach(() => vi.unstubAllGlobals())

const reply = (body: unknown, ok = true) =>
  vi.fn().mockResolvedValue({ ok, status: ok ? 200 : 500, json: async () => body })

describe('getHealth', () => {
  it('returns ok when status is ok', async () => {
    vi.stubGlobal('fetch', reply({ status: 'ok', models: {} }))
    expect(await getHealth()).toBe('ok')
  })
  it('returns down for other bodies and HTTP errors', async () => {
    vi.stubGlobal('fetch', reply({ status: 'degraded' }))
    expect(await getHealth()).toBe('down')
    vi.stubGlobal('fetch', reply({}, false))
    expect(await getHealth()).toBe('down')
  })
  it('returns down when the network fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    expect(await getHealth()).toBe('down')
  })
  it('rethrows abort', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('x', 'AbortError')))
    await expect(getHealth()).rejects.toThrow()
  })
})
