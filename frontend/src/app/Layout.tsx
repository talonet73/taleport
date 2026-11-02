import { useEffect } from 'react'
import { Outlet } from 'react-router'

import { useServerEvents, useSettings } from '../api/hooks'
import { setLanguage } from '../i18n'
import { useApplyTheme } from '../theme/useApplyTheme'
import { ScanPanel } from './ScanPanel'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

export function Layout() {
  const { data: settings } = useSettings()
  useServerEvents()
  useApplyTheme(settings?.theme)

  const language = settings?.language
  useEffect(() => {
    if (language) setLanguage(language)
  }, [language])

  return (
    <div className="flex h-screen min-w-[1280px] overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto px-8 pt-2 pb-10">
          <Outlet />
        </main>
      </div>
      <ScanPanel />
    </div>
  )
}
