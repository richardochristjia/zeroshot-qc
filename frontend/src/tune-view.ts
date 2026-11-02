export type DiffLine = { kind: 'same' | 'added' | 'removed'; text: string }

// Rules are usually one paragraph, so split on newlines and sentence ends.
const split = (text: string): string[] =>
  text.split(/\n|(?<=[.;])\s+/).map((l) => l.trim()).filter(Boolean)

/** Line-level diff via longest common subsequence. */
export function diffRules(before: string, after: string): DiffLine[] {
  const a = split(before)
  const b = split(after)
  const lcs = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1])
  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      out.push({ kind: 'same', text: a[i++] })
      j++
    }
    else if (j >= b.length || (i < a.length && lcs[i + 1][j] >= lcs[i][j + 1])) out.push({ kind: 'removed', text: a[i++] })
    else out.push({ kind: 'added', text: b[j++] })
  }
  return out
}
