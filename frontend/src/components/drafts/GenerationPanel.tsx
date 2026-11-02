import { useTranslation } from 'react-i18next'

import { useBatch, useDrafts } from '../../api/hooks'
import { DraftCard } from './DraftCard'

/** Drafts of the last generation, then the most recent ones. */
export function GenerationResults({ batchId, truncated }: { batchId: string | null; truncated?: boolean }) {
  const { t } = useTranslation()
  const { data: batch = [] } = useBatch(batchId)
  const { data: recent = [] } = useDrafts(20)
  const others = recent.filter((d) => d.batch_id !== batchId)

  return (
    <div className="space-y-6">
      {truncated && <p className="rounded-xl bg-surface-raised p-3 text-ink">{t('longContent.truncated')}</p>}
      {batch.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold text-ink">{t('generator.results', { count: batch.length })}</h2>
          {[...batch].reverse().map((draft) => (
            <DraftCard key={draft.id} draft={draft} />
          ))}
        </section>
      )}
      {others.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold text-ink">{t('generator.recent')}</h2>
          {others.map((draft) => (
            <DraftCard key={draft.id} draft={draft} />
          ))}
        </section>
      )}
    </div>
  )
}
