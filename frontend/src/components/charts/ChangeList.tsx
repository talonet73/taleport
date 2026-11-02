import { ArrowDownRight, ArrowUpRight, Sparkle } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { ChangeRow } from '../../api/insights'

/** Emerging or falling terms: arrow + written change, never color alone. */
export function ChangeList({ rows, direction, emptyText }: { rows: ChangeRow[]; direction: 'up' | 'down'; emptyText: string }) {
  const { t } = useTranslation()
  if (!rows.length) return <p className="text-muted">{emptyText}</p>
  return (
    <ul className="divide-y divide-line">
      {rows.map((r) => {
        const Icon = r.change_pct === null ? Sparkle : direction === 'up' ? ArrowUpRight : ArrowDownRight
        return (
          <li key={r.term} className="flex items-center gap-3 py-2">
            <Icon className="size-4 shrink-0 text-accent-text" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-ink">{r.term}</span>
            <span className="shrink-0 text-sm text-muted">
              {r.previous} → {r.current}
            </span>
            <span className="w-20 shrink-0 text-right text-sm font-medium text-ink">
              {r.change_pct === null ? t('trends.new') : `${r.change_pct > 0 ? '+' : ''}${r.change_pct}%`}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
