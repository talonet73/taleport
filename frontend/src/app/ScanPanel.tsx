import { CheckCircle2, CircleAlert, CircleDashed, Loader2, MinusCircle, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useCancelScan, useCurrentScan } from '../api/hooks'
import type { CellState, ScanCell } from '../api/types'
import { SOURCE_ICONS } from '../components/sources'
import { useErrorMessage } from '../components/useErrorMessage'

const STATE_ICONS: Record<CellState, typeof CheckCircle2> = {
  pending: CircleDashed,
  running: Loader2,
  done: CheckCircle2,
  skipped: MinusCircle,
  error: CircleAlert,
}

const STATE_COLORS: Record<CellState, string> = {
  pending: 'text-muted',
  running: 'text-accent-text animate-spin',
  done: 'text-teal',
  skipped: 'text-muted',
  error: 'text-red-400',
}

/** Floating live progress of the current scan, per topic and source. */
export function ScanPanel() {
  const { t } = useTranslation()
  const { data: scan } = useCurrentScan()
  const cancel = useCancelScan()
  const errorMessage = useErrorMessage()
  const [dismissed, setDismissed] = useState<number | null>(null)

  // A new scan re-opens the panel.
  useEffect(() => {
    if (scan?.status === 'running') setDismissed(null)
  }, [scan?.scan_id, scan?.status])

  if (!scan || dismissed === scan.scan_id) return null
  const running = scan.status === 'running'
  const cell = (source: string, topicId: number) =>
    scan.cells.find((c) => c.source === source && c.topic_id === topicId)
  const total = scan.cells.length
  const finished = scan.cells.filter((c) => c.state !== 'pending' && c.state !== 'running').length
  const newItems = scan.cells.reduce((n, c) => n + c.new, 0)
  const problems = scan.cells.filter((c) => c.state === 'error' || (c.state === 'skipped' && c.code))
  const uniqueProblems = [
    ...new Map(problems.map((c) => [`${c.source}:${c.code}`, c] as const)).values(),
  ]

  return (
    <section
      aria-live="polite"
      className="fixed right-6 bottom-6 z-30 w-[34rem] max-w-[calc(100vw-3rem)] rounded-card border border-line bg-surface-raised p-5 shadow-card"
    >
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-ink">
            {running ? t('scan.running') : t(`scan.status.${scan.status}`)}
          </h2>
          <p className="text-sm text-muted">
            {t('scan.summary', { done: finished, total, count: newItems })}
          </p>
        </div>
        {running ? (
          <button
            type="button"
            onClick={() => cancel.mutate()}
            className="rounded-full border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface"
          >
            {t('scan.cancel')}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setDismissed(scan.scan_id)}
            aria-label={t('common.close')}
            className="rounded-full p-1.5 text-muted hover:bg-surface hover:text-ink"
          >
            <X className="size-4" aria-hidden />
          </button>
        )}
      </header>

      <div className="max-h-72 overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted">
              <th className="py-1 text-left font-medium">{t('scan.topic')}</th>
              {scan.sources.map((source) => {
                const Icon = SOURCE_ICONS[source]
                return (
                  <th key={source} className="px-1 py-1 font-medium" title={t(`sources.${source}`)}>
                    <Icon className="mx-auto size-4" aria-hidden />
                    <span className="sr-only">{t(`sources.${source}`)}</span>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {scan.topics.map((topic) => (
              <tr key={topic.id} className="border-t border-line">
                <td className="max-w-40 truncate py-1.5 pr-2 text-ink">{topic.name}</td>
                {scan.sources.map((source) => (
                  <td key={source} className="px-1 text-center">
                    <CellIcon cell={cell(source, topic.id)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {uniqueProblems.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
          {uniqueProblems.map((c) => (
            <li key={`${c.source}:${c.code}`} className={c.state === 'error' ? 'text-red-400' : 'text-muted'}>
              <span className="font-medium">{t(`sources.${c.source}`)}:</span>{' '}
              {errorMessage({ code: c.code, params: c.params })}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function CellIcon({ cell }: { cell: ScanCell | undefined }) {
  const { t } = useTranslation()
  if (!cell) return null
  const Icon = STATE_ICONS[cell.state]
  const label =
    cell.state === 'done'
      ? t('scan.cellDone', { found: cell.found, count: cell.new })
      : t(`scan.cell.${cell.state}`)
  return (
    <span title={label} className="inline-flex items-center gap-1">
      <Icon className={`size-4 ${STATE_COLORS[cell.state]}`} aria-hidden />
      {cell.state === 'done' && <span className="text-xs text-muted">{cell.new}</span>}
      <span className="sr-only">{label}</span>
    </span>
  )
}
