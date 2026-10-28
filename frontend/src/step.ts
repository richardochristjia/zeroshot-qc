/** Move `index` by `delta`, clamped to the list; -1 when the list is empty. */
export function stepIndex(index: number, delta: number, length: number): number {
  if (length === 0) return -1
  return Math.min(length - 1, Math.max(0, index + delta))
}
