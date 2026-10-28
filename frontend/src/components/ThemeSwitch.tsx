import { useState } from 'react'
import { applyTheme, readStoredTheme, type Theme } from '../theme.ts'
import { Icon, type IconName } from './Icon.tsx'

const options: { value: Theme; label: string; icon: IconName }[] = [
  { value: 'system', label: 'System', icon: 'monitor' },
  { value: 'light', label: 'Light', icon: 'sun' },
  { value: 'dark', label: 'Dark', icon: 'moon' },
]

export function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(readStoredTheme)
  return (
    <div role="group" aria-label="Theme" className="flex overflow-hidden rounded-md border border-line-strong">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={theme === o.value}
          aria-label={o.label}
          onClick={() => {
            setTheme(o.value)
            applyTheme(o.value)
          }}
          className={`inline-flex min-h-7 items-center gap-1.5 px-2.5 text-xs max-[1000px]:min-h-9 ${theme === o.value ? 'bg-sunken font-medium text-ink' : 'text-ink-2 hover:text-ink'}`}
        >
          <Icon name={o.icon} />
          <span className="max-[1000px]:hidden">{o.label}</span>
        </button>
      ))}
    </div>
  )
}
