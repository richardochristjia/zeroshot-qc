export interface BoxPercent {
  left: number
  top: number
  width: number
  height: number
}

/** Convert a [x, y, w, h] pixel box to percentages of the image; null until the image size is known. */
export function boxPercent(
  bbox: readonly [number, number, number, number],
  naturalWidth: number,
  naturalHeight: number,
): BoxPercent | null {
  if (naturalWidth <= 0 || naturalHeight <= 0) return null
  const [x, y, w, h] = bbox
  return {
    left: (x / naturalWidth) * 100,
    top: (y / naturalHeight) * 100,
    width: (w / naturalWidth) * 100,
    height: (h / naturalHeight) * 100,
  }
}
