import { Bell, Bot, PenLine, RefreshCw, Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router'

import {
  useCurrentScan,
  useSettings,
  useStartScan,
  useTopics,
  useUpdateSettings,
} from '../api/hooks'
import { AI_MODES, type AiMode } from '../api/types'

export function Topbar() {
  const { t } = useTranslation()

  return (
    <header className="flex items-center gap-4 px-8 py-5">
      {/* "Ask" box: wired up in phase 6. */}
      <label className="relative min-w-0 flex-1">
        <span className="sr-only">{t('topbar.askLabel')}</span>
        <Search
          className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted"
          aria-hidden
        />
        <input
          type="search"
          disabled
          title={t('topbar.comingSoon')}
          placeholder={t('topbar.askPlaceholder')}
          className="w-full rounded-full border border-line bg-surface py-2.5 pr-4 pl-11 text-ink shadow-card placeholder:text-muted disabled:cursor-not-allowed"
        />
      </label>

      <ScanNowButton />
      <Link
        to="/generator"
        className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2.5 font-semibold text-ink shadow-card hover:bg-surface-raised"
      >
        <PenLine className="size-4" aria-hidden />
        {t('topbar.newPost')}
      </Link>

      <NotificationBell />
      <AiSelector />
    </header>
  )
}

function ScanNowButton() {
  const { t } = useTranslation()
  const { data: scan } = useCurrentScan()
  const { data: topics } = useTopics()
  const start = useStartScan()
  const navigate = useNavigate()
  const running = scan?.status === 'running'
  const hasActive = topics?.some((topic) => topic.active) ?? false

  return (
    <button
      type="button"
      disabled={running || start.isPending}
      title={hasActive ? undefined : t('topbar.scanNeedsTopics')}
      onClick={() => (hasActive ? start.mutate(undefined) : navigate('/topics'))}
      className="flex items-center gap-2 rounded-full bg-accent-gradient px-4 py-2.5 font-semibold text-on-accent shadow-card disabled:cursor-not-allowed disabled:opacity-60"
    >
      <RefreshCw className={`size-4 ${running ? 'animate-spin' : ''}`} aria-hidden />
      {running ? t('topbar.scanning') : t('topbar.scanNow')}
    </button>
  )
}

function NotificationBell() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={t('topbar.notifications')}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="grid size-11 place-items-center rounded-full border border-line bg-surface text-ink shadow-card hover:bg-surface-raised"
      >
        <Bell className="size-5" aria-hidden />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-card border border-line bg-surface-raised p-4 text-muted shadow-card">
          {t('topbar.noNotifications')}
        </div>
      )}
    </div>
  )
}

function AiSelector() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()

  return (
    <label className="flex items-center gap-2 rounded-full border border-line bg-surface py-1.5 pr-2 pl-3 shadow-card">
      <span className="grid size-8 place-items-center rounded-full bg-accent-gradient text-on-accent">
        <Bot className="size-4" aria-hidden />
      </span>
      <span className="sr-only">{t('topbar.activeAi')}</span>
      <select
        value={settings?.default_ai ?? 'chat'}
        onChange={(event) => update.mutate({ default_ai: event.target.value as AiMode })}
        className="cursor-pointer rounded-full bg-transparent py-1 pr-1 font-semibold text-ink outline-none"
      >
        {AI_MODES.map((mode) => (
          <option key={mode} value={mode} className="bg-surface text-ink">
            {t(`ai.${mode}`)}
          </option>
        ))}
      </select>
    </label>
  )
}
