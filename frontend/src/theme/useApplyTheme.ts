import { useEffect } from 'react'

import type { ThemeSetting } from '../api/types'

const STORAGE_KEY = 'taleport.theme' // read by the inline script in index.html

export function useApplyTheme(setting: ThemeSetting | undefined): void {
  useEffect(() => {
    if (!setting) return
    try {
      localStorage.setItem(STORAGE_KEY, setting)
    } catch {
      // storage unavailable: the theme still applies for this session
    }
    const prefersLight = window.matchMedia('(prefers-color-scheme: light)')
    const apply = () => {
      const resolved = setting === 'system' ? (prefersLight.matches ? 'light' : 'dark') : setting
      document.documentElement.dataset.theme = resolved
    }
    apply()
    if (setting !== 'system') return
    prefersLight.addEventListener('change', apply)
    return () => prefersLight.removeEventListener('change', apply)
  }, [setting])
}
