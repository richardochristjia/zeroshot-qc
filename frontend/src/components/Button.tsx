import type { ButtonHTMLAttributes } from 'react'
import { Icon, type IconName } from './Icon.tsx'

type Variant = 'primary' | 'secondary' | 'ghost'

const variants: Record<Variant, string> = {
  primary: 'bg-accent border-accent text-on-accent hover:brightness-110',
  secondary: 'bg-surface border-line-strong text-ink hover:bg-sunken',
  ghost: 'bg-transparent border-transparent text-ink-2 hover:bg-sunken hover:text-ink',
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; icon?: IconName }

export function Button({ variant = 'secondary', icon, className = '', type = 'button', children, ...rest }: Props) {
  return (
    <button
      type={type}
      className={`btn inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border px-3.5 text-sm font-medium transition-colors disabled:opacity-45 ${variants[variant]} ${className}`}
      {...rest}
    >
      {icon && <Icon name={icon} />}
      {children}
    </button>
  )
}
