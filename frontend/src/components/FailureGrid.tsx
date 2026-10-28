import { useState } from 'react'
import type { JSX } from 'react'
import { resolveFileUrl } from '../api.ts'
import type { EvalResultRow } from '../api.ts'
import { failureKind } from '../eval-view.ts'
import type { FailureKind } from '../eval-view.ts'
import { Icon } from './Icon.tsx'

const chipClass = (active: boolean): string =>
  `num inline-flex min-h-8 items-center rounded-md border px-3 text-[13px] ${
    active ? 'border-ink bg-ink text-ground' : 'border-line-strong bg-surface text-ink-2 hover:bg-sunken'
  }`

function Thumb({ row }: { row: EvalResultRow }): JSX.Element {
  const [broken, setBroken] = useState<boolean>(false)
  if (row.imageUrl === null || broken) {
    return (
      <div className="flex aspect-square w-full items-center justify-center bg-sunken text-ink-3">
        <Icon name="file" className="size-6" />
      </div>
    )
  }
  // shortcut: full-size images as thumbnails, add a backend thumbnail endpoint if served over a slow network
  return (
    <img
      src={resolveFileUrl(row.imageUrl)}
      alt=""
      loading="lazy"
      decoding="async"
      className="aspect-square w-full object-cover"
      onError={() => setBroken(true)}
    />
  )
}

function Card({ row, onOpen }: { row: EvalResultRow; onOpen: () => void }): JSX.Element {
  const missed = failureKind(row) === 'missed'
  const name = row.image.startsWith(`${row.category}/`) ? row.image.slice(row.category.length + 1) : row.image
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="block w-full overflow-hidden rounded-md border border-line bg-surface text-left hover:border-line-strong"
      >
        <Thumb row={row} />
        <div className="flex flex-col gap-1 p-2">
          <span
            className={`inline-flex w-fit items-center gap-1 rounded-sm px-1.5 py-0.5 text-xs font-medium ${
              missed ? 'bg-sunken text-detect' : 'bg-fail-tint text-fail'
            }`}
          >
            <Icon name={missed ? 'alert' : 'x'} className="size-3.5" />
            {missed ? 'Missed' : 'False fail'}
          </span>
          <span className="truncate font-mono text-xs text-ink-2" title={name}>{name}</span>
          <span className="num text-xs text-ink-3">{(row.confidence * 100).toFixed(0)}%</span>
        </div>
      </button>
    </li>
  )
}

interface Props {
  /** All failure rows of the run, before filtering. */
  rows: EvalResultRow[]
  kind: FailureKind | ''
  category: string
  onKind: (kind: FailureKind | '') => void
  onCategory: (category: string) => void
  /** Filtered rows in display order (same list the dialog steps through). */
  filtered: EvalResultRow[]
  onOpen: (index: number) => void
}

export function FailureGrid({ rows, kind, category, onKind, onCategory, filtered, onOpen }: Props): JSX.Element {
  const count = (k: FailureKind): number => rows.filter((r) => failureKind(r) === k).length
  const categories = [...new Set(rows.map((r) => r.category))].sort()
  const shown = categories.filter((c) => filtered.some((r) => r.category === c))
  return (
    <div className="flex flex-col gap-4 p-3.5">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter failures">
        <button type="button" aria-pressed={kind === ''} className={chipClass(kind === '')} onClick={() => onKind('')}>
          All · {rows.length}
        </button>
        <button type="button" aria-pressed={kind === 'false-fail'} className={chipClass(kind === 'false-fail')} onClick={() => onKind('false-fail')}>
          False fail · {count('false-fail')}
        </button>
        <button type="button" aria-pressed={kind === 'missed'} className={chipClass(kind === 'missed')} onClick={() => onKind('missed')}>
          Missed · {count('missed')}
        </button>
        <span className="mx-1 w-px self-stretch bg-line" aria-hidden="true" />
        {categories.map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={category === c}
            className={chipClass(category === c)}
            onClick={() => onCategory(category === c ? '' : c)}
          >
            {c} · {rows.filter((r) => r.category === c).length}
          </button>
        ))}
      </div>
      {filtered.length === 0 && <p className="text-[13px] text-ink-3">No failures match these filters.</p>}
      {shown.map((c) => (
        <div key={c}>
          <h3 className="mb-2 text-xs font-medium text-ink-3">{c}</h3>
          <ul className="grid grid-cols-2 gap-3 min-[641px]:grid-cols-4 min-[1001px]:grid-cols-6">
            {filtered.map((row, index) =>
              row.category === c ? <Card key={`${row.image}-${index}`} row={row} onOpen={() => onOpen(index)} /> : null,
            )}
          </ul>
        </div>
      ))}
    </div>
  )
}
