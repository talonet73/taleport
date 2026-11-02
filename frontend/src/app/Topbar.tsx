import { Bell, Bot, CircleHelp, PenLine, RefreshCw, Search } from 'lucide-react'
import type { TFunction } from 'i18next'
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
import { useAskPresets } from '../api/insights'
import {
  type AppNotification,
  useClearNotifications,
  useMarkNotificationsRead,
  useNotifications,
} from '../api/planner'
import { AI_MODES, type AiMode } from '../api/types'

export function Topbar() {
  const { t } = useTranslation()

  return (
    <header className="flex items-center gap-4 px-8 py-5">
      <AskBox />
      <ScanNowButton />
      <Link
        to="/generator"
        className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2.5 font-semibold text-ink shadow-card hover:bg-surface-raised"
      >
        <PenLine className="size-4" aria-hidden />
        {t('topbar.newPost')}
      </Link>

      <Link
        to="/guide"
        aria-label={t('guide.title')}
        title={t('guide.title')}
        className="grid size-11 place-items-center rounded-full border border-line bg-surface text-ink shadow-card hover:bg-surface-raised"
      >
        <CircleHelp className="size-5" aria-hidden />
      </Link>
      <NotificationBell />
      <AiSelector />
    </header>
  )
}

/** "Ask" box: free questions go to the AI as a plan; ready-made ones run instantly. */
function AskBox() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { data: presets = [] } = useAskPresets()
  const [value, setValue] = useState('')
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLFormElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <form
      ref={ref}
      role="search"
      className="relative min-w-0 flex-1"
      onSubmit={(e) => {
        e.preventDefault()
        if (!value.trim()) return
        setOpen(false)
        navigate(`/ask?q=${encodeURIComponent(value.trim())}`)
      }}
    >
      <label>
        <span className="sr-only">{t('topbar.askLabel')}</span>
        <Search className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted" aria-hidden />
        <input
          type="search"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          // Opened by the user (click or arrow key), not by focus coming back from a dialog.
          onClick={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false)
            if (e.key === 'ArrowDown') setOpen(true)
          }}
          placeholder={t('topbar.askPlaceholder')}
          className="w-full rounded-full border border-line bg-surface py-2.5 pr-4 pl-11 text-ink shadow-card placeholder:text-muted"
        />
      </label>
      {open && presets.length > 0 && (
        <div className="absolute inset-x-0 z-30 mt-2 rounded-card border border-line bg-surface-raised p-2 shadow-card">
          <p className="px-2 py-1 text-xs font-medium text-muted">{t('ask.ready')}</p>
          {presets.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                setOpen(false)
                navigate(`/ask?preset=${id}`)
              }}
              className="block w-full rounded-lg px-2 py-1.5 text-left text-ink hover:bg-surface"
            >
              {t(`ask.presets.${id}`)}
            </button>
          ))}
        </div>
      )}
    </form>
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
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const { data } = useNotifications()
  const markRead = useMarkNotificationsRead()
  const clear = useClearNotifications()
  const unread = data?.unread ?? 0
  const rows = data?.rows ?? []

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const when = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso))

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={unread ? t('notifications.unreadLabel', { count: unread }) : t('topbar.notifications')}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="relative grid size-11 place-items-center rounded-full border border-line bg-surface text-ink shadow-card hover:bg-surface-raised"
      >
        <Bell className="size-5" aria-hidden />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 grid min-w-5 place-items-center rounded-full bg-accent-gradient px-1 text-xs font-bold text-on-accent">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-96 rounded-card border border-line bg-surface-raised shadow-card">
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
            <p className="font-semibold text-ink">{t('topbar.notifications')}</p>
            <div className="flex gap-3 text-sm">
              {unread > 0 && (
                <button type="button" onClick={() => markRead.mutate(undefined)} className="text-accent-text hover:underline">
                  {t('notifications.markAllRead')}
                </button>
              )}
              {rows.some((r) => r.read) && (
                <button type="button" onClick={() => clear.mutate()} className="text-muted hover:text-ink">
                  {t('notifications.clearRead')}
                </button>
              )}
            </div>
          </div>
          {rows.length === 0 ? (
            <p className="p-4 text-muted">{t('topbar.noNotifications')}</p>
          ) : (
            <ul className="max-h-96 divide-y divide-line overflow-y-auto">
              {rows.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => {
                      if (!n.read) markRead.mutate([n.id])
                      if (n.link) {
                        setOpen(false)
                        navigate(n.link)
                      }
                    }}
                    className="flex w-full gap-3 px-4 py-3 text-left hover:bg-surface"
                  >
                    <span
                      aria-hidden
                      className={`mt-1.5 size-2 shrink-0 rounded-full ${n.read ? 'bg-transparent' : 'bg-accent'}`}
                    />
                    <span className="min-w-0 flex-1">
                      <span className={`block text-ink ${n.read ? '' : 'font-semibold'}`}>
                        {t(`notifications.kinds.${n.kind}.title`, n.params)}
                      </span>
                      <span className="block text-sm text-muted">{notificationBody(n, t)}</span>
                      <span className="mt-0.5 block text-xs text-muted">{when(n.created_at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

function notificationBody(n: AppNotification, t: TFunction): string {
  const params: Record<string, string | number> = { ...n.params }
  if (n.kind === 'source_failing') {
    params.source = t(`sources.${n.params.source}`)
    params.reason = t(`errors.${n.params.code}`, { defaultValue: '' })
  }
  return t(`notifications.kinds.${n.kind}.body`, params)
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
