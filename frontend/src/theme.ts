export type Theme = 'system' | 'light' | 'dark'

export const THEME_KEY = 'zsqc-theme'

export function resolveTheme(stored: unknown): Theme {
  return stored === 'light' || stored === 'dark' ? stored : 'system'
}

export function readStoredTheme(): Theme {
  try {
    return resolveTheme(localStorage.getItem(THEME_KEY))
  } catch {
    return 'system'
  }
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement
  if (theme === 'system') delete root.dataset.theme
  else root.dataset.theme = theme
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    // storage blocked: theme still applies for this session
  }
}
