import { beforeEach, describe, expect, it } from 'vitest'
import { applyTheme, readStoredTheme, resolveTheme } from './theme.ts'

describe('resolveTheme', () => {
  it('accepts only light and dark', () => {
    expect(resolveTheme('light')).toBe('light')
    expect(resolveTheme('dark')).toBe('dark')
    expect(resolveTheme('system')).toBe('system')
    expect(resolveTheme('blue')).toBe('system')
    expect(resolveTheme(null)).toBe('system')
    expect(resolveTheme(7)).toBe('system')
  })
})

describe('applyTheme', () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    globalThis.localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    } as unknown as Storage
    globalThis.document = { documentElement: { dataset: {} } } as unknown as Document
  })

  it('sets and clears data-theme and persists', () => {
    applyTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(readStoredTheme()).toBe('dark')
    applyTheme('system')
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(readStoredTheme()).toBe('system')
  })

  it('survives blocked storage', () => {
    globalThis.localStorage = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    } as unknown as Storage
    expect(() => applyTheme('light')).not.toThrow()
    expect(readStoredTheme()).toBe('system')
  })
})
