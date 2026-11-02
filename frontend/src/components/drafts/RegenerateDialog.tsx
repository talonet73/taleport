import { useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { aiPost, useSettings } from '../../api/hooks'
import type { AiMode } from '../../api/types'
import { AiModeSelect } from '../ai/AiModeSelect'
import { HandoffPanel } from '../ai/HandoffPanel'
import { useAiFlow } from '../ai/useAiFlow'
import { Modal } from '../Modal'
import { useErrorMessage } from '../useErrorMessage'

export function RegenerateDialog({ draftId, onClose }: { draftId: number; onClose: () => void }) {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const queryClient = useQueryClient()
  const errorMessage = useErrorMessage()
  const [mode, setMode] = useState<AiMode>(settings?.default_ai ?? 'chat')

  const flow = useAiFlow<never>({
    start: (m) => aiPost(`/drafts/${draftId}/regenerate`, { mode: m }),
    parse: (text) => aiPost(`/drafts/${draftId}/regenerate/parse`, { text }),
    onDone: () => {
      void queryClient.invalidateQueries({ queryKey: ['drafts'] })
      void queryClient.invalidateQueries({ queryKey: ['generation'] })
      onClose()
    },
  })

  return (
    <Modal title={t('drafts.regenerate')} onClose={onClose} wide={flow.phase === 'handoff'}>
      {flow.phase === 'handoff' && flow.handoff ? (
        <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
      ) : (
        <div className="space-y-4">
          <p className="text-muted">{t('drafts.regenerateHint')}</p>
          <AiModeSelect value={mode} onChange={setMode} />
          {flow.error !== null && <p className="text-red-400">{errorMessage(flow.error)}</p>}
          <button
            type="button"
            disabled={flow.busy}
            onClick={() => flow.run(mode)}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-60"
          >
            {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <RefreshCw className="size-4" aria-hidden />}
            {flow.busy ? t('ai.working') : t('drafts.regenerate')}
          </button>
        </div>
      )}
    </Modal>
  )
}
