import type { ReactNode } from 'react'
import { Icon } from './Icon.tsx'

type Props = { kind?: 'error' | 'notice'; children: ReactNode; className?: string }

export function Alert({ kind = 'error', children, className = '' }: Props) {
  const isError = kind === 'error'
  return (
    <div
      role={isError ? 'alert' : 'status'}
      className={`flex items-start gap-2 rounded-md px-3 py-2 text-sm ${isError ? 'bg-fail-tint text-fail' : 'bg-sunken text-ink-2'} ${className}`}
    >
      <Icon name={isError ? 'alert' : 'check'} className="mt-0.5" />
      <div>{children}</div>
    </div>
  )
}
