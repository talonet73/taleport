import { ArrowDownRight, ArrowRight, ArrowUpRight, Sparkle } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { ThemeTrend } from '../api/types'

const ICONS = { up: ArrowUpRight, down: ArrowDownRight, flat: ArrowRight, new: Sparkle } as const

/** Trend arrow with its label: never color alone. */
export function TrendBadge({ trend }: { trend: ThemeTrend }) {
  const { t } = useTranslation()
  const Icon = ICONS[trend]
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-surface-raised px-2.5 py-0.5 text-sm font-medium text-ink">
      <Icon className="size-3.5" aria-hidden />
      {t(`today.trend.${trend}`)}
    </span>
  )
}
