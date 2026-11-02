import { ArrowLeft, Lightbulb, MessageCircleQuestion } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'

import { useTheme } from '../../api/hooks'
import type { ScoreDetails } from '../../api/types'
import { Card } from '../../components/Card'
import { XSearchDialog } from '../../components/ai/XSearchDialog'
import { ItemList } from '../../components/ItemList'
import { ScoreRing } from '../../components/ScoreRing'
import { TrendBadge } from '../../components/TrendBadge'
import { TrendChart } from '../../components/TrendChart'

export function ThemeDetailPage() {
  const { id } = useParams()
  const { data: theme } = useTheme(Number(id))
  const { t, i18n } = useTranslation()
  const [xOpen, setXOpen] = useState(false)

  if (!theme) return null
  const sources = theme.sources.map((s) => t(`sources.${s}`)).join(', ')

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex items-start gap-4">
        <Link
          to="/today"
          aria-label={t('common.back')}
          className="mt-1 rounded-full p-2 text-muted hover:bg-surface hover:text-ink"
        >
          <ArrowLeft className="size-5" aria-hidden />
        </Link>
        <ScoreRing score={theme.score} size={72} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-bold text-ink">{theme.title}</h1>
            <TrendBadge trend={theme.trend} />
          </div>
          <p className="mt-1 text-muted">
            {theme.topic?.name} · {t('themes.itemsCount', { count: theme.item_count })} · {sources}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={t('themes.summary')}>
          <p className="max-w-prose text-[16px] leading-relaxed text-ink">
            {theme.summary ??
              (theme.related_terms.length
                ? t('themes.statsSummary', {
                    count: theme.item_count,
                    sources,
                    related: theme.related_terms.slice(0, 3).join(', '),
                  })
                : t('themes.statsSummaryNoRelated', { count: theme.item_count, sources }))}
          </p>
          <p className="mt-3 text-sm text-muted">
            {theme.summary ? t('themes.writtenByAi') : t('themes.aiLater')}
          </p>
          <WhyHot details={theme.score_details} />
        </Card>

        <Card title={t('themes.trendTitle')} description={t('themes.trendHint', { term: theme.title })}>
          <TrendChart points={theme.trend7} seriesLabel={t('themes.trendTitle')} />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={t('themes.questions')}>
          {theme.questions.length === 0 ? (
            <p className="text-muted">{t('themes.noQuestions')}</p>
          ) : (
            <ul className="space-y-3">
              {theme.questions.map((q) => (
                <li key={q} className="flex gap-3 text-ink">
                  <MessageCircleQuestion className="mt-0.5 size-5 shrink-0 text-accent-text" aria-hidden />
                  <span className="text-[16px]">{q}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={t('themes.angle')}>
          <div className="flex gap-3">
            <Lightbulb className="mt-0.5 size-5 shrink-0 text-accent-text" aria-hidden />
            <p className="text-[16px] text-ink">{theme.angle ?? t('themes.angleLater')}</p>
          </div>
        </Card>
      </div>

      <Card
        title={t('themes.xTitle')}
        description={t('themes.xHint')}
        actions={
          <button
            type="button"
            onClick={() => setXOpen(true)}
            className="shrink-0 rounded-full border border-line px-4 py-2 font-medium text-ink hover:bg-surface-raised"
          >
            {t('today.searchX')}
          </button>
        }
      >
        {theme.x_reports.length === 0 ? (
          <p className="text-muted">{t('themes.xEmpty')}</p>
        ) : (
          <div className="space-y-4">
            {theme.x_reports.map((report) => (
              <article key={report.id} className="rounded-xl bg-surface-raised p-4">
                <p className="mb-2 text-sm text-muted">
                  {t(report.via === 'api' ? 'themes.xViaApi' : 'themes.xViaChat')} ·{' '}
                  {new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(
                    new Date(report.created_at),
                  )}
                </p>
                <p className="max-w-prose text-[15px] whitespace-pre-wrap text-ink">{report.text}</p>
              </article>
            ))}
          </div>
        )}
      </Card>
      {xOpen && <XSearchDialog themeId={theme.id} title={theme.title} onClose={() => setXOpen(false)} />}

      <Card title={t('themes.sourcesTitle')}>
        <ItemList items={theme.items} />
      </Card>
    </div>
  )
}

/** Plain-language explanation of the hot score, one component per bar. */
function WhyHot({ details }: { details: ScoreDetails }) {
  const { t, i18n } = useTranslation()
  const number = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 })
  const rows = [
    {
      key: 'volume',
      text:
        details.average === null
          ? t('themes.why.volumeNew', { today: details.today })
          : t('themes.why.volume', { today: details.today, average: number.format(details.average) }),
    },
    {
      key: 'growth',
      text:
        details.yesterday === null
          ? t('themes.why.growthNew')
          : t('themes.why.growth', { yesterday: details.yesterday, today: details.today }),
    },
    { key: 'diversity', text: t('themes.why.diversity', { count: details.sources }) },
    { key: 'size', text: t('themes.why.size', { count: details.today }) },
  ] as const

  return (
    <div className="mt-6 border-t border-line pt-4">
      <h3 className="mb-3 font-semibold text-ink">{t('themes.why.title')}</h3>
      <ul className="space-y-3">
        {rows.map(({ key, text }) => {
          const value = Math.round(details.components[key] * 100)
          return (
            <li key={key}>
              <div className="flex justify-between gap-3 text-sm">
                <span className="text-ink">{text}</span>
                <span className="shrink-0 font-medium text-muted">{value}%</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-surface-raised">
                <div className="h-1.5 rounded-full bg-chart-1" style={{ width: `${value}%` }} />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
