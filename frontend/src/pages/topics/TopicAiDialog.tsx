import { Loader2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { aiPost, useSettings } from '../../api/hooks'
import type { AiMode, TopicSuggestion } from '../../api/types'
import { AiModeSelect } from '../../components/ai/AiModeSelect'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { Modal } from '../../components/Modal'
import { useErrorMessage } from '../../components/useErrorMessage'

interface TopicAiDialogProps {
  editions: string[]
  onApply: (suggestion: TopicSuggestion) => void
  onClose: () => void
}

/** "Create with AI": one sentence in, every topic field proposed; the user reviews and saves. */
export function TopicAiDialog({ editions, onApply, onClose }: TopicAiDialogProps) {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const errorMessage = useErrorMessage()
  const [description, setDescription] = useState('')
  const [mode, setMode] = useState<AiMode>(settings?.default_ai ?? 'chat')

  const flow = useAiFlow<TopicSuggestion>({
    start: (m) => aiPost('/ai/topic-suggestion', { description, editions, mode: m }),
    parse: (text) => aiPost('/ai/topic-suggestion/parse', { text, editions }),
    onDone: (envelope) => {
      if (envelope.result) onApply(envelope.result)
      onClose()
    },
  })

  return (
    <Modal title={t('ai.topic.title')} onClose={onClose} wide={flow.phase === 'handoff'}>
      {flow.phase === 'handoff' && flow.handoff ? (
        <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
      ) : (
        <div className="space-y-4">
          <label className="flex flex-col gap-2">
            <span className="font-medium text-ink">{t('ai.topic.describe')}</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder={t('ai.topic.placeholder')}
              className="rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none placeholder:text-muted focus:border-accent"
            />
          </label>
          <AiModeSelect value={mode} onChange={setMode} />
          <p className="text-sm text-muted">{t('ai.topic.review')}</p>
          {flow.error !== null && <p className="text-red-400">{errorMessage(flow.error)}</p>}
          <button
            type="button"
            disabled={!description.trim() || flow.busy}
            onClick={() => flow.run(mode)}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-60"
          >
            {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
            {flow.busy ? t('ai.working') : t('ai.topic.generate')}
          </button>
        </div>
      )}
    </Modal>
  )
}
