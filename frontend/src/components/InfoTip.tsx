import { useEffect, useId, useRef, useState } from 'react'
import type { JSX } from 'react'
import { Icon } from './Icon.tsx'

const TIP_W = 256

export function InfoTip({ term, text }: { term: string; text: string }): JSX.Element {
  const id = useId()
  const btn = useRef<HTMLButtonElement>(null)
  const tip = useRef<HTMLSpanElement>(null)
  const [open, setOpen] = useState<boolean>(false)
  const [pos, setPos] = useState<{ left: number; top: number }>({ left: 0, top: 0 })

  useEffect(() => {
    if (!open) return
    const close = (): void => setOpen(false)
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.stopPropagation() // keep Esc from also closing a surrounding dialog
        close()
      }
    }
    window.addEventListener('scroll', close, true)
    document.addEventListener('keydown', onKey, true)
    return () => {
      window.removeEventListener('scroll', close, true)
      document.removeEventListener('keydown', onKey, true)
    }
  }, [open])

  const show = (): void => {
    const r = btn.current?.getBoundingClientRect()
    if (r === undefined) return
    const left = Math.max(8, Math.min(r.left + r.width / 2 - TIP_W / 2, window.innerWidth - TIP_W - 8))
    setPos({ left, top: r.bottom + 6 })
    setOpen(true)
  }

  // Flip above when the tip would run off the bottom (measured after render).
  useEffect(() => {
    const r = btn.current?.getBoundingClientRect()
    const h = tip.current?.offsetHeight
    if (!open || r === undefined || h === undefined) return
    if (r.bottom + 6 + h > window.innerHeight - 8 && r.top - 6 - h >= 8) {
      setPos((p) => ({ ...p, top: r.top - 6 - h }))
    }
  }, [open])

  return (
    <span className="inline-flex" onMouseEnter={show} onMouseLeave={() => setOpen(false)}>
      <button
        ref={btn}
        type="button"
        aria-label={`About ${term}`}
        aria-describedby={open ? id : undefined}
        onFocus={show}
        onBlur={() => setOpen(false)}
        onClick={() => (open ? setOpen(false) : show())}
        className="inline-flex items-center text-ink-3 hover:text-ink"
      >
        <Icon name="info" />
      </button>
      {open && (
        <span
          ref={tip}
          id={id}
          role="tooltip"
          style={{ position: 'fixed', left: pos.left, top: pos.top, width: TIP_W }}
          className="z-50 rounded-md border border-line-strong bg-surface p-2.5 text-left text-xs font-normal leading-snug text-ink-2"
        >
          {text}
        </span>
      )}
    </span>
  )
}
