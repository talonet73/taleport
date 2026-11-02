import { useTranslation } from 'react-i18next'

import type { Groups } from '../../api/insights'
import { BarList } from './BarList'

/** Small multiples: one panel per language or source, each with its own top terms. */
export function GroupCompare({ data, labelKey }: { data: Groups; labelKey: 'languages' | 'sources' }) {
  const { t } = useTranslation()
  const items = (n: number) => t('themes.itemsCount', { count: n })
  if (!data.groups.length) return <p className="text-muted">{t('trends.noData')}</p>
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {data.groups.map((g) => (
        <div key={g.key} className="rounded-xl bg-surface-raised p-4">
          <p className="font-semibold text-ink">{t(`${labelKey}.${g.key}`)}</p>
          <p className="mb-3 text-sm text-muted">{items(g.items)}</p>
          <BarList
            rows={g.top.map((r) => ({ label: r.term, value: r.count }))}
            unit={(n) => t('trends.mentions', { count: n })}
            emptyText={t('trends.noData')}
          />
        </div>
      ))}
    </div>
  )
}
