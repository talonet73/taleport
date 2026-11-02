import { BarChart3, ClipboardCopy, ExternalLink, Lightbulb, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import { copyToClipboard, openExternal, useTopics } from '../../api/hooks'
import {
  type ArchiveFilters,
  type ArchivePost,
  useArchivePosts,
  useArchiveThemes,
  useResultsSummary,
} from '../../api/planner'
import { PLATFORMS } from '../../api/types'
import { Card } from '../../components/Card'
import { PriorityNote } from '../../components/results/PriorityNote'
import { ResultsForm, ResultsLine } from '../../components/results/ResultsForm'
import { TrendBadge } from '../../components/TrendBadge'
import { useErrorMessage } from '../../components/useErrorMessage'

const field = 'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'
const PAGE = 20

type Tab = 'posts' | 'themes'

/** Debounced copy of a value (the search box queries while typing). */
function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(timer)
  }, [value, ms])
  return debounced
}

export function ArchivePage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'themes' ? 'themes' : 'posts'
  const { data: topics = [] } = useTopics()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [filters, setFilters] = useState<ArchiveFilters>({})
  const [limit, setLimit] = useState(PAGE)
  const search = useDebounced(q)

  useEffect(() => setLimit(PAGE), [search, filters, tab])

  const set = (key: string, value: string) => setFilters((f) => ({ ...f, [key]: value || undefined }))
  const query = { ...filters, q: search || undefined, limit }

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">{t('nav.archive')}</h1>
        <p className="mt-1 max-w-prose text-muted">{t('archive.subtitle')}</p>
      </div>

      <div role="tablist" aria-label={t('nav.archive')} className="flex gap-1">
        {(['posts', 'themes'] as const).map((key) => (
          <button
            key={key}
            role="tab"
            type="button"
            aria-selected={tab === key}
            onClick={() => setParams(key === 'posts' ? {} : { tab: key })}
            className={`rounded-full px-4 py-2 font-semibold ${
              tab === key ? 'bg-accent-gradient text-on-accent' : 'border border-line text-ink hover:bg-surface-raised'
            }`}
          >
            {t(`archive.tabs.${key}`)}
          </button>
        ))}
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <label className="min-w-64 flex-1 text-sm font-medium text-ink">
            {t('archive.search')}
            <span className="relative mt-1.5 block">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
              <input
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t(`archive.searchPlaceholder.${tab}`)}
                aria-label={t('archive.search')}
                className={`${field} w-full pl-9`}
              />
            </span>
          </label>
          {tab === 'posts' && (
            <>
              <label className="text-sm font-medium text-ink">
                {t('archive.status')}
                <select aria-label={t('archive.status')} value={filters.status ?? ''} onChange={(e) => set('status', e.target.value)} className={`${field} mt-1.5 block`}>
                  <option value="">{t('archive.all')}</option>
                  {(['draft', 'scheduled', 'published'] as const).map((s) => (
                    <option key={s} value={s}>
                      {t(`archive.statuses.${s}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-ink">
                {t('archive.platform')}
                <select aria-label={t('archive.platform')} value={filters.platform ?? ''} onChange={(e) => set('platform', e.target.value)} className={`${field} mt-1.5 block`}>
                  <option value="">{t('archive.all')}</option>
                  {PLATFORMS.map((p) => (
                    <option key={p} value={p}>
                      {t(`platforms.${p}`)}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          {topics.length > 1 && (
            <label className="text-sm font-medium text-ink">
              {t('archive.topic')}
              <select aria-label={t('archive.topic')} value={filters.topic_id ?? ''} onChange={(e) => set('topic_id', e.target.value)} className={`${field} mt-1.5 block`}>
                <option value="">{t('archive.all')}</option>
                {topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="text-sm font-medium text-ink">
            {t('archive.from')}
            <input type="date" aria-label={t('archive.from')} value={filters.start ?? ''} onChange={(e) => set('start', e.target.value)} className={`${field} mt-1.5 block`} />
          </label>
          <label className="text-sm font-medium text-ink">
            {t('archive.to')}
            <input type="date" aria-label={t('archive.to')} value={filters.end ?? ''} onChange={(e) => set('end', e.target.value)} className={`${field} mt-1.5 block`} />
          </label>
        </div>
      </Card>

      {tab === 'posts' ? (
        <>
          <ResultsSummaryCard />
          <PostsList query={query} onMore={() => setLimit((l) => l + PAGE)} />
        </>
      ) : (
        <ThemesList query={query} onMore={() => setLimit((l) => l + PAGE)} />
      )}
    </div>
  )
}

function ResultsSummaryCard() {
  const { t, i18n } = useTranslation()
  const { data } = useResultsSummary()
  if (!data || data.posts === 0) return null
  const fmt = (n: number | null) =>
    n === null ? '–' : new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 }).format(n)
  return (
    <Card title={t('results.summaryTitle')} description={t('results.summaryText', { count: data.posts })}>
      {data.reasons.map((reason, i) => (
        <PriorityNote key={i} reason={reason} className="mb-4" />
      ))}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="py-1 pr-3 font-medium">{t('archive.platform')}</th>
              <th className="py-1 pr-3 text-right font-medium">{t('results.posts')}</th>
              {(['likes', 'comments', 'shares', 'views', 'interactions'] as const).map((m) => (
                <th key={m} className="py-1 pr-3 text-right font-medium">
                  {t(`results.avg.${m}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.platforms.map((row) => (
              <tr key={row.platform} className="border-t border-line text-ink">
                <td className="py-1.5 pr-3">{t(`platforms.${row.platform}`)}</td>
                <td className="py-1.5 pr-3 text-right">{row.posts}</td>
                {(['likes', 'comments', 'shares', 'views', 'interactions'] as const).map((m) => (
                  <td key={m} className={`py-1.5 pr-3 text-right ${m === 'interactions' ? 'font-semibold' : ''}`}>
                    {fmt(row[m])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function PostsList({ query, onMore }: { query: ArchiveFilters; onMore: () => void }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data, error, isFetching } = useArchivePosts(query)
  if (error) return <p className="text-red-400">{errorMessage(error)}</p>
  if (!data) return <p className="text-muted">{t('common.loading')}</p>
  return (
    <section aria-live="polite" className={isFetching ? 'opacity-70' : ''}>
      <p className="mb-3 text-sm text-muted">{t('archive.postsFound', { count: data.total })}</p>
      {data.rows.length === 0 ? (
        <Card>
          <p className="text-muted">{t('archive.noPosts')}</p>
        </Card>
      ) : (
        <ul className="space-y-3">
          {data.rows.map((post) => (
            <li key={post.id}>
              <PostRow post={post} />
            </li>
          ))}
        </ul>
      )}
      {data.rows.length < data.total && (
        <button type="button" onClick={onMore} className="mt-4 rounded-full border border-line px-5 py-2 font-semibold text-ink hover:bg-surface-raised">
          {t('archive.more')}
        </button>
      )}
    </section>
  )
}

function PostRow({ post }: { post: ArchivePost }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [copied, setCopied] = useState(false)
  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
  const date =
    post.status === 'published' && post.publication
      ? t('drafts.status.published', { date: fmt(post.publication.published_at) })
      : post.status === 'scheduled' && post.scheduled_at
        ? t('drafts.status.scheduled', { date: fmt(post.scheduled_at) })
        : t('archive.createdOn', { date: fmt(post.created_at) })

  return (
    <article className="rounded-card border border-line bg-surface p-5 shadow-card">
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-accent-gradient px-3 py-0.5 text-sm font-semibold text-on-accent">
          {t(`platforms.${post.platform}`)}
        </span>
        <span className="rounded-full bg-surface-raised px-2.5 py-0.5 text-sm text-ink">{t(`languages.${post.language}`)}</span>
        <span className="text-sm text-muted">
          {post.source_label}
          {post.topic_name ? ` · ${post.topic_name}` : ''}
        </span>
        <span className="ml-auto text-sm font-medium text-accent-text">{date}</span>
      </header>
      <p className={`max-w-prose text-[15px] leading-relaxed whitespace-pre-wrap text-ink ${open ? '' : 'line-clamp-3'}`}>
        {post.text}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="text-sm text-accent-text hover:underline">
          {open ? t('archive.less') : t('archive.readAll')}
        </button>
        <button
          type="button"
          onClick={() => copyToClipboard(post.text).then((r) => r.copied && setCopied(true))}
          className="flex items-center gap-1 rounded-xl border border-line px-3 py-1 text-sm text-ink hover:bg-surface-raised"
        >
          <ClipboardCopy className="size-3.5" aria-hidden />
          {copied ? t('drafts.copied') : t('drafts.copy')}
        </button>
        {post.publication?.url && (
          <button
            type="button"
            onClick={() => openExternal(post.publication!.url!)}
            className="flex items-center gap-1 rounded-xl border border-line px-3 py-1 text-sm text-ink hover:bg-surface-raised"
          >
            <ExternalLink className="size-3.5" aria-hidden />
            {t('archive.openPost')}
          </button>
        )}
        {post.status === 'published' && (
          <button
            type="button"
            onClick={() => setEditing((v) => !v)}
            className="flex items-center gap-1 rounded-xl border border-line px-3 py-1 text-sm text-ink hover:bg-surface-raised"
          >
            <BarChart3 className="size-3.5" aria-hidden />
            {post.results ? t('results.edit') : t('results.enter')}
          </button>
        )}
      </div>
      {post.status === 'published' && !editing && (
        <div className="mt-3">
          {post.results ? <ResultsLine results={post.results} /> : <p className="text-sm text-muted">{t('results.missing')}</p>}
        </div>
      )}
      {editing && (
        <div className="mt-3 border-t border-line pt-3">
          <ResultsForm draftId={post.id} initial={post.results} onDone={() => setEditing(false)} />
        </div>
      )}
    </article>
  )
}

function ThemesList({ query, onMore }: { query: ArchiveFilters; onMore: () => void }) {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data, error, isFetching } = useArchiveThemes(query)
  if (error) return <p className="text-red-400">{errorMessage(error)}</p>
  if (!data) return <p className="text-muted">{t('common.loading')}</p>
  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium' }).format(new Date(`${iso}T12:00:00`))
  return (
    <section aria-live="polite" className={isFetching ? 'opacity-70' : ''}>
      <p className="mb-3 text-sm text-muted">{t('archive.themesFound', { count: data.total })}</p>
      {data.rows.length === 0 ? (
        <Card>
          <p className="text-muted">{t('archive.noThemes')}</p>
        </Card>
      ) : (
        <ul className="space-y-3">
          {data.rows.map((theme) => (
            <li key={theme.id} className="rounded-card border border-line bg-surface p-5 shadow-card">
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                <span>{fmt(theme.day)}</span>
                <span>· {theme.topic_name}</span>
                <TrendBadge trend={theme.trend} />
                <span className="ml-auto font-semibold text-ink">{t('archive.score', { score: theme.score })}</span>
              </div>
              <Link to={`/themes/${theme.id}`} className="mt-1 block text-lg font-semibold text-ink hover:underline">
                {theme.title}
              </Link>
              {theme.summary && <p className="mt-1 max-w-prose text-muted">{theme.summary}</p>}
              <p className="mt-2 flex items-center gap-1 text-sm text-muted">
                <Lightbulb className="size-3.5 text-accent-text" aria-hidden />
                {t('archive.themeCounts', { items: theme.item_count, drafts: theme.drafts, published: theme.published })}
              </p>
            </li>
          ))}
        </ul>
      )}
      {data.rows.length < data.total && (
        <button type="button" onClick={onMore} className="mt-4 rounded-full border border-line px-5 py-2 font-semibold text-ink hover:bg-surface-raised">
          {t('archive.more')}
        </button>
      )}
    </section>
  )
}
