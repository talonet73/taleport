import { Loader2, MessageCircleQuestion } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router'

import { aiPost, useSettings } from '../../api/hooks'
import { type AskResult, useAskPresets } from '../../api/insights'
import { api } from '../../api/client'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { Card } from '../../components/Card'
import { ExportPdfButton } from '../../components/reports/ExportPdfButton'
import { StepResult } from '../../components/insights/StepResult'
import { Modal } from '../../components/Modal'
import { useErrorMessage } from '../../components/useErrorMessage'

/** Answers to 'Ask': ready-made questions run without AI; free questions become a plan. */
export function AskPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { data: settings } = useSettings()
  const { data: presets = [] } = useAskPresets()
  const errorMessage = useErrorMessage()
  const [result, setResult] = useState<AskResult | null>(null)
  const [presetError, setPresetError] = useState<unknown>(null)
  const [loadingPreset, setLoadingPreset] = useState(false)
  const question = params.get('q') ?? ''
  const preset = params.get('preset') ?? ''
  const lastRun = useRef('')

  const flow = useAiFlow<never>({
    start: (m) => aiPost('/ask', { question, mode: m }),
    parse: (text) => aiPost('/ask/parse', { question, text }),
    onDone: (envelope) => setResult(envelope as unknown as AskResult),
  })

  useEffect(() => {
    const key = `${question}|${preset}`
    if (key === lastRun.current || (!question && !preset)) return
    lastRun.current = key
    setResult(null)
    setPresetError(null)
    if (preset) {
      setLoadingPreset(true)
      api<AskResult>(`/ask/preset/${preset}`, { method: 'POST' })
        .then(setResult)
        .catch(setPresetError)
        .finally(() => setLoadingPreset(false))
    } else if (settings) {
      void flow.run(settings.default_ai)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, preset, settings])

  const heading = preset ? t(`ask.presets.${preset}`) : question
  const error = presetError ?? (flow.phase !== 'handoff' ? flow.error : null)

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">{t('ask.title')}</h1>
        <p className="mt-1 max-w-prose text-muted">{t('ask.subtitle')}</p>
      </div>

      <Card title={t('ask.ready')}>
        <div className="flex flex-wrap gap-2">
          {presets.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => navigate(`/ask?preset=${id}`)}
              aria-pressed={preset === id}
              className={`rounded-full px-3 py-1.5 text-sm ${
                preset === id ? 'bg-accent-gradient font-semibold text-on-accent' : 'border border-line text-ink hover:bg-surface-raised'
              }`}
            >
              {t(`ask.presets.${id}`)}
            </button>
          ))}
        </div>
      </Card>

      {heading && (
        <h2 className="flex items-start gap-2 text-xl font-semibold text-ink">
          <MessageCircleQuestion className="mt-1 size-5 shrink-0 text-accent-text" aria-hidden />
          {heading}
        </h2>
      )}
      {(loadingPreset || flow.busy) && (
        <p className="flex items-center gap-2 text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {t('ai.working')}
        </p>
      )}
      {error !== null && error !== undefined && <p className="text-red-400">{errorMessage(error)}</p>}

      {result && (
        <div className="space-y-6">
          {result.title && !preset && <p className="text-muted">{result.title}</p>}
          {result.steps.map((step, i) => (
            <Card key={i} title={t(`ask.functions.${step.function}`)}>
              <StepResult step={step} />
            </Card>
          ))}
          {result.plan !== undefined && (
            <ExportPdfButton
              kind="ask"
              body={{ plan: result.plan, question: result.question ?? (preset ? t(`ask.presets.${preset}`) : '') }}
            />
          )}
        </div>
      )}

      {flow.phase === 'handoff' && flow.handoff && (
        <Modal title={t('ask.handoffTitle')} onClose={flow.reset} wide>
          <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
        </Modal>
      )}
    </div>
  )
}
