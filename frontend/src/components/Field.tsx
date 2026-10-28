import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react'

type Props = { label: ReactNode; hint?: ReactNode; error?: ReactNode; children: ReactElement<Record<string, unknown>> }

/** Label + hint + control + error. Wires id and aria-describedby into the single child control. */
export function Field({ label, hint, error, children }: Props) {
  const id = useId()
  const describedBy = [hint ? `${id}-hint` : '', error ? `${id}-err` : ''].filter(Boolean).join(' ') || undefined
  const control = isValidElement(children)
    ? cloneElement(children, { id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })
    : children
  return (
    <div className="flex flex-col gap-1 text-[13px] font-medium text-ink-2">
      <label htmlFor={id}>{label}</label>
      {control}
      {hint && (
        <span id={`${id}-hint`} className="text-xs font-normal text-ink-3">
          {hint}
        </span>
      )}
      {error && (
        <span id={`${id}-err`} className="text-xs font-normal text-fail">
          {error}
        </span>
      )}
    </div>
  )
}
