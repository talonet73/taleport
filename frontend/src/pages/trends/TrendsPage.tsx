import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { type TrendsQuery, useTrends } from '../../api/insights'
import { useTopics } from '../../api/hooks'
import { LANGUAGES } from '../../api/types'
import { Card } from '../../components/Card'
import { ExportPdfButton } from '../../components/reports/ExportPdfButton'
import { BarList } from '../../components/charts/BarList'
import { ChangeList } from '../../components/charts/ChangeList'
import { GroupCompare } from '../../components/charts/GroupCompare'
import { MultiLineChart } from '../../components/charts/MultiLineChart'
import { WordCloud } from '../../components/charts/WordCloud'
import { useErrorMessage } from '../../components/useErrorMessage'

const field = 'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'

export function TrendsPage() {
  const { t, i18n } = useTranslation()
  const { data: topics = [] } = useTopics()
  const errorMessage = useErrorMessage()
  const [query, setQuery] = useState<TrendsQuery>({ period: 'last_7_days', topics: [], language: '' })
  const { data, error, isFetching } = useTrends(query)
  const mentions = (n: number) => t('trends.mentions', { count: n })
  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { day: 'numeric', month: 'short' }).format(new Date(`${iso}T12:00:00`))

  const toggleTopic = (id: number) =>
    setQuery((q) => ({ ...q, topics: q.topics.includes(id) ? q.topics.filter((x) => x !== id) : [...q.topics, id] }))

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('nav.trends')}</h1>
          <p className="mt-1 max-w-prose text-muted">{t('trends.subtitle')}</p>
        </div>
        <ExportPdfButton
          kind="trends"
          disabled={query.period === 'custom' && !(query.start && query.end)}
          body={{
            period: query.period,
            start: query.period === 'custom' ? query.start : null,
            end: query.period === 'custom' ? query.end : null,
            topics: query.topics.length ? query.topics : null,
            language: query.language || null,
          }}
        />
      </div>

      {/* Filters: one row above the charts */}
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-ink">{t('trends.period')}</legend>
            <div className="flex gap-1" role="radiogroup">
              {(['last_7_days', 'last_30_days', 'custom'] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  role="radio"
                  aria-checked={query.period === p}
                  onClick={() => setQuery((q) => ({ ...q, period: p }))}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium ${
                    query.period === p ? 'bg-accent-gradient text-on-accent' : 'border border-line text-ink hover:bg-surface-raised'
                  }`}
                >
                  {t(`trends.periods.${p}`)}
                </button>
              ))}
            </div>
          </fieldset>
          {query.period === 'custom' && (
            <>
              <label className="flex flex-col gap-1 text-sm text-ink">
                {t('trends.from')}
                <input type="date" value={query.start ?? ''} onChange={(e) => setQuery((q) => ({ ...q, start: e.target.value }))} className={field} />
              </label>
              <label className="flex flex-col gap-1 text-sm text-ink">
                {t('trends.to')}
                <input type="date" value={query.end ?? ''} onChange={(e) => setQuery((q) => ({ ...q, end: e.target.value }))} className={field} />
              </label>
            </>
          )}
          <label className="flex flex-col gap-1 text-sm text-ink">
            {t('trends.language')}
            <select value={query.language} onChange={(e) => setQuery((q) => ({ ...q, language: e.target.value }))} className={field}>
              <option value="">{t('trends.allLanguages')}</option>
              {LANGUAGES.map((l) => (
                <option key={l} value={l}>
                  {t(`languages.${l}`)}
                </option>
              ))}
            </select>
          </label>
          {topics.length > 1 && (
            <fieldset>
              <legend className="mb-1.5 text-sm font-medium text-ink">{t('trends.topics')}</legend>
              <div className="flex flex-wrap gap-1">
                {topics.map((tp) => (
                  <button
                    key={tp.id}
                    type="button"
                    aria-pressed={query.topics.includes(tp.id)}
                    onClick={() => toggleTopic(tp.id)}
                    className={`rounded-full px-3 py-1.5 text-sm ${
                      query.topics.includes(tp.id) ? 'bg-accent-gradient text-on-accent' : 'border border-line text-ink'
                    }`}
                  >
                    {tp.name}
                  </button>
                ))}
              </div>
            </fieldset>
          )}
          {isFetching && <span className="text-sm text-muted">{t('trends.loading')}</span>}
        </div>
      </Card>

      {error && <p className="text-red-400">{errorMessage(error)}</p>}
      {data && (
        <>
          <p className="text-muted">
            {t('trends.scope', { start: fmt(data.scope.start), end: fmt(data.scope.end), count: data.keywords.total_items })}
          </p>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title={t('trends.topKeywords')} description={t('trends.shareHint')}>
              <BarList rows={data.keywords.rows.map((r) => ({ label: r.term, value: r.count, share: r.share }))} unit={mentions} emptyText={t('trends.noData')} />
            </Card>
            <Card title={t('trends.topHashtags')}>
              <BarList rows={data.hashtags.rows.map((r) => ({ label: `#${r.term}`, value: r.count, share: r.share }))} unit={mentions} emptyText={t('trends.noHashtags')} />
            </Card>
          </div>

          <Card title={t('trends.trendTitle')} description={t('trends.trendHint')}>
            <MultiLineChart days={data.trend.days} series={data.trend.series.map((s) => ({ name: s.term, values: s.values }))} title={t('trends.trendTitle')} />
          </Card>

          <Card
            title={t('trends.changesTitle')}
            description={
              data.changes.has_history
                ? t('trends.changesHint', { start: fmt(data.changes.previous.start), end: fmt(data.changes.previous.end) })
                : t('trends.noHistory')
            }
          >
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <p className="mb-2 font-semibold text-ink">{t('trends.emerging')}</p>
                <ChangeList rows={data.changes.emerging} direction="up" emptyText={t('trends.noChanges')} />
              </div>
              <div>
                <p className="mb-2 font-semibold text-ink">{t('trends.declining')}</p>
                <ChangeList rows={data.changes.declining} direction="down" emptyText={t('trends.noChanges')} />
              </div>
            </div>
          </Card>

          <Card title={t('trends.cloud')}>
            <WordCloud words={data.cloud.map((r) => ({ term: r.term, count: r.count }))} unit={mentions} />
            {data.cloud.length === 0 && <p className="text-muted">{t('trends.noData')}</p>}
          </Card>

          <Card title={t('trends.byLanguage')}>
            <GroupCompare data={data.by_language} labelKey="languages" />
          </Card>
          <Card title={t('trends.bySource')}>
            <GroupCompare data={data.by_source} labelKey="sources" />
          </Card>
        </>
      )}
    </div>
  )
}
