import type { ReactNode } from 'react'

/** The only h1 on a page. */
export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end gap-4">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="mt-0.5 text-[13px] text-ink-2">{subtitle}</p>}
      </div>
      {children && <div className="ml-auto">{children}</div>}
    </div>
  )
}
