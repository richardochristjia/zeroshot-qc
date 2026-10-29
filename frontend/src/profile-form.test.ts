import { describe, expect, it } from 'vitest'
import type { ProductProfile } from './api.ts'
import { fromForm, isDirty, toForm, validateForm } from './profile-form.ts'

const base: ProductProfile = {
  id: 'bottle_v2',
  name: 'Bottle',
  defectPrompts: ['scratch'],
  rules: 'r',
  mmPerPx: null,
  minScore: 0.3,
  referenceImage: null,
}

describe('profile-form', () => {
  it('round trips null mm and reference', () => {
    expect(fromForm(toForm(base))).toEqual(base)
  })
  it('keeps trailing newline in the form, saves as one prompt', () => {
    const f = { ...toForm(base), prompts: 'a\n' }
    expect(f.prompts).toBe('a\n')
    expect(fromForm(f).defectPrompts).toEqual(['a'])
  })
  it('flags blank-only prompts', () => {
    expect(validateForm({ ...toForm(base), prompts: '\n  \n' }).prompts).toBeDefined()
  })
  it('validates mm per px', () => {
    for (const bad of ['0.', 'abc', '-1']) expect(validateForm({ ...toForm(base), mmPerPx: bad }).mmPerPx).toBeDefined()
    const blank = { ...toForm(base), mmPerPx: '' }
    expect(validateForm(blank).mmPerPx).toBeUndefined()
    expect(fromForm(blank).mmPerPx).toBeNull()
    expect(validateForm({ ...toForm(base), mmPerPx: '0.05' }).mmPerPx).toBeUndefined()
  })
  it('validates min score', () => {
    for (const bad of ['', '1.2']) expect(validateForm({ ...toForm(base), minScore: bad }).minScore).toBeDefined()
    expect(validateForm({ ...toForm(base), minScore: '0.3' }).minScore).toBeUndefined()
  })
  it('validates a new id', () => {
    expect(validateForm({ ...toForm(base), id: 'bad id!' }, { checkId: true }).id).toBeDefined()
    expect(validateForm(toForm(base), { checkId: true }).id).toBeUndefined()
  })
  it('tracks dirty state', () => {
    const f = toForm(base)
    expect(isDirty(f, toForm(base))).toBe(false)
    expect(isDirty({ ...f, name: 'x' }, toForm(base))).toBe(true)
    expect(isDirty(f, null)).toBe(true)
  })
})
