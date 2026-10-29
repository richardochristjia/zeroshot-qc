import { describe, expect, it } from 'vitest'
import { FRAME_H, FRAME_W, HOLD_MS, PRESENT_DIFF, arm, frameDiff, idleState, step } from './line-trigger.ts'
import type { TriggerState } from './line-trigger.ts'

const N = FRAME_W * FRAME_H
const uniform = (v: number): Uint8Array => new Uint8Array(N).fill(v)
/** Background 100 with the first `n` pixels set to `v`. */
const patch = (v: number, n = N / 2): Uint8Array => {
  const f = uniform(100)
  f.fill(v, 0, n)
  return f
}

/** Feed frames every 100ms; returns final state and capture count. */
function run(start: TriggerState, frames: Uint8Array[]): { state: TriggerState; captures: number } {
  let state = start
  let captures = 0
  frames.forEach((f, i) => {
    const r = step(state, f, i * 100)
    state = r.state
    if (r.capture) captures++
  })
  return { state, captures }
}

const holdFrames = Math.ceil(HOLD_MS / 100) + 3
const bg = uniform(100)

describe('line trigger', () => {
  it('1 stays armed on background frames', () => {
    const r = run(arm(bg), Array.from({ length: 20 }, () => uniform(100)))
    expect(r.state.phase).toBe('armed')
    expect(r.captures).toBe(0)
  })

  it('2 captures exactly once when a part holds still', () => {
    const r = run(arm(bg), Array.from({ length: holdFrames + 10 }, () => patch(220)))
    expect(r.captures).toBe(1)
  })

  it('3 does not capture while the part keeps moving', () => {
    const frames = Array.from({ length: 30 }, (_, i) => patch(i % 2 ? 220 : 160))
    const r = run(arm(bg), frames)
    expect(r.state.phase).toBe('settling')
    expect(r.captures).toBe(0)
  })

  it('4 waits for clear after capture', () => {
    const r = run(arm(bg), Array.from({ length: holdFrames + 30 }, () => patch(220)))
    expect(r.state.phase).toBe('waiting-clear')
    expect(r.captures).toBe(1)
  })

  it('5 re-arms once the scene clears', () => {
    const frames = [...Array.from({ length: holdFrames }, () => patch(220)), uniform(100)]
    expect(run(arm(bg), frames).state.phase).toBe('armed')
  })

  it('6 ignores noise below PRESENT_DIFF', () => {
    const noisy = uniform(100 + PRESENT_DIFF - 2)
    const r = run(arm(bg), Array.from({ length: 20 }, () => noisy))
    expect(r.state.phase).toBe('armed')
    expect(r.captures).toBe(0)
  })

  it('7 frameDiff of identical buffers is 0', () => {
    expect(frameDiff(uniform(77), uniform(77))).toBe(0)
  })

  it('8 frameDiff of black vs white is 255', () => {
    expect(frameDiff(uniform(0), uniform(255))).toBe(255)
  })

  it('9 idle never captures', () => {
    const r = run(idleState(), Array.from({ length: 20 }, () => patch(220)))
    expect(r.state.phase).toBe('idle')
    expect(r.captures).toBe(0)
  })
})
