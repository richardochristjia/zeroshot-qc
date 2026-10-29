import type { ProductProfile } from './api.ts'

/** Same rule as the backend's _PROFILE_NAME_RE. */
export const PROFILE_ID_RE = /^[A-Za-z0-9_-]+$/

/** Every field is raw text so typing never gets rewritten. */
export type ProfileForm = {
  id: string
  name: string
  prompts: string
  rules: string
  mmPerPx: string
  minScore: string
  referenceImage: string
}

export type FormErrors = Partial<Record<'id' | 'name' | 'prompts' | 'mmPerPx' | 'minScore', string>>

export function toForm(p: ProductProfile): ProfileForm {
  return {
    id: p.id,
    name: p.name,
    prompts: p.defectPrompts.join('\n'),
    rules: p.rules,
    mmPerPx: p.mmPerPx === null ? '' : String(p.mmPerPx),
    minScore: String(p.minScore),
    referenceImage: p.referenceImage ?? '',
  }
}

export function promptLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

function parseNumber(text: string): number | null {
  const t = text.trim()
  if (t === '') return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}

/** "0." is flagged invalid but kept as text, so 0.05 can be typed. */
export function validateForm(f: ProfileForm, opts: { checkId?: boolean } = {}): FormErrors {
  const errors: FormErrors = {}
  if (opts.checkId === true && !PROFILE_ID_RE.test(f.id)) errors.id = 'Use letters, digits, - or _ only.'
  if (f.name.trim() === '') errors.name = 'Name is required.'
  if (promptLines(f.prompts).length === 0) errors.prompts = 'Add at least one prompt.'
  const mm = f.mmPerPx.trim()
  if (mm !== '' && !(parseNumber(mm) !== null && /\d$/.test(mm) && (parseNumber(mm) as number) > 0)) {
    errors.mmPerPx = 'Leave blank or enter a number above 0.'
  }
  const score = parseNumber(f.minScore)
  if (score === null || score < 0 || score > 1) errors.minScore = 'Enter a number from 0 to 1.'
  return errors
}

/** Call only on a form that passed validateForm. */
export function fromForm(f: ProfileForm): ProductProfile {
  const ref = f.referenceImage.trim()
  return {
    id: f.id.trim(),
    name: f.name.trim(),
    defectPrompts: promptLines(f.prompts),
    rules: f.rules,
    mmPerPx: parseNumber(f.mmPerPx),
    minScore: parseNumber(f.minScore) ?? 0,
    referenceImage: ref === '' ? null : ref,
  }
}

export function isDirty(form: ProfileForm, saved: ProfileForm | null): boolean {
  return saved === null || JSON.stringify(form) !== JSON.stringify(saved)
}
