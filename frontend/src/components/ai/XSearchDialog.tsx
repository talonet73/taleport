import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { aiPost, queryKeys, useAiProviders } from '../../api/hooks'
import { Modal } from '../Modal'
import { useErrorMessage } from '../useErrorMessage'
import { HandoffPanel } from './HandoffPanel'
import { useAiFlow } from './useAiFlow'

interface XSearchDialogProps {
  themeId?: number
  topicId?: number
  title: string
  onClose: () => void
}

/** "Search X with Grok": free via grok.com (paste back), or paid via the xAI API. */
export function XSearchDialog({ themeId, topicId, title, onClose }: XSearchDialogProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const errorMessage = useErrorMessage()
  const { data: providers } = useAiProviders()
  const xaiReady = providers?.providers.find((p) => p.id === 'xai')?.ready ?? false
  const [mode, setMode] = useState<'chat' | 'xai'>('chat')
  const target = { theme_id: themeId ?? null, topic_id: topicId ?? null }

  const flow = useAiFlow<never>({
    start: () => aiPost('/ai/x-search', { ...target, mode }),
    parse: (text) => aiPost('/ai/x-search/save', { ...target, text }),
    onDone: () => {
      void queryClient.invalidateQueries({ queryKey: ['themes'] })
      void queryClient.invalidateQueries({ queryKey: queryKeys.status })
    },
  })

  return (
    <Modal title={t('ai.x.title', { title })} onClose={onClose} wide={flow.phase === 'handoff'}>
      {flow.phase === 'done' ? (
        <div className="space-y-4">
          <p className="flex items-center gap-2 text-ink">
            <CheckCircle2 className="size-5 text-teal" aria-hidden />
            {t('ai.x.saved')}
          </p>
          <button type="button" onClick={onClose} className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent">
            {t('common.close')}
          </button>
        </div>
      ) : flow.phase === 'handoff' && flow.handoff ? (
        <HandoffPanel
          handoff={flow.handoff}
          fallback={null}
          error={flow.error}
          onSubmit={flow.submitPasted}
          submitLabel={t('ai.x.saveAnswer')}
        />
      ) : (
        <div className="space-y-4">
          <p className="max-w-prose text-muted">{t('ai.x.description')}</p>
          <fieldset className="space-y-2">
            <label className="flex items-start gap-3 rounded-xl border border-line p-3">
              <input type="radio" name="x-mode" checked={mode === 'chat'} onChange={() => setMode('chat')} className="mt-1 accent-cyan" />
              <span>
                <span className="block font-medium text-ink">{t('ai.x.chat')}</span>
                <span className="text-sm text-muted">{t('ai.x.chatHint')}</span>
              </span>
            </label>
            <label className={`flex items-start gap-3 rounded-xl border border-line p-3 ${xaiReady ? '' : 'opacity-60'}`}>
              <input
                type="radio"
                name="x-mode"
                disabled={!xaiReady}
                checked={mode === 'xai'}
                onChange={() => setMode('xai')}
                className="mt-1 accent-cyan"
              />
              <span>
                <span className="block font-medium text-ink">{t('ai.x.api')}</span>
                <span className="text-sm text-muted">{xaiReady ? t('ai.x.apiHint') : t('ai.x.apiNoKey')}</span>
              </span>
            </label>
          </fieldset>
          {flow.error !== null && <p className="text-red-400">{errorMessage(flow.error)}</p>}
          <button
            type="button"
            disabled={flow.busy}
            onClick={() => flow.run('chat')}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-60"
          >
            {flow.busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {flow.busy ? t('ai.working') : t('ai.x.start')}
          </button>
        </div>
      )}
    </Modal>
  )
}
