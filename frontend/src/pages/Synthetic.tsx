import { useEffect, useState } from 'react'
import type { JSX } from 'react'
import { motion } from 'motion/react'
import { ApiError, listSyntheticGallery, resolveFileUrl } from '../api.ts'
import type { SynthGalleryItem } from '../api.ts'
import { Alert } from '../components/Alert.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { Icon } from '../components/Icon.tsx'
import { PageHeader } from '../components/PageHeader.tsx'

function errorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail
  return fallback
}

function PairCard({ item, index, showMask }: { item: SynthGalleryItem; index: number; showMask: boolean }): JSX.Element {
  // Parent keys this card by imageUrl, so the broken flags reset per item.
  const [imgBroken, setImgBroken] = useState<boolean>(false)
  const [maskBroken, setMaskBroken] = useState<boolean>(false)
  const maskNote =
    item.maskUrl === null ? 'No mask for this pair.' : maskBroken ? 'Mask file missing under data/.' : null
  return (
    <motion.li layout transition={{ duration: 0.2, ease: 'easeOut' }} className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="relative aspect-square bg-sunken">
        {imgBroken ? (
          <div className="flex h-full items-center justify-center p-3 text-center text-xs text-ink-3">
            Image file missing under data/.
          </div>
        ) : (
          <img
            src={resolveFileUrl(item.imageUrl)}
            alt={`${item.category} ${item.defect} synthetic image`}
            className="block h-full w-full object-cover"
            onError={() => setImgBroken(true)}
          />
        )}
        {item.maskUrl !== null && !maskBroken && !imgBroken && (
          <img
            src={resolveFileUrl(item.maskUrl)}
            alt={`${item.category} ${item.defect} defect mask`}
            className="absolute inset-0 h-full w-full object-cover mix-blend-screen transition-opacity duration-150"
            style={{ imageRendering: 'pixelated', opacity: showMask ? 0.85 : 0 }}
            onError={() => setMaskBroken(true)}
          />
        )}
      </div>
      <div className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
        <span className="truncate text-ink-2">
          {item.category} / {item.defect}
          {maskNote !== null && <span className="block text-ink-3">{maskNote}</span>}
        </span>
        <span className="num shrink-0 font-mono text-ink-3">#{String(index + 1).padStart(3, '0')}</span>
      </div>
    </motion.li>
  )
}

interface DefectGroup {
  defect: string
  items: SynthGalleryItem[]
}

interface CategoryGroup {
  category: string
  defects: DefectGroup[]
}

function groupItems(items: SynthGalleryItem[]): CategoryGroup[] {
  const byCategory = new Map<string, Map<string, SynthGalleryItem[]>>()
  for (const item of items) {
    let byDefect = byCategory.get(item.category)
    if (byDefect === undefined) {
      byDefect = new Map<string, SynthGalleryItem[]>()
      byCategory.set(item.category, byDefect)
    }
    const list = byDefect.get(item.defect)
    if (list === undefined) {
      byDefect.set(item.defect, [item])
    } else {
      list.push(item)
    }
  }
  return [...byCategory.keys()].sort().map((category) => {
    const byDefect: Map<string, SynthGalleryItem[]> =
      byCategory.get(category) ?? new Map<string, SynthGalleryItem[]>()
    return {
      category,
      defects: [...byDefect.keys()].sort().map((defect) => ({
        defect,
        items: (byDefect.get(defect) ?? []).slice().sort((a, b) =>
          a.imageUrl < b.imageUrl ? -1 : a.imageUrl > b.imageUrl ? 1 : 0,
        ),
      })),
    }
  })
}

export default function Synthetic(): JSX.Element {
  const [items, setItems] = useState<SynthGalleryItem[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('')
  const [showMasks, setShowMasks] = useState<boolean>(false)

  useEffect(() => {
    const controller = new AbortController()
    listSyntheticGallery(controller.signal)
      .then((loaded) => {
        setItems(loaded)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(errorDetail(err, 'Could not load synthetic gallery.'))
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  const chips = groupItems(items).flatMap((group) =>
    group.defects.map((d) => ({ key: `${group.category} / ${d.defect}`, items: d.items })),
  )
  const visible = chips.filter((chip) => filter === '' || chip.key === filter).flatMap((chip) => chip.items)
  const chipClass = (active: boolean): string =>
    `num inline-flex min-h-8 items-center rounded-md border px-3 text-[13px] ${
      active ? 'border-ink bg-ink text-ground' : 'border-line-strong bg-surface text-ink-2 hover:bg-sunken'
    }`

  return (
    <section aria-label="Synthetic">
      <PageHeader title="Synthetic" subtitle="Generated defect images with exact masks, for eval when real defects are scarce.">
        <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" checked={showMasks} onChange={(event) => setShowMasks(event.target.checked)} />
          <Icon name="eye" />
          Show masks
        </label>
      </PageHeader>

      {error !== null && <Alert className="mb-4">{error}</Alert>}

      {loading ? (
        <EmptyState title="Loading gallery…" />
      ) : items.length === 0 ? (
        <EmptyState icon="sparkles" title="No synthetic images yet.">
          Generate a pair from the API or CLI, then return here to browse the gallery.
        </EmptyState>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by category and defect">
            <button type="button" aria-pressed={filter === ''} className={chipClass(filter === '')} onClick={() => setFilter('')}>
              All · {items.length}
            </button>
            {chips.map((chip) => (
              <button
                key={chip.key}
                type="button"
                aria-pressed={filter === chip.key}
                className={chipClass(filter === chip.key)}
                onClick={() => setFilter(chip.key)}
              >
                {chip.key} · {chip.items.length}
              </button>
            ))}
          </div>
          <ul className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
            {visible.map((item, index) => (
              <PairCard key={item.imageUrl} item={item} index={index} showMask={showMasks} />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
