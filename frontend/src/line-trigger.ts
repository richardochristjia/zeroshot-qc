/** Pure background-difference + stillness trigger for Line mode. No DOM. */
export const FRAME_W = 64
export const FRAME_H = 48
export const PRESENT_DIFF = 18
export const STILL_DIFF = 4
export const HOLD_MS = 600

export type Phase = 'idle' | 'armed' | 'settling' | 'waiting-clear'

export interface TriggerState {
  phase: Phase
  background: Uint8Array | null
  prev: Uint8Array | null
  stillSince: number
}

export function toGray(rgba: Uint8ClampedArray): Uint8Array {
  const out = new Uint8Array(rgba.length / 4)
  for (let i = 0; i < out.length; i++) {
    out[i] = 0.299 * rgba[i * 4] + 0.587 * rgba[i * 4 + 1] + 0.114 * rgba[i * 4 + 2]
  }
  return out
}

/** Mean absolute difference, 0..255. */
export function frameDiff(a: Uint8Array, b: Uint8Array): number {
  const n = Math.min(a.length, b.length)
  if (n === 0) return 0
  let sum = 0
  for (let i = 0; i < n; i++) sum += Math.abs(a[i] - b[i])
  return sum / n
}

export const idleState = (): TriggerState => ({ phase: 'idle', background: null, prev: null, stillSince: 0 })

export const arm = (frame: Uint8Array): TriggerState => ({ phase: 'armed', background: frame, prev: frame, stillSince: 0 })

export const pause = (): TriggerState => idleState()

export function step(state: TriggerState, frame: Uint8Array, nowMs: number): { state: TriggerState; capture: boolean } {
  const { background, prev } = state
  if (state.phase === 'idle' || background === null) return { state, capture: false }
  const present = frameDiff(frame, background) > PRESENT_DIFF
  let next: TriggerState = { ...state, prev: frame }
  let capture = false
  if (state.phase === 'armed') {
    if (present) next = { ...next, phase: 'settling', stillSince: nowMs }
  } else if (state.phase === 'settling') {
    if (!present) next = { ...next, phase: 'armed' }
    else if (prev !== null && frameDiff(frame, prev) > STILL_DIFF) next = { ...next, stillSince: nowMs }
    else if (nowMs - state.stillSince >= HOLD_MS) {
      next = { ...next, phase: 'waiting-clear' }
      capture = true
    }
  } else if (!present) {
    next = { ...next, phase: 'armed' }
  }
  return { state: next, capture }
}
