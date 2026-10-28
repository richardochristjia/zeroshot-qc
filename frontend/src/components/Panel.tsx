import type { HTMLAttributes, ReactNode } from 'react'

export function Panel({ className = '', ...rest }: HTMLAttributes<HTMLElement>) {
  return <section className={`rounded-md border border-line bg-surface ${className}`} {...rest} />
}

export function PanelHeader({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-3.5 py-2.5">
      <h2 className="inline-flex items-center gap-1.5">{title}</h2>
      {children}
    </div>
  )
}
