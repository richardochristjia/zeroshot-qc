import { expect, it } from 'vitest';
import { N_IMAGES, ROWS } from './metrics';

it('rounds F1 to the bundled eval numbers', () => {
  expect(ROWS.map((r) => r.f1.toFixed(2))).toEqual(['0.00', '0.87', '0.92']);
});

it('reports the 150-image set', () => {
  expect(N_IMAGES).toBe(150);
});
