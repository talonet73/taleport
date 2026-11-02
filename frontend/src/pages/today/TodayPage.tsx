import { FileText, Flame, Newspaper, RefreshCw, Send, Sparkles, Tags } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { ThemeInsightsDialog } from '../../components/ai/ThemeInsightsDialog'
import { XSearchDialog } from '../../components/ai/XSearchDialog'

import { openExternal, useCurrentScan, useStartScan, useToday, useTopics } from '../../api/hooks'
import type { ThemeSummary } from '../../api/types'
import { Card } from '../../components/Card'
import { ScoreRing } from '../../components/ScoreRing'
import { TrendBadge } from '../../components/TrendBadge'

export function TodayPage() {
  const { t, i18n } = useTranslation()
  const { data: today } = useToday()
  const { data: topics } = useTopics()
  const dateLabel = new Intl.DateTimeFormat(i18n.language, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date())

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">{t('nav.today')}</h1>
        <p className="mt-1 text-muted first-letter:uppercase">{dateLabel}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile icon={<Newspaper />} label={t('today.stats.items')} value={today?.stats.items_today} />
        <StatTile icon={<Flame />} label={t('today.stats.themes')} value={today?.stats.themes_today} />
        <StatTile icon={<FileText />} label={t('today.stats.generated')} value={today?.stats.posts_generated} />
        <StatTile icon={<Send />} label={t('today.stats.published')} value={today?.stats.posts_published_week} />
      </div>

      {topics && topics.length === 0 && (
        <Card className="flex items-center gap-5">
          <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-accent-gradient text-on-accent">
            <Tags className="size-7" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-lg font-semibold text-ink">{t('today.noTopicsTitle')}</p>
            <p className="max-w-prose text-muted">{t('today.noTopicsBody')}</p>
          </div>
          <Link to="/topics/new" className="rounded-full bg-accent-gradient px-4 py-2.5 font-semibold text-on-accent">
            {t('topics.new')}
          </Link>
        </Card>
      )}

      {today?.topics.map((section) => (
        <Card
          key={section.topic.id}
          title={
            <Link to={`/topics/${section.topic.id}`} className="hover:underline">
              {section.topic.name}
            </Link>
          }
          description={t('today.itemsToday', { count: section.items_today })}
          actions={
            <div className="flex gap-2">
              {section.themes.length > 0 && (
                <ImproveWithAiButton topicId={section.topic.id} topicName={section.topic.name} />
              )}
              <ScanTopicButton topicId={section.topic.id} />
            </div>
          }
        >
          {section.themes.length === 0 ? (
            <p className="text-muted">
              {section.items_today === 0 ? t('today.noItems') : t('today.noThemes')}
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {section.themes.map((theme) => (
                <ThemeRow key={theme.id} theme={theme} />
              ))}
            </ul>
          )}
        </Card>
      ))}
    </div>
  )
}

function StatTile({ icon, label, value }: { icon: ReactNode; label: string; value?: number }) {
  return (
    <div className="flex items-center gap-4 rounded-card border border-line bg-surface p-5 shadow-card">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-gradient text-on-accent [&>svg]:size-5">
        {icon}
      </span>
      <div>
        <p className="text-3xl leading-none font-bold text-ink">{value ?? '–'}</p>
        <p className="mt-1 text-sm text-muted">{label}</p>
      </div>
    </div>
  )
}

function ScanTopicButton({ topicId }: { topicId: number }) {
  const { t } = useTranslation()
  const start = useStartScan()
  const { data: scan } = useCurrentScan()
  const running = scan?.status === 'running'
  return (
    <button
      type="button"
      disabled={running || start.isPending}
      onClick={() => start.mutate(topicId)}
      className="flex shrink-0 items-center gap-2 rounded-full border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-raised disabled:opacity-50"
    >
      <RefreshCw className={`size-4 ${running ? 'animate-spin' : ''}`} aria-hidden />
      {t('topics.scanOne')}
    </button>
  )
}

function ImproveWithAiButton({ topicId, topicName }: { topicId: number; topicName: string }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex shrink-0 items-center gap-2 rounded-full border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-raised"
      >
        <Sparkles className="size-4" aria-hidden />
        {t('ai.insights.button')}
      </button>
      {open && <ThemeInsightsDialog topicId={topicId} topicName={topicName} onClose={() => setOpen(false)} />}
    </>
  )
}

function ThemeRow({ theme }: { theme: ThemeSummary }) {
  const { t } = useTranslation()
  const [xOpen, setXOpen] = useState(false)
  const sources = theme.sources.map((s) => t(`sources.${s}`)).join(', ')

  return (
    <li className="flex flex-wrap items-center gap-4 py-4">
      <ScoreRing score={theme.score} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/themes/${theme.id}`} className="text-lg font-semibold text-ink hover:underline">
            {theme.title}
          </Link>
          <TrendBadge trend={theme.trend} />
          {theme.covered && (
            <span className="rounded-full border border-line px-2.5 py-0.5 text-sm text-muted">
              {t('today.covered')}
            </span>
          )}
        </div>
        <p className="text-sm text-muted">
          {t('themes.itemsCount', { count: theme.item_count })} · {sources}
          {theme.question_count > 0 && ` · ${t('today.questions', { count: theme.question_count })}`}
        </p>
        {theme.summary ? (
          <p className="mt-1 line-clamp-2 max-w-prose text-ink/90">{theme.summary}</p>
        ) : (
          theme.representative && (
            <button
              type="button"
              onClick={() => openExternal(theme.representative!.url)}
              className="mt-1 line-clamp-1 text-left text-ink/90 hover:underline"
            >
              “{theme.representative.title}”
            </button>
          )
        )}
        {theme.related_terms.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {theme.related_terms.map((term) => (
              <span key={term} className="rounded-full bg-surface-raised px-2.5 py-0.5 text-sm text-muted">
                {term}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Link
          to={`/generator?theme=${theme.id}`}
          className="flex items-center gap-1.5 rounded-full bg-accent-gradient px-3 py-1.5 text-sm font-semibold text-on-accent"
        >
          <Sparkles className="size-4" aria-hidden />
          {t('today.generatePost')}
        </Link>
        <button
          type="button"
          onClick={() => setXOpen(true)}
          className="rounded-full border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-raised"
        >
          {t('today.searchX')}
        </button>
        {xOpen && <XSearchDialog themeId={theme.id} title={theme.title} onClose={() => setXOpen(false)} />}
        <Link
          to={`/themes/${theme.id}`}
          className="rounded-full border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-raised"
        >
          {t('today.details')}
        </Link>
      </div>
    </li>
  )
}
