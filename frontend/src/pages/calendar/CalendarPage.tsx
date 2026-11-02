import { CheckCircle2, ChevronLeft, ChevronRight, Clock, Lightbulb } from 'lucide-react'
import { type DragEvent, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useDraftAction } from '../../api/hooks'
import { type CalendarEntry, type PostingTime, useCalendar, useMoveDraft } from '../../api/planner'
import { Card } from '../../components/Card'
import { Modal } from '../../components/Modal'
import { useErrorMessage } from '../../components/useErrorMessage'

type View = 'week' | 'month'

const pad = (n: number) => String(n).padStart(2, '0')
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
const mondayOf = (d: Date) => addDays(d, -((d.getDay() + 6) % 7))

function range(view: View, anchor: Date): Date[] {
  if (view === 'week') {
    const start = mondayOf(anchor)
    return Array.from({ length: 7 }, (_, i) => addDays(start, i))
  }
  const start = mondayOf(new Date(anchor.getFullYear(), anchor.getMonth(), 1))
  return Array.from({ length: 42 }, (_, i) => addDays(start, i))
}

export function CalendarPage() {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const [view, setView] = useState<View>('week')
  const [anchor, setAnchor] = useState(() => new Date())
  const [dragOver, setDragOver] = useState<string | null>(null)
  const [selected, setSelected] = useState<CalendarEntry | null>(null)
  const days = useMemo(() => range(view, anchor), [view, anchor])
  const start = isoDay(days[0])
  const end = isoDay(days[days.length - 1])
  const { data, isLoading } = useCalendar(start, end)
  const move = useMoveDraft()
  const today = isoDay(new Date())

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEntry[]>()
    for (const entry of data?.entries ?? []) {
      map.set(entry.day!, [...(map.get(entry.day!) ?? []), entry])
    }
    return map
  }, [data])

  const shift = (direction: number) =>
    setAnchor((a) =>
      view === 'week' ? addDays(a, 7 * direction) : new Date(a.getFullYear(), a.getMonth() + direction, 1),
    )

  const title =
    view === 'week'
      ? new Intl.DateTimeFormat(i18n.language, { day: 'numeric', month: 'short' }).formatRange(days[0], days[6])
      : new Intl.DateTimeFormat(i18n.language, { month: 'long', year: 'numeric' }).format(anchor)

  const onDrop = (event: DragEvent, day: string) => {
    event.preventDefault()
    setDragOver(null)
    const id = Number(event.dataTransfer.getData('text/plain'))
    if (id) move.mutate({ id, day })
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('calendar.title')}</h1>
          <p className="mt-1 text-muted">{t('calendar.subtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label={t('calendar.view')} className="flex rounded-full border border-line bg-surface p-1">
            {(['week', 'month'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold ${
                  view === v ? 'bg-accent-gradient text-on-accent' : 'text-muted hover:text-ink'
                }`}
              >
                {t(`calendar.${v}`)}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => shift(-1)} aria-label={t('calendar.previous')} className="rounded-full border border-line bg-surface p-2 text-ink hover:bg-surface-raised">
            <ChevronLeft className="size-4" aria-hidden />
          </button>
          <button type="button" onClick={() => setAnchor(new Date())} className="rounded-full border border-line bg-surface px-4 py-1.5 text-sm font-semibold text-ink hover:bg-surface-raised">
            {t('calendar.today')}
          </button>
          <button type="button" onClick={() => shift(1)} aria-label={t('calendar.next')} className="rounded-full border border-line bg-surface p-2 text-ink hover:bg-surface-raised">
            <ChevronRight className="size-4" aria-hidden />
          </button>
          <p className="min-w-44 text-right text-lg font-semibold text-ink first-letter:uppercase" aria-live="polite">
            {title}
          </p>
        </div>
      </header>

      {move.isError && <p className="text-sm text-red-400">{errorMessage(move.error)}</p>}

      <div className="grid gap-6 xl:grid-cols-[1fr_18rem]">
        <section aria-label={title} className={isLoading ? 'opacity-60' : ''}>
          <div className="grid grid-cols-7 gap-2">
            {days.slice(0, 7).map((d) => (
              <p key={d.toISOString()} className="px-2 text-sm font-medium text-muted capitalize">
                {new Intl.DateTimeFormat(i18n.language, { weekday: 'short' }).format(d)}
              </p>
            ))}
            {days.map((d) => {
              const day = isoDay(d)
              const entries = byDay.get(day) ?? []
              const outside = view === 'month' && d.getMonth() !== anchor.getMonth()
              return (
                <div
                  key={day}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragOver(day)
                  }}
                  onDragLeave={() => setDragOver((v) => (v === day ? null : v))}
                  onDrop={(e) => onDrop(e, day)}
                  className={`flex flex-col gap-1.5 rounded-card border p-2 transition-colors ${
                    view === 'week' ? 'min-h-80' : 'min-h-28'
                  } ${dragOver === day ? 'border-accent bg-surface-raised' : 'border-line bg-surface'} ${
                    outside ? 'opacity-50' : ''
                  }`}
                >
                  <p
                    className={`text-sm font-semibold ${
                      day === today ? 'w-fit rounded-full bg-accent-gradient px-2 text-on-accent' : 'text-ink'
                    }`}
                  >
                    {view === 'week'
                      ? new Intl.DateTimeFormat(i18n.language, { day: 'numeric', month: 'short' }).format(d)
                      : d.getDate()}
                  </p>
                  {entries.map((entry) => (
                    <EntryChip key={`${entry.status}-${entry.id}`} entry={entry} compact={view === 'month'} onOpen={() => setSelected(entry)} />
                  ))}
                </div>
              )
            })}
          </div>
          <p className="mt-3 text-sm text-muted">{t('calendar.dragHint')}</p>
        </section>

        <aside className="space-y-6">
          <Card title={t('calendar.unscheduled')}>
            {data && data.unscheduled.length === 0 ? (
              <p className="text-sm text-muted">
                {t('calendar.noUnscheduled')}{' '}
                <Link to="/generator" className="text-accent-text hover:underline">
                  {t('calendar.goGenerator')}
                </Link>
              </p>
            ) : (
              <ul className="max-h-[28rem] space-y-1.5 overflow-y-auto">
                {data?.unscheduled.map((entry) => (
                  <li key={entry.id}>
                    <EntryChip entry={entry} onOpen={() => setSelected(entry)} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {data && <PostingTimes times={data.posting_times} />}
        </aside>
      </div>

      {selected && <MoveDialog entry={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

function EntryChip({ entry, compact, onOpen }: { entry: CalendarEntry; compact?: boolean; onOpen: () => void }) {
  const { t } = useTranslation()
  const published = entry.status === 'published'
  return (
    <button
      type="button"
      draggable={!published}
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', String(entry.id))
        e.dataTransfer.effectAllowed = 'move'
      }}
      onClick={onOpen}
      aria-label={`${t(`platforms.${entry.platform}`)} · ${entry.label}${entry.time ? ` · ${entry.time}` : ''}${
        published ? ` · ${t('calendar.published')}` : ''
      }`}
      className={`w-full rounded-xl border px-2 py-1.5 text-left text-xs ${
        published ? 'border-line bg-surface-raised/60' : 'cursor-grab border-line bg-surface-raised hover:border-accent'
      }`}
    >
      {entry.time && (
        <span className="flex items-center gap-1 font-semibold text-ink">
          {published ? (
            <CheckCircle2 className="size-3.5 shrink-0 text-accent-text" aria-hidden />
          ) : (
            <Clock className="size-3.5 shrink-0 text-muted" aria-hidden />
          )}
          {entry.time}
        </span>
      )}
      <span className="block truncate font-semibold text-accent-text">{t(`platforms.${entry.platform}`)}</span>
      {!compact && <span className="mt-0.5 line-clamp-2 block text-ink">{entry.label || entry.preview}</span>}
    </button>
  )
}

function MoveDialog({ entry, onClose }: { entry: CalendarEntry; onClose: () => void }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const move = useMoveDraft()
  const action = useDraftAction()
  const [day, setDay] = useState(entry.day ?? isoDay(new Date()))
  const [time, setTime] = useState(entry.time ?? '')
  const published = entry.status === 'published'

  return (
    <Modal title={`${t(`platforms.${entry.platform}`)} · ${entry.label}`} onClose={onClose}>
      <p className="mb-4 max-w-prose text-[15px] whitespace-pre-wrap text-ink">{entry.preview}…</p>
      {published ? (
        <p className="text-muted">{t('calendar.publishedNote')}</p>
      ) : (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            move.mutate({ id: entry.id, day, time: time || undefined }, { onSuccess: onClose })
          }}
        >
          <label className="text-sm text-muted">
            {t('calendar.day')}
            <input type="date" aria-label={t('calendar.day')} value={day} onChange={(e) => setDay(e.target.value)} required className="mt-1 block rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-ink" />
          </label>
          <label className="text-sm text-muted">
            {t('calendar.time')}
            <input type="time" aria-label={t('calendar.time')} value={time} onChange={(e) => setTime(e.target.value)} className="mt-1 block rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-ink" />
          </label>
          <button type="submit" className="rounded-xl bg-accent-gradient px-4 py-1.5 font-semibold text-on-accent">
            {t('common.save')}
          </button>
          {entry.status === 'scheduled' && (
            <button
              type="button"
              onClick={() =>
                action.mutate(
                  { path: `/drafts/${entry.id}/schedule`, method: 'PUT', body: { scheduled_at: null } },
                  { onSuccess: onClose },
                )
              }
              className="rounded-xl border border-line px-4 py-1.5 text-ink hover:bg-surface-raised"
            >
              {t('drafts.unschedule')}
            </button>
          )}
          <p className="basis-full text-xs text-muted">{t('calendar.timeHint')}</p>
        </form>
      )}
      {(move.isError || action.isError) && (
        <p className="mt-2 text-sm text-red-400">{errorMessage(move.error ?? action.error)}</p>
      )}
    </Modal>
  )
}

function PostingTimes({ times }: { times: PostingTime[] }) {
  const { t } = useTranslation()
  return (
    <Card title={t('calendar.postingTimes')}>
      <ul className="space-y-2 text-sm">
        {times.map((pt) => (
          <li key={pt.platform}>
            <p className="flex justify-between gap-2">
              <span className="text-ink">{t(`platforms.${pt.platform}`)}</span>
              <span className="font-semibold text-ink">{pt.time}</span>
            </p>
            {pt.learned && pt.learned.time !== pt.time && (
              <p className="mt-0.5 flex items-start gap-1 text-xs text-muted">
                <Lightbulb className="mt-0.5 size-3 shrink-0 text-accent-text" aria-hidden />
                {t('calendar.learned', { time: pt.learned.time, posts: pt.learned.posts, average: pt.learned.average })}
              </p>
            )}
          </li>
        ))}
      </ul>
      <Link to="/settings#posting-times" className="mt-3 inline-block text-sm text-accent-text hover:underline">
        {t('calendar.editTimes')}
      </Link>
    </Card>
  )
}
