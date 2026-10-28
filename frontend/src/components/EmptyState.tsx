import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon.tsx'

type Props = { icon?: IconName; title: string; children?: ReactNode; action?: ReactNode; className?: string }

export function EmptyState({ icon, title, children, action, className = '' }: Props) {
  return (
    <div className={`flex flex-col items-center gap-2 rounded-md border border-dashed border-line-strong p-7 text-center text-sm text-ink-2 ${className}`}>
      {icon && <Icon name={icon} className="!h-8 !w-8 text-ink-3" />}
      <p className="font-medium text-ink">{title}</p>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}
