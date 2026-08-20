import { computed, ref } from 'vue'

export type Theme = 'light' | 'dark'

const THEME_STORAGE_KEY = 'theme'
const theme = ref<Theme>('light')
const isDark = computed(() => theme.value === 'dark')

function getStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
  return storedTheme === 'dark' || storedTheme === 'light' ? storedTheme : null
}

function getSystemTheme(): Theme {
  if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

export function setTheme(nextTheme: Theme, persist = true): void {
  theme.value = nextTheme

  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('dark', nextTheme === 'dark')
  }

  if (persist && typeof window !== 'undefined') {
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
  }
}

export function initializeTheme(): Theme {
  const initialTheme = getStoredTheme() ?? getSystemTheme()
  setTheme(initialTheme, false)
  return initialTheme
}

export function toggleTheme(): Theme {
  const nextTheme = isDark.value ? 'light' : 'dark'
  setTheme(nextTheme)
  return nextTheme
}

export function useTheme() {
  return {
    theme,
    isDark,
    setTheme,
    initializeTheme,
    toggleTheme
  }
}
