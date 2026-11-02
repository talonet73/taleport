import { RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { useCurrentScan, useStartScan, useTopicItems } from '../../api/hooks'
import { Card } from '../../components/Card'
import { ItemList } from '../../components/ItemList'

/** Latest items collected for a topic. */
export function TopicItems({ topicId }: { topicId: number }) {
  const { t } = useTranslation()
  const { data: items = [], refetch } = useTopicItems(topicId)
  const startScan = useStartScan()
  const { data: scan } = useCurrentScan()
  const scanning = scan?.status === 'running'

  return (
    <Card
      title={t('topics.items.title')}
      description={t('topics.items.description')}
      actions={
        <button
          type="button"
          disabled={scanning || startScan.isPending}
          onClick={() => startScan.mutate(topicId, { onSettled: () => void refetch() })}
          className="flex items-center gap-2 rounded-full border border-line px-4 py-2 font-semibold text-ink hover:bg-surface-raised disabled:opacity-50"
        >
          <RefreshCw className={`size-4 ${scanning ? 'animate-spin' : ''}`} aria-hidden />
          {t('topics.scanOne')}
        </button>
      }
    >
      {items.length === 0 ? <p className="text-muted">{t('topics.items.empty')}</p> : <ItemList items={items} />}
    </Card>
  )
}
