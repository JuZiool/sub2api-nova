import { beforeEach, describe, expect, it } from 'vitest'
import { initializeTheme, setTheme, toggleTheme, useTheme } from '@/utils/theme'

describe('theme utility', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
    setTheme('light', false)
  })

  it('restores a saved dark theme', () => {
    localStorage.setItem('theme', 'dark')

    expect(initializeTheme()).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(useTheme().isDark.value).toBe(true)
  })

  it('uses the system preference when no theme is saved', () => {
    const originalMatchMedia = window.matchMedia
    window.matchMedia = (() => ({ matches: true })) as typeof window.matchMedia

    expect(initializeTheme()).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    window.matchMedia = originalMatchMedia
  })

  it('toggles and persists the global theme', () => {
    setTheme('light')

    expect(toggleTheme()).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    expect(toggleTheme()).toBe('light')
    expect(localStorage.getItem('theme')).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
