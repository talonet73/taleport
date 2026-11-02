import { CheckCircle2, CircleAlert, Loader2, PlugZap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  useAiProviders,
  useProviderModels,
  useSettings,
  useTestProvider,
  useUpdateSettings,
} from '../../api/hooks'
import { AI_MODES, type AiMode, CHAT_SITES, type ChatSite, type ProviderStatus } from '../../api/types'
import { Card } from '../../components/Card'
import { Toggle } from '../../components/Toggle'
import { useErrorMessage } from '../../components/useErrorMessage'

const fieldClass =
  'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'

export function AiSettingsCard() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const { data: providers } = useAiProviders()
  const update = useUpdateSettings()
  if (!settings) return null

  return (
    <Card title={t('settings.ai.title')} description={t('settings.ai.description')}>
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-2">
            <span className="font-medium text-ink">{t('settings.ai.default')}</span>
            <select
              value={settings.default_ai}
              onChange={(e) => update.mutate({ default_ai: e.target.value as AiMode })}
              className={fieldClass}
            >
              {AI_MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {t(`ai.${mode}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-2">
            <span className="font-medium text-ink">{t('settings.ai.chatSite')}</span>
            <select
              value={settings.chat_site}
              onChange={(e) => update.mutate({ chat_site: e.target.value as ChatSite })}
              className={fieldClass}
            >
              {CHAT_SITES.map((site) => (
                <option key={site} value={site}>
                  {t(`ai.sites.${site}`)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <Toggle
              checked={settings.ai_auto_insights}
              onChange={(v) => update.mutate({ ai_auto_insights: v })}
              label={t('settings.ai.autoInsights')}
            />
            <div>
              <p className="text-ink">{t('settings.ai.autoInsights')}</p>
              <p className="max-w-prose text-sm text-muted">{t('settings.ai.autoInsightsHint')}</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Toggle
              checked={settings.chat_prefill}
              onChange={(v) => update.mutate({ chat_prefill: v })}
              label={t('settings.ai.prefill')}
            />
            <div>
              <p className="text-ink">{t('settings.ai.prefill')}</p>
              <p className="max-w-prose text-sm text-muted">{t('settings.ai.prefillHint')}</p>
            </div>
          </div>
        </div>

        <div>
          <h3 className="mb-2 font-semibold text-ink">{t('settings.ai.providers')}</h3>
          <ul className="divide-y divide-line rounded-xl border border-line">
            {providers?.providers.map((provider) => (
              <ProviderRow key={provider.id} provider={provider} />
            ))}
          </ul>
        </div>

        <label className="flex flex-wrap items-center gap-3">
          <span className="w-48 font-medium text-ink">{t('settings.ai.ollamaUrl')}</span>
          <OllamaUrlInput value={settings.ollama_url} onSave={(ollama_url) => update.mutate({ ollama_url })} />
        </label>

      </div>
    </Card>
  )
}

function OllamaUrlInput({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  return (
    <input
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => draft !== value && /^https?:\/\/\S+$/.test(draft) && onSave(draft)}
      className={`${fieldClass} w-72`}
    />
  )
}

function ProviderRow({ provider }: { provider: ProviderStatus }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const test = useTestProvider()
  const [model, setModel] = useState(settings?.ai_models[provider.id] ?? '')
  const canList = provider.ready && ['ollama', 'openai', 'xai', 'gemini'].includes(provider.id)
  const { data: models } = useProviderModels(provider.id, canList)
  const listId = `models-${provider.id}`

  const saveModel = () => {
    if (!settings || (settings.ai_models[provider.id] ?? '') === model.trim()) return
    const next = { ...settings.ai_models }
    if (model.trim()) next[provider.id] = model.trim()
    else delete next[provider.id]
    update.mutate({ ai_models: next })
  }

  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <span className="w-32 font-medium text-ink">{provider.label}</span>
      <span
        className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-sm ${
          provider.ready ? 'bg-teal/15 text-accent-text' : 'bg-surface-raised text-muted'
        }`}
      >
        {provider.ready ? <CheckCircle2 className="size-3.5" aria-hidden /> : <CircleAlert className="size-3.5" aria-hidden />}
        {provider.ready
          ? t('settings.ai.ready')
          : errorMessage({
              code: provider.code,
              params: { provider: provider.label, url: settings?.ollama_url ?? '' },
            })}
      </span>
      <span className="text-sm text-muted">{provider.paid ? t('settings.ai.paid') : t('settings.ai.free')}</span>
      <div className="ml-auto flex items-center gap-2">
        <input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          onBlur={saveModel}
          list={listId}
          placeholder={provider.model || t('settings.ai.modelPlaceholder')}
          aria-label={t('settings.ai.model', { provider: provider.label })}
          className={`${fieldClass} w-56`}
        />
        <datalist id={listId}>
          {(models ?? provider.models ?? []).map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>
        <button
          type="button"
          disabled={!provider.ready || test.isPending}
          onClick={() => test.mutate(provider.id)}
          className="flex items-center gap-1.5 rounded-xl border border-line px-3 py-2 text-sm font-medium text-ink hover:bg-surface-raised disabled:opacity-50"
        >
          {test.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <PlugZap className="size-4" aria-hidden />}
          {t('settings.ai.test')}
        </button>
      </div>
      {test.isSuccess && (
        <p className="w-full text-sm text-accent-text">
          {t('settings.ai.testOk', { model: test.data.model, ms: test.data.latency_ms })}
        </p>
      )}
      {test.isError && <p className="w-full text-sm text-red-400">{errorMessage(test.error)}</p>}
    </li>
  )
}
