import { ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { openExternal } from '../api/hooks'
import type { CollectedItem } from '../api/types'
import { SOURCE_ICONS } from './sources'

/** Collected news/videos/discussions; links open in the default browser. */
export function ItemList({ items }: { items: CollectedItem[] }) {
  const { t, i18n } = useTranslation()
  const formatDate = (iso: string | null) =>
    iso
      ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(
          new Date(iso),
        )
      : ''

  return (
    <ul className="divide-y divide-line">
      {items.map((item) => {
        const Icon = SOURCE_ICONS[item.source]
        return (
          <li key={item.id} className="flex gap-3 py-3">
            <span
              title={t(`sources.${item.source}`)}
              className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-surface-raised text-accent-text"
            >
              <Icon className="size-4" aria-hidden />
              <span className="sr-only">{t(`sources.${item.source}`)}</span>
            </span>
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => openExternal(item.url)}
                className="text-left font-medium text-ink hover:underline"
              >
                {item.title}
                <ExternalLink className="ml-1 inline size-3.5 text-muted" aria-hidden />
              </button>
              {item.excerpt && <p className="mt-0.5 line-clamp-2 text-sm text-muted">{item.excerpt}</p>}
              <p className="mt-1 text-sm text-muted">
                {[item.publisher, formatDate(item.published_at ?? item.first_seen_at ?? null)]
                  .filter(Boolean)
                  .join(' · ')}
                {typeof item.metrics.views === 'number' &&
                  ` · ${t('topics.items.views', { count: item.metrics.views })}`}
              </p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
