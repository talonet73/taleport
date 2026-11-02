import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { aiPost, queryKeys, useSettings } from '../../api/hooks'
import type { AiMode } from '../../api/types'
import { Modal } from '../Modal'
import { useErrorMessage } from '../useErrorMessage'
import { AiModeSelect } from './AiModeSelect'
import { HandoffPanel } from './HandoffPanel'
import { useAiFlow } from './useAiFlow'

/** AI titles, summaries and angles for today's themes of one topic. */
export function ThemeInsightsDialog({ topicId, topicName, onClose }: { topicId: number; topicName: string; onClose: () => void }) {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const queryClient = useQueryClient()
  const errorMessage = useErrorMessage()
  const [mode, setMode] = useState<AiMode>(settings?.default_ai ?? 'chat')
  const [updated, setUpdated] = useState<number | null>(null)

  const flow = useAiFlow<never>({
    start: (m) => aiPost('/ai/theme-insights', { topic_id: topicId, mode: m }),
    parse: (text) => aiPost('/ai/theme-insights/parse', { topic_id: topicId, text }),
    onDone: (envelope) => {
      setUpdated(envelope.updated ?? 0)
      void queryClient.invalidateQueries({ queryKey: queryKeys.today })
      void queryClient.invalidateQueries({ queryKey: ['themes'] })
      void queryClient.invalidateQueries({ queryKey: queryKeys.status })
    },
  })

  return (
    <Modal title={t('ai.insights.title', { topic: topicName })} onClose={onClose} wide={flow.phase === 'handoff'}>
      {flow.phase === 'done' ? (
        <div className="space-y-4">
          <p className="flex items-center gap-2 text-ink">
            <CheckCircle2 className="size-5 text-teal" aria-hidden />
            {t('ai.insights.done', { count: updated ?? 0 })}
          </p>
          <button type="button" onClick={onClose} className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent">
            {t('common.close')}
          </button>
        </div>
      ) : flow.phase === 'handoff' && flow.handoff ? (
        <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
      ) : (
        <div className="space-y-4">
          <p className="max-w-prose text-muted">{t('ai.insights.description')}</p>
          <AiModeSelect value={mode} onChange={setMode} />
          {flow.error !== null && <p className="text-red-400">{errorMessage(flow.error)}</p>}
          <button
            type="button"
            disabled={flow.busy}
            onClick={() => flow.run(mode)}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-60"
          >
            {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
            {flow.busy ? t('ai.working') : t('ai.insights.start')}
          </button>
        </div>
      )}
    </Modal>
  )
}
