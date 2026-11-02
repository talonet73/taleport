import { FileText, Flame, Newspaper, Send } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useWeek } from '../../api/insights'
import { Card } from '../../components/Card'
import { ExportPdfButton } from '../../components/reports/ExportPdfButton'
import { BarList } from '../../components/charts/BarList'
import { DailyBars } from '../../components/charts/DailyBars'
import { ScoreRing } from '../../components/ScoreRing'
import { TrendBadge } from '../../components/TrendBadge'

export function WeekPage() {
  const { t, i18n } = useTranslation()
  const { data: week } = useWeek()
  if (!week) return null

  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { day: 'numeric', month: 'long' }).format(new Date(`${iso}T12:00:00`))
  const items = (n: number) => t('themes.itemsCount', { count: n })
  const sourceTotals = week.daily.by_source
    .map((s) => ({ label: t(`sources.${s.source}`), value: s.values.reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.value - a.value)

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('nav.week')}</h1>
          <p className="mt-1 text-muted">{t('week.range', { start: fmt(week.scope.start), end: fmt(week.scope.end) })}</p>
        </div>
        <ExportPdfButton kind="weekly" body={{}} />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile icon={<Newspaper />} label={t('week.items')} value={week.stats.items} />
        <Tile icon={<Flame />} label={t('week.themes')} value={week.stats.themes} />
        <Tile icon={<FileText />} label={t('week.generated')} value={week.stats.generated} />
        <Tile icon={<Send />} label={t('week.published')} value={week.stats.published} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title={t('week.perDay')} className="lg:col-span-2">
          <DailyBars days={week.daily.days} values={week.daily.totals} title={t('week.perDay')} unit={items} />
        </Card>
        <Card title={t('week.bySource')}>
          <BarList rows={sourceTotals} unit={items} emptyText={t('trends.noData')} />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={t('week.hotThemes')}>
          {week.themes.rows.length === 0 ? (
            <p className="text-muted">{t('trends.noData')}</p>
          ) : (
            <ul className="divide-y divide-line">
              {week.themes.rows.map((th) => (
                <li key={th.id} className="flex items-center gap-3 py-2.5">
                  <ScoreRing score={th.score} size={40} />
                  <div className="min-w-0 flex-1">
                    <Link to={`/themes/${th.id}`} className="font-medium text-ink hover:underline">
                      {th.title}
                    </Link>
                    <p className="text-sm text-muted">
                      {th.topic_name} · {fmt(th.day)} · {items(th.item_count)}
                    </p>
                  </div>
                  <TrendBadge trend={th.trend} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={t('week.topKeywords')} actions={<Link to="/trends" className="text-sm text-accent-text hover:underline">{t('week.toTrends')}</Link>}>
          <BarList
            rows={week.keywords.rows.map((r) => ({ label: r.term, value: r.count, share: r.share }))}
            unit={(n) => t('trends.mentions', { count: n })}
            emptyText={t('trends.noData')}
          />
        </Card>
      </div>
    </div>
  )
}

function Tile({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="flex items-center gap-4 rounded-card border border-line bg-surface p-5 shadow-card">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-gradient text-on-accent [&>svg]:size-5">
        {icon}
      </span>
      <div>
        <p className="text-3xl leading-none font-bold text-ink">{value}</p>
        <p className="mt-1 text-sm text-muted">{label}</p>
      </div>
    </div>
  )
}
