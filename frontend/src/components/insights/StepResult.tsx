import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { AskStep, ScopeInfo } from '../../api/insights'
import { BarList } from '../charts/BarList'
import { ChangeList } from '../charts/ChangeList'
import { GroupCompare } from '../charts/GroupCompare'
import { MultiLineChart } from '../charts/MultiLineChart'
import { TrendBadge } from '../TrendBadge'

function range(scope: ScopeInfo, lang: string): string {
  const f = (iso: string) => new Intl.DateTimeFormat(lang, { day: 'numeric', month: 'short' }).format(new Date(`${iso}T12:00:00`))
  return scope.start === scope.end ? f(scope.start) : `${f(scope.start)} – ${f(scope.end)}`
}

/** A written one-line answer for a step, built from its data (no AI involved). */
function useSentence(step: AskStep): string {
  const { t, i18n } = useTranslation()
  switch (step.function) {
    case 'top_keywords': {
      const top = step.result.rows[0]
      if (!top) return t('ask.sentence.empty')
      return t(step.result.kind === 'hashtag' ? 'ask.sentence.topHashtag' : 'ask.sentence.topKeyword', {
        term: top.term, count: top.count, share: top.share, range: range(step.scope, i18n.language),
      })  // prettier-ignore
    }
    case 'emerging_keywords': {
      const up = step.result.emerging.map((r) => r.term).slice(0, 3).join(', ')
      const down = step.result.declining.map((r) => r.term).slice(0, 3).join(', ')
      if (!step.result.has_history) return t('ask.sentence.noHistory')
      return t('ask.sentence.changes', { up: up || '–', down: down || '–' })
    }
    case 'topic_trend':
      return step.result.series.length
        ? t('ask.sentence.trend', { terms: step.result.series.map((s) => s.term).join(', ') })
        : t('ask.sentence.empty')
    case 'compare_periods': {
      const top = step.result.rows[0]
      return top ? t('ask.sentence.periods', { term: top.term, a: top.a, b: top.b }) : t('ask.sentence.empty')
    }
    case 'compare_languages':
    case 'compare_sources': {
      const best = [...step.result.groups].sort((a, b) => b.items - a.items)[0]
      if (!best) return t('ask.sentence.empty')
      const name = t(`${step.function === 'compare_languages' ? 'languages' : 'sources'}.${best.key}`)
      return t('ask.sentence.groups', { name, count: best.items })
    }
    case 'top_themes': {
      const top = step.result.rows[0]
      return top ? t('ask.sentence.themes', { title: top.title, score: top.score }) : t('ask.sentence.empty')
    }
    case 'post_performance': {
      const generated = step.result.rows.reduce((n, r) => n + r.generated, 0)
      const published = step.result.rows.reduce((n, r) => n + (r.published ?? 0), 0)
      return t('ask.sentence.posts', { generated, published })
    }
  }
}

export function StepResult({ step }: { step: AskStep }) {
  const { t } = useTranslation()
  const sentence = useSentence(step)
  const mentions = (n: number) => t('trends.mentions', { count: n })

  return (
    <div className="space-y-4">
      <p className="max-w-prose text-[16px] text-ink">{sentence}</p>
      {step.function === 'top_keywords' && (
        <BarList
          rows={step.result.rows.map((r) => ({ label: step.result.kind === 'hashtag' ? `#${r.term}` : r.term, value: r.count, share: r.share }))}
          unit={mentions}
          emptyText={t('trends.noData')}
        />
      )}
      {step.function === 'emerging_keywords' && (
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <p className="mb-2 font-semibold text-ink">{t('trends.emerging')}</p>
            <ChangeList rows={step.result.emerging} direction="up" emptyText={t('trends.noChanges')} />
          </div>
          <div>
            <p className="mb-2 font-semibold text-ink">{t('trends.declining')}</p>
            <ChangeList rows={step.result.declining} direction="down" emptyText={t('trends.noChanges')} />
          </div>
        </div>
      )}
      {step.function === 'topic_trend' && (
        <MultiLineChart
          days={step.result.days}
          series={step.result.series.map((s) => ({ name: s.term, values: s.values }))}
          title={t('trends.trendTitle')}
        />
      )}
      {step.function === 'compare_periods' && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="py-1 font-medium">{t('ask.term')}</th>
              <th className="py-1 text-right font-medium">{t('ask.periodA')}</th>
              <th className="py-1 text-right font-medium">{t('ask.periodB')}</th>
              <th className="py-1 text-right font-medium">{t('ask.difference')}</th>
            </tr>
          </thead>
          <tbody>
            {step.result.rows.map((r) => (
              <tr key={r.term} className="border-t border-line text-ink">
                <td className="py-1.5">{r.term}</td>
                <td className="py-1.5 text-right">{r.a}</td>
                <td className="py-1.5 text-right">{r.b}</td>
                <td className="py-1.5 text-right font-medium">{r.b - r.a > 0 ? `+${r.b - r.a}` : r.b - r.a}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {step.function === 'compare_languages' && <GroupCompare data={step.result} labelKey="languages" />}
      {step.function === 'compare_sources' && <GroupCompare data={step.result} labelKey="sources" />}
      {step.function === 'top_themes' && (
        <ul className="divide-y divide-line">
          {step.result.rows.map((th) => (
            <li key={th.id} className="flex flex-wrap items-center gap-3 py-2">
              <span className="w-10 text-right font-bold text-ink">{th.score}</span>
              <Link to={`/themes/${th.id}`} className="font-medium text-ink hover:underline">
                {th.title}
              </Link>
              <TrendBadge trend={th.trend} />
              <span className="ml-auto text-sm text-muted">
                {th.topic_name} · {th.day}
              </span>
            </li>
          ))}
        </ul>
      )}
      {step.function === 'post_performance' && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-1 font-medium">{t('generator.platforms')}</th>
                <th className="py-1 text-right font-medium">{t('week.generated')}</th>
                <th className="py-1 text-right font-medium">{t('week.published')}</th>
              </tr>
            </thead>
            <tbody>
              {step.result.rows.map((r) => (
                <tr key={r.platform} className="border-t border-line text-ink">
                  <td className="py-1.5">{t(`platforms.${r.platform}`)}</td>
                  <td className="py-1.5 text-right">{r.generated}</td>
                  <td className="py-1.5 text-right">{r.published ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!step.result.metrics_available && <p className="text-sm text-muted">{t('ask.metricsLater')}</p>}
        </>
      )}
    </div>
  )
}
