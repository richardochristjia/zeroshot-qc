import { useEffect, useRef } from 'react'
import type { JSX, KeyboardEvent, ReactNode } from 'react'
import { Button } from './Button.tsx'

type Props = {
  open: boolean
  title: string
  onClose: () => void
  onKeyDown?: (e: KeyboardEvent<HTMLDialogElement>) => void
  children: ReactNode
}

export function Dialog({ open, title, onClose, onKeyDown, children }: Props): JSX.Element {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const d = ref.current
    if (d === null) return
    if (open && !d.open) d.showModal()
    else if (!open && d.open) d.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-label={title}
      onClose={onClose}
      onKeyDown={onKeyDown}
      onClick={(e) => {
        if (e.target === ref.current) ref.current?.close()
      }}
      className="m-auto max-h-[92vh] w-[min(720px,calc(100vw-32px))] rounded-md border border-line bg-surface p-0 text-ink backdrop:bg-black/50"
    >
      {open && (
        <>
          <div className="flex items-center justify-between gap-3 border-b border-line px-3.5 py-2.5">
            <h2 className="min-w-0 truncate">{title}</h2>
            <Button variant="ghost" onClick={() => ref.current?.close()}>
              Close
            </Button>
          </div>
          {children}
        </>
      )}
    </dialog>
  )
}
