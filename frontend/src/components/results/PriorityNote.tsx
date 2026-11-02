import { Lightbulb } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { PriorityReason } from '../../api/types'

/** "Suggested because posts on LinkedIn had more comments (13 on average)". */
export function PriorityNote({ reason, className = '' }: { reason: PriorityReason; className?: string }) {
  const { t, i18n } = useTranslation()
  const value = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 }).format(reason.params.value)
  const metric = t(`results.more.${reason.params.metric}`)
  const text =
    reason.code === 'platform'
      ? t('results.reason.platform', { platform: t(`platforms.${reason.params.platform}`), metric, value })
      : t('results.reason.theme', { theme: reason.params.theme, metric, value, count: reason.params.posts })
  return (
    <p className={`flex items-start gap-2 text-sm text-ink ${className}`}>
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-accent-text" aria-hidden />
      <span>{text}</span>
    </p>
  )
}
