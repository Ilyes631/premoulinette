import { createContext, useContext } from 'react'

export type ThemePreference = 'system' | 'dark' | 'light'
export type ResolvedTheme = 'dark' | 'light'

/** Must match the inline script in index.html. */
export const THEME_STORAGE_KEY = 'premoulinette.theme'

export function readStoredTheme(): ThemePreference {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY)
    return value === 'dark' || value === 'light' || value === 'system' ? value : 'system'
  } catch {
    return 'system'
  }
}

export function storeTheme(theme: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // storage unavailable (private mode): the choice simply is not remembered
  }
}

export function systemPrefersLight(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-color-scheme: light)').matches
    : false
}

/** Dark-first: "system" resolves to dark unless the OS explicitly asks for light. */
export function resolveTheme(pref: ThemePreference, prefersLight = systemPrefersLight()): ResolvedTheme {
  if (pref === 'system') return prefersLight ? 'light' : 'dark'
  return pref
}

export interface ThemeContextValue {
  theme: ThemePreference
  resolvedTheme: ResolvedTheme
  setTheme: (theme: ThemePreference) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}
