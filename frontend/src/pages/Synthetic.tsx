import { useEffect, useState } from 'react'
import type { JSX } from 'react'
import { ApiError, listSyntheticGallery } from '../api.ts'
import type { SynthGalleryItem } from '../api.ts'

function errorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail
  return fallback
}

interface PairCardProps {
  item: SynthGalleryItem
}

function PairCard({ item }: PairCardProps): JSX.Element {
  const [imgBroken, setImgBroken] = useState<boolean>(false)
  const [maskBroken, setMaskBroken] = useState<boolean>(false)
  useEffect(() => {
    setImgBroken(false)
    setMaskBroken(false)
  }, [item.imageUrl, item.maskUrl])
  return (
    <li className="rounded border border-neutral-300 bg-white px-3 py-2">
      {imgBroken ? (
        <div className="rounded border border-dashed border-neutral-300 px-3 py-8 text-center text-xs text-neutral-500">
          Image file missing under data/.
        </div>
      ) : (
        <img
          src={item.imageUrl}
          alt={`${item.category} ${item.defect} synthetic image`}
          className="block w-full"
          onError={() => setImgBroken(true)}
        />
      )}
      {item.maskUrl === null ? (
        <div className="mt-2 rounded border border-dashed border-neutral-300 px-3 py-4 text-center text-xs text-neutral-500">
          No mask for this pair.
        </div>
      ) : maskBroken ? (
        <div className="mt-2 rounded border border-dashed border-neutral-300 px-3 py-4 text-center text-xs text-neutral-500">
          Mask file missing under data/.
        </div>
      ) : (
        <img
          src={item.maskUrl}
          alt={`${item.category} ${item.defect} defect mask`}
          className="mt-2 block w-full"
          onError={() => setMaskBroken(true)}
        />
      )}
    </li>
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

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
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

  const groups = groupItems(items)

  return (
    <section aria-label="Synthetic">
      <h1 className="text-xl font-semibold">Synthetic</h1>
      <p className="mt-2 text-sm">
        Gallery of generated defect pairs grouped by category and defect type.
      </p>

      {error !== null && (
        <p
          role="alert"
          className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800"
        >
          {error}
        </p>
      )}

      {loading ? (
        <p role="status" className="mt-6 text-sm text-neutral-500">
          Loading gallery…
        </p>
      ) : items.length === 0 ? (
        <div className="mt-6 rounded border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500">
          No synthetic images yet. Generate a pair from the API or CLI, then
          return here to browse the gallery.
        </div>
      ) : (
        <div className="mt-6 space-y-8">
          {groups.map((group) => (
            <div key={group.category}>
              <h2 className="text-sm font-semibold">{group.category}</h2>
              {group.defects.map((defectGroup) => (
                <div key={defectGroup.defect} className="mt-3">
                  <h3 className="text-sm text-neutral-600">
                    {defectGroup.defect} ({defectGroup.items.length})
                  </h3>
                  <ul className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {defectGroup.items.map((item) => (
                      <PairCard key={item.imageUrl} item={item} />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
