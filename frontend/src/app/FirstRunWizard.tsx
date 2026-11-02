import { Check, CheckCircle2, ExternalLink, Loader2, Monitor, Moon, Sun } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  openExternal,
  useAiProviders,
  useCurrentScan,
  useSecrets,
  useSettings,
  useStartScan,
  useTopics,
  useUpdateSettings,
} from '../api/hooks'
import { AI_MODES, type AiMode, LANGUAGES, type Language, type SecretName } from '../api/types'
import { Logo } from '../components/Logo'
import { Toggle } from '../components/Toggle'
import { useErrorMessage } from '../components/useErrorMessage'
import { SecretRow } from '../pages/settings/SettingsPage'
import { NewTopicForm } from '../pages/topics/TopicEditor'

const STEPS = ['language', 'ai', 'youtube', 'scan', 'topic', 'firstScan'] as const
type Step = (typeof STEPS)[number]

const PAID_KEYS: SecretName[] = ['anthropic', 'openai', 'xai', 'perplexity', 'gemini']
const LINKS = {
  ollama: 'https://ollama.com/download',
  console: 'https://console.cloud.google.com/projectcreate',
  library: 'https://console.cloud.google.com/apis/library/youtube.googleapis.com',
  credentials: 'https://console.cloud.google.com/apis/credentials',
}

const choice = (active: boolean) =>
  `rounded-card border p-4 text-left ${active ? 'border-accent bg-surface-raised' : 'border-line hover:border-accent'}`

/** Guided setup shown until it is completed or skipped (§4.1); Settings can restart it. */
export function FirstRunWizard() {
  const { t } = useTranslation()
  const update = useUpdateSettings()
  const [index, setIndex] = useState(0)
  const step: Step = STEPS[index]
  const { data: topics = [] } = useTopics()
  // Without a topic the step can only be skipped (saving the form moves on by itself).
  const skipOnly = step === 'topic' && topics.length === 0
  const finish = () => update.mutate({ first_run_completed: true })

  return (
    <div className="flex h-screen min-w-[1280px] flex-col overflow-y-auto">
      <header className="flex items-center justify-between px-10 pt-8">
        <Logo className="h-12 w-auto" />
        <button type="button" onClick={finish} className="text-sm text-muted hover:text-ink">
          {t('welcome.exit')}
        </button>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-8">
        <ol className="mb-8 flex items-center gap-2" aria-label={t('welcome.progress')}>
          {STEPS.map((name, i) => (
            <li key={name} className="flex flex-1 items-center gap-2">
              <span
                aria-current={i === index ? 'step' : undefined}
                className={`grid size-8 shrink-0 place-items-center rounded-full text-sm font-bold ${
                  i < index
                    ? 'bg-accent-gradient text-on-accent'
                    : i === index
                      ? 'border-2 border-accent text-ink'
                      : 'border border-line text-muted'
                }`}
              >
                {i < index ? <Check className="size-4" aria-hidden /> : i + 1}
                <span className="sr-only">{t(`welcome.steps.${name}`)}</span>
              </span>
              {i < STEPS.length - 1 && <span className={`h-0.5 flex-1 rounded ${i < index ? 'bg-accent' : 'bg-line'}`} />}
            </li>
          ))}
        </ol>

        <p className="text-sm font-semibold text-accent-text">
          {t('welcome.stepOf', { n: index + 1, total: STEPS.length })}
        </p>
        <h1 className="mt-1 text-3xl font-bold text-ink">{t(`welcome.${step}.title`)}</h1>
        <p className="mt-2 mb-6 max-w-prose text-muted">{t(`welcome.${step}.text`)}</p>

        {step === 'language' && <LanguageStep />}
        {step === 'ai' && <AiStep />}
        {step === 'youtube' && <YouTubeStep />}
        {step === 'scan' && <ScanTimeStep />}
        {step === 'topic' && <TopicStep onSaved={() => setIndex(index + 1)} />}
        {step === 'firstScan' && <FirstScanStep onDone={finish} />}

        <nav className="mt-10 flex items-center gap-3 border-t border-line pt-6">
          {index > 0 && (
            <button type="button" onClick={() => setIndex(index - 1)} className="rounded-full border border-line px-5 py-2 text-ink hover:bg-surface">
              {t('welcome.back')}
            </button>
          )}
          <span className="flex-1" />
          {index < STEPS.length - 1 ? (
            <button
              type="button"
              onClick={() => setIndex(index + 1)}
              className={
                skipOnly ? 'text-muted hover:text-ink' : 'rounded-full bg-accent-gradient px-6 py-2 font-semibold text-on-accent'
              }
            >
              {skipOnly ? t('welcome.skip') : t('welcome.next')}
            </button>
          ) : (
            <button type="button" onClick={finish} className="text-muted hover:text-ink">
              {t('welcome.finishWithoutScan')}
            </button>
          )}
        </nav>
      </main>
    </div>
  )
}

function LanguageStep() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  if (!settings) return null
  const themes = [
    { value: 'dark', icon: <Moon className="size-5" aria-hidden /> },
    { value: 'light', icon: <Sun className="size-5" aria-hidden /> },
    { value: 'system', icon: <Monitor className="size-5" aria-hidden /> },
  ] as const
  return (
    <div className="space-y-6">
      <div role="radiogroup" aria-label={t('settings.appearance.language')} className="grid grid-cols-3 gap-3">
        {LANGUAGES.map((lang: Language) => (
          <button
            key={lang}
            type="button"
            role="radio"
            aria-checked={settings.language === lang}
            onClick={() => update.mutate({ language: lang })}
            className={choice(settings.language === lang)}
          >
            <span className="text-lg font-semibold text-ink">{t(`languages.${lang}`)}</span>
          </button>
        ))}
      </div>
      <div role="radiogroup" aria-label={t('settings.appearance.theme')} className="grid grid-cols-3 gap-3">
        {themes.map(({ value, icon }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={settings.theme === value}
            onClick={() => update.mutate({ theme: value })}
            className={`${choice(settings.theme === value)} flex items-center gap-3 text-ink`}
          >
            {icon}
            {t(`settings.appearance.theme${value[0].toUpperCase()}${value.slice(1)}`)}
          </button>
        ))}
      </div>
    </div>
  )
}

function AiStep() {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: settings } = useSettings()
  const { data: providers } = useAiProviders()
  const { data: secrets } = useSecrets()
  const update = useUpdateSettings()
  if (!settings) return null
  const ollama = providers?.providers.find((p) => p.id === 'ollama')

  return (
    <div className="space-y-6">
      <Box>
        <p className="font-semibold text-ink">{t('welcome.ai.ollama')}</p>
        {!providers ? (
          <p className="mt-1 flex items-center gap-2 text-muted">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            {t('welcome.ai.detecting')}
          </p>
        ) : ollama?.ready ? (
          <p className="mt-1 flex items-center gap-2 text-ink">
            <CheckCircle2 className="size-4 text-accent-text" aria-hidden />
            {t('welcome.ai.ollamaReady', { models: ollama.models?.join(', ') || ollama.model })}
          </p>
        ) : (
          <>
            <p className="mt-1 text-muted">{errorMessage({ code: ollama?.code ?? 'ai.ollama_missing' })}</p>
            <p className="mt-1 text-sm text-muted">{t('welcome.ai.ollamaHow')}</p>
            <ExternalButton url={LINKS.ollama}>{t('welcome.ai.ollamaDownload')}</ExternalButton>
          </>
        )}
      </Box>

      <div>
        <p className="mb-2 font-semibold text-ink">{t('welcome.ai.choose')}</p>
        <div role="radiogroup" aria-label={t('welcome.ai.choose')} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {AI_MODES.map((mode: AiMode) => (
            <button
              key={mode}
              type="button"
              role="radio"
              aria-checked={settings.default_ai === mode}
              onClick={() => update.mutate({ default_ai: mode })}
              className={`${choice(settings.default_ai === mode)} p-3 text-sm text-ink`}
            >
              {t(`ai.${mode}`)}
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm text-muted">{t('welcome.ai.chatHint')}</p>
      </div>

      <details className="rounded-card border border-line bg-surface p-4">
        <summary className="cursor-pointer font-semibold text-ink">{t('welcome.ai.keys')}</summary>
        <p className="mt-2 text-sm text-muted">{t('welcome.ai.keysHint')}</p>
        <ul className="mt-2 divide-y divide-line">
          {PAID_KEYS.map((name) => (
            <SecretRow key={name} name={name} isSet={secrets?.[name] ?? false} />
          ))}
        </ul>
      </details>
    </div>
  )
}

function YouTubeStep() {
  const { t } = useTranslation()
  const { data: secrets } = useSecrets()
  const steps: { key: string; url?: string }[] = [
    { key: 'project', url: LINKS.console },
    { key: 'enable', url: LINKS.library },
    { key: 'key', url: LINKS.credentials },
    { key: 'restrict' },
    { key: 'paste' },
  ]
  return (
    <div className="space-y-6">
      <ol className="space-y-3">
        {steps.map((s, i) => (
          <li key={s.key} className="flex gap-3">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-raised text-sm font-bold text-ink">{i + 1}</span>
            <div>
              <p className="text-ink">{t(`welcome.youtube.steps.${s.key}`)}</p>
              {s.url && <ExternalButton url={s.url}>{t('welcome.youtube.open')}</ExternalButton>}
            </div>
          </li>
        ))}
      </ol>
      <ul className="rounded-card border border-line bg-surface px-4">
        <SecretRow name="youtube" isSet={secrets?.youtube ?? false} />
      </ul>
      <p className="text-sm text-muted">{t('welcome.youtube.withoutKey')}</p>
    </div>
  )
}

function ScanTimeStep() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const [time, setTime] = useState(settings?.scan_time ?? '07:00')
  if (!settings) return null
  return (
    <div className="space-y-5">
      <label className="flex flex-wrap items-center gap-3">
        <span className="w-64 font-medium text-ink">{t('settings.scan.time')}</span>
        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          onBlur={() => time && time !== settings.scan_time && update.mutate({ scan_time: time })}
          className="rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink"
        />
      </label>
      <div className="flex items-start gap-3">
        <Toggle
          checked={settings.start_with_windows}
          onChange={(v) => update.mutate({ start_with_windows: v })}
          label={t('settings.scan.startWithWindows')}
        />
        <div>
          <p className="text-ink">{t('settings.scan.startWithWindows')}</p>
          <p className="text-sm text-muted">{t('welcome.scan.recoveryHint')}</p>
        </div>
      </div>
    </div>
  )
}

function TopicStep({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation()
  const { data: topics = [] } = useTopics()
  const [adding, setAdding] = useState(false)
  if (topics.length > 0 && !adding) {
    return (
      <Box>
        <p className="text-ink">{t('welcome.topic.existing', { count: topics.length, names: topics.map((x) => x.name).join(', ') })}</p>
        <button type="button" onClick={() => setAdding(true)} className="mt-3 text-sm font-semibold text-accent-text hover:underline">
          {t('welcome.topic.addAnother')}
        </button>
      </Box>
    )
  }
  return <NewTopicForm onSaved={onSaved} />
}

function FirstScanStep({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: topics = [] } = useTopics()
  const { data: scan } = useCurrentScan()
  const start = useStartScan()
  const [startedId, setStartedId] = useState<number | null>(null)
  const ours = scan && startedId !== null && scan.scan_id === startedId ? scan : null
  const cells = ours?.cells ?? []
  const finished = cells.filter((c) => c.state !== 'pending' && c.state !== 'running').length
  const running = ours?.status === 'running'
  const found = cells.reduce((n, c) => n + c.found, 0)
  const fresh = cells.reduce((n, c) => n + c.new, 0)

  if (!topics.some((x) => x.active)) return <Box>{t('welcome.firstScan.noTopic')}</Box>

  return (
    <div className="space-y-5">
      {!ours ? (
        <button
          type="button"
          disabled={start.isPending}
          onClick={() => start.mutate(undefined, { onSuccess: (r) => setStartedId(r.scan_id) })}
          className="rounded-full bg-accent-gradient px-6 py-2.5 font-semibold text-on-accent disabled:opacity-60"
        >
          {t('welcome.firstScan.start')}
        </button>
      ) : (
        <Box>
          <p className="flex items-center gap-2 font-semibold text-ink" role="status">
            {running ? (
              <Loader2 className="size-4 animate-spin text-accent-text" aria-hidden />
            ) : (
              <CheckCircle2 className="size-4 text-accent-text" aria-hidden />
            )}
            {running ? t('welcome.firstScan.running', { done: finished, total: cells.length }) : t('welcome.firstScan.done', { found, fresh })}
          </p>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={cells.length}
            aria-valuenow={finished}
            className="mt-3 h-2 overflow-hidden rounded-full bg-surface-raised"
          >
            <div className="h-full rounded-full bg-accent-gradient transition-all" style={{ width: `${cells.length ? (100 * finished) / cells.length : 0}%` }} />
          </div>
          <p className="mt-2 text-sm text-muted">{t('welcome.firstScan.hint')}</p>
        </Box>
      )}
      {start.isError && <p className="text-sm text-red-400">{errorMessage(start.error)}</p>}
      {ours && !running && (
        <button type="button" onClick={onDone} className="rounded-full bg-accent-gradient px-6 py-2.5 font-semibold text-on-accent">
          {t('welcome.firstScan.goToday')}
        </button>
      )}
    </div>
  )
}

function Box({ children }: { children: ReactNode }) {
  return <div className="rounded-card border border-line bg-surface p-4">{children}</div>
}

function ExternalButton({ url, children }: { url: string; children: ReactNode }) {
  return (
    <button type="button" onClick={() => openExternal(url)} className="mt-1 flex items-center gap-1 text-sm font-semibold text-accent-text hover:underline">
      {children}
      <ExternalLink className="size-3.5" aria-hidden />
    </button>
  )
}
