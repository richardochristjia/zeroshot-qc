import { expect, it } from 'vitest';
import { FPS, SCENES, totalFrames } from './script';

it('totals 150 s, within the 180 s cap', () => {
  expect(totalFrames()).toBe(4500);
  expect(totalFrames() / FPS).toBeLessThanOrEqual(180);
});

it('names a .mov for every recording scene', () => {
  for (const s of SCENES.filter((s) => s.recording)) expect(s.recording).toMatch(/\.mov$/);
});

it('keeps zoom keyframes ordered and inside the scene', () => {
  for (const s of SCENES) {
    const at = (s.zoom ?? []).map((k) => k.at);
    expect(at).toEqual([...at].sort((a, b) => a - b));
    for (const t of at) expect(t).toBeLessThanOrEqual(s.seconds);
    expect(new Set(at).size).toBe(at.length);
  }
});
