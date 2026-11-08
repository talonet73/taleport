import { CheckCircle2, Lightbulb, Swords, Target, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { VideoProject } from '../../api/video'
import { Card } from '../../components/Card'
import { makeFormat } from './format'

const PRIORITY_CLASS = {
  high: 'bg-accent-gradient text-on-accent',
  medium: 'border border-accent text-accent-text',
  low: 'bg-surface-raised text-muted',
}

function PointList({ icon, title, points, names }: {
  icon: ReactNode
  title: string
  points: { title: string; detail: string; videos: number[] }[]
  names: Map<number, string>
}) {
  const { t } = useTranslation()
  if (!points.length) return null
  return (
    <Card title={<span className="flex items-center gap-2">{icon}{title}</span>}>
      <ul className="space-y-4">
        {points.map((point, i) => (
          <li key={i}>
            <p className="font-semibold text-ink">{point.title}</p>
            {point.detail && <p className="text-ink/90">{point.detail}</p>}
            {point.videos.length > 0 && (
              <p className="mt-1 text-sm text-muted">
                {t('video.analysis.examples', { videos: point.videos.map((id) => names.get(id) ?? `#${id}`).join(', ') })}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** Comparison table: always available (no AI needed). */
export function ComparisonTable({ project }: { project: VideoProject }) {
  const { t, i18n } = useTranslation()
  const f = makeFormat(i18n.language)
  const groups = project.groups.filter((g) => g.summary.videos > 0)
  if (!groups.length) return null
  const cell = 'px-3 py-2 text-right tabular-nums'
  return (
    <Card title={t('video.compare.title')} description={t('video.compare.subtitle')}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="px-3 py-2 text-left font-medium">{t('video.compare.profile')}</th>
              {(['videos', 'length', 'cuts', 'firstCut', 'firstWords', 'views', 'watched', 'interactions'] as const).map((k) => (
                <th key={k} className="px-3 py-2 text-right font-medium">
                  {t(`video.compare.${k}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={`${g.kind}-${g.name}`} className="border-b border-line/60 text-ink">
                <td className="px-3 py-2 font-semibold">
                  {g.kind === 'client' ? project.client_name : g.name}
                  {g.kind === 'client' && <span className="ml-2 text-xs font-normal text-accent-text">{t('video.compare.you')}</span>}
                </td>
                <td className={cell}>{g.summary.videos}</td>
                <td className={cell}>{f.sec(g.summary.duration)}</td>
                <td className={cell}>{f.n(g.summary.cuts_per_minute)}</td>
                <td className={cell}>{f.sec(g.summary.first_cut_at)}</td>
                <td className={cell}>{f.sec(g.summary.first_word_at)}</td>
                <td className={cell}>{f.compact(g.summary.views)}</td>
                <td className={cell}>{f.pct(g.summary.watched_ratio)}</td>
                <td className={cell}>{f.pct(g.summary.interaction_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-muted">{t('video.compare.note')}</p>
    </Card>
  )
}

export function AnalysisView({ project }: { project: VideoProject }) {
  const { t } = useTranslation()
  const analysis = project.analysis
  if (!analysis) return null
  const names = new Map(project.videos.map((v) => [v.id, v.file_name]))

  return (
    <div className="space-y-6">
      <Card title={t('video.analysis.summary')}>
        <p className="max-w-prose text-lg text-ink">{analysis.summary}</p>
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <PointList icon={<CheckCircle2 className="size-5 text-accent-text" aria-hidden />} title={t('video.analysis.strengths')} points={analysis.strengths} names={names} />
        <PointList icon={<TriangleAlert className="size-5 text-red-400" aria-hidden />} title={t('video.analysis.weaknesses')} points={analysis.weaknesses} names={names} />
      </div>

      {analysis.recommendations.length > 0 && (
        <Card title={<span className="flex items-center gap-2"><Target className="size-5 text-accent-text" aria-hidden />{t('video.analysis.recommendations')}</span>}>
          <ol className="space-y-3">
            {analysis.recommendations.map((r, i) => (
              <li key={i} className="flex gap-3">
                <span className={`h-fit shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${PRIORITY_CLASS[r.priority]}`}>
                  {t(`video.priority.${r.priority}`)}
                </span>
                <div>
                  <p className="font-semibold text-ink">{r.action}</p>
                  {r.why && <p className="text-muted">{r.why}</p>}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {analysis.competitors.length > 0 && (
        <Card title={<span className="flex items-center gap-2"><Swords className="size-5 text-accent-text" aria-hidden />{t('video.analysis.competitors')}</span>}>
          <div className="grid gap-4 lg:grid-cols-2">
            {analysis.competitors.map((c, i) => (
              <div key={i} className="space-y-1.5 rounded-2xl bg-surface-raised p-4">
                <p className="font-semibold text-ink">{c.name}</p>
                {c.what_works && <p className="text-ink"><b>{t('video.analysis.whatWorks')}:</b> {c.what_works}</p>}
                {c.weak_spots && <p className="text-ink"><b>{t('video.analysis.weakSpots')}:</b> {c.weak_spots}</p>}
                {c.to_borrow && <p className="text-accent-text"><b>{t('video.analysis.toBorrow')}:</b> {c.to_borrow}</p>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {analysis.videos.length > 0 && (
        <Card title={t('video.analysis.byVideo')}>
          <div className="space-y-4">
            {analysis.videos.map((v) => (
              <div key={v.id} className="border-b border-line/60 pb-4 last:border-0 last:pb-0">
                <p className="font-semibold text-ink">{names.get(v.id) ?? `#${v.id}`}</p>
                {v.verdict && <p className="text-ink">{v.verdict}</p>}
                <dl className="mt-1 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
                  {v.hook && (<><dt className="text-muted">{t('video.analysis.hook')}</dt><dd className="text-ink">{v.hook}</dd></>)}
                  {v.drop_off && (<><dt className="text-muted">{t('video.analysis.dropOff')}</dt><dd className="text-ink">{v.drop_off}</dd></>)}
                  {v.fix && (<><dt className="text-muted">{t('video.analysis.fix')}</dt><dd className="font-medium text-accent-text">{v.fix}</dd></>)}
                </dl>
              </div>
            ))}
          </div>
        </Card>
      )}

      {analysis.ideas.length > 0 && (
        <Card title={<span className="flex items-center gap-2"><Lightbulb className="size-5 text-accent-text" aria-hidden />{t('video.analysis.ideas')}</span>}>
          <ul className="list-disc space-y-1 pl-5 text-ink">
            {analysis.ideas.map((idea, i) => (
              <li key={i}>{idea}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
