import { FileText, Flame, Loader2, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'

import { aiPost, useSettings, useToday, useTopics } from '../../api/hooks'
import { useResultsSummary } from '../../api/planner'
import type { AiMode, Language, Platform } from '../../api/types'
import { AiModeSelect } from '../../components/ai/AiModeSelect'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { Card } from '../../components/Card'
import { GenerationResults } from '../../components/drafts/GenerationPanel'
import { LanguagePicker, PlatformPicker } from '../../components/drafts/Pickers'
import { Modal } from '../../components/Modal'
import { PriorityNote } from '../../components/results/PriorityNote'
import { useErrorMessage } from '../../components/useErrorMessage'
import { useTopicVoice, VoiceSelect } from '../../components/voices/VoiceSelect'
import { ReferenceSource } from './ReferenceSource'

const MAX_POSTS = 12
const fieldClass =
  'w-full rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none placeholder:text-muted focus:border-accent'

export function GeneratorPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const { data: settings } = useSettings()
  const { data: today } = useToday()
  const { data: topics = [] } = useTopics()
  const errorMessage = useErrorMessage()
  const { data: results } = useResultsSummary()

  const [themeId, setThemeId] = useState<number | null>(params.get('theme') ? Number(params.get('theme')) : null)
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [languages, setLanguages] = useState<Language[]>([])
  const [variants, setVariants] = useState(1)
  const [tone, setTone] = useState('')
  const [mode, setMode] = useState<AiMode | null>(null)
  const [batchId, setBatchId] = useState<string | null>(null)
  const [source, setSource] = useState<'theme' | 'reference'>(params.get('source') === 'reference' ? 'reference' : 'theme')
  const [voice, setVoice] = useState('')

  const sections = today?.topics ?? []
  const theme = sections.flatMap((s) => s.themes).find((th) => th.id === themeId)
  const topic = topics.find((tp) => tp.id === theme?.topic_id)

  // Defaults from the theme's topic: its social networks, languages and tone.
  useEffect(() => {
    if (!topic) return
    setPlatforms((p) => (p.length ? p : topic.platforms.length ? topic.platforms : ['linkedin']))
    setLanguages((l) =>
      l.length ? l : [...new Set(topic.editions.map((e) => e.split('-')[0] as Language))].slice(0, 1),
    )
  }, [topic])
  useEffect(() => {
    if (!themeId && sections[0]?.themes[0]) setThemeId(sections[0].themes[0].id)
  }, [sections, themeId])
  // The voice linked to the theme's topic is pre-selected (it can still be changed).
  const topicVoice = useTopicVoice(topic?.id)
  useEffect(() => setVoice(topicVoice), [topicVoice])

  const total = platforms.length * Math.max(languages.length, 1) * variants
  const request = { theme_id: themeId, platforms, languages, variants, tone: tone || null, voice_id: voice ? Number(voice) : null }
  const flow = useAiFlow<never>({
    start: (m) => aiPost('/generator/theme', { ...request, mode: m }),
    parse: (text) => aiPost('/generator/theme/parse', { ...request, text }),
    onDone: (envelope) => setBatchId(envelope.batch_id ?? null),
  })

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">{t('nav.generator')}</h1>
        <p className="mt-1 max-w-prose text-muted">{t('generator.subtitle')}</p>
      </div>

      <div role="tablist" aria-label={t('generator.source.label')} className="inline-flex rounded-full border border-line bg-surface p-1 shadow-card">
        {(
          [
            ['theme', Flame, t('generator.source.theme')],
            ['reference', FileText, t('generator.source.reference')],
          ] as const
        ).map(([key, Icon, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={source === key}
            onClick={() => setSource(key)}
            className={`flex items-center gap-2 rounded-full px-4 py-2 font-semibold transition ${
              source === key ? 'bg-accent-gradient text-on-accent' : 'text-muted hover:text-ink'
            }`}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        ))}
      </div>

      {source === 'reference' ? (
        <Card>
          <ReferenceSource onBatch={setBatchId} />
        </Card>
      ) : (
      <Card>
        <div className="space-y-5">
          <label className="flex flex-col gap-2">
            <span className="font-medium text-ink">{t('generator.theme')}</span>
            {sections.some((s) => s.themes.length) ? (
              <select
                value={themeId ?? ''}
                onChange={(e) => setThemeId(Number(e.target.value))}
                className={fieldClass}
              >
                {sections.map((s) => (
                  <optgroup key={s.topic.id} label={s.topic.name}>
                    {s.themes.map((th) => (
                      <option key={th.id} value={th.id}>
                        {th.title} ({th.score}){th.covered ? ` · ${t('today.covered')}` : ''}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            ) : (
              <p className="text-muted">{t('generator.noThemes')}</p>
            )}
          </label>
          {theme?.covered && <p className="text-sm text-accent-text">{t('generator.coveredHint')}</p>}

          <PlatformPicker value={platforms} onChange={setPlatforms} />
          {results?.reasons.map((reason, i) => <PriorityNote key={i} reason={reason} />)}
          <LanguagePicker value={languages} onChange={setLanguages} />

          <VoiceSelect value={voice} onChange={setVoice} />

          <div className="grid gap-4 md:grid-cols-3">
            <label className="flex flex-col gap-2">
              <span className="font-medium text-ink">{t('generator.variants')}</span>
              <select value={variants} onChange={(e) => setVariants(Number(e.target.value))} className={fieldClass}>
                {[1, 2, 3].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2">
              <span className="font-medium text-ink">{voice ? t('generator.toneExtra') : t('generator.tone')}</span>
              <input
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                placeholder={topic?.tone || t('topics.placeholders.tone')}
                className={fieldClass}
              />
            </label>
            <AiModeSelect value={mode ?? settings?.default_ai ?? 'chat'} onChange={setMode} />
          </div>

          <p className={`text-sm ${total > MAX_POSTS ? 'text-red-400' : 'text-muted'}`}>
            {t('generator.count', { count: total, max: MAX_POSTS })}
          </p>
          {flow.error !== null && flow.phase !== 'handoff' && <p className="text-red-400">{errorMessage(flow.error)}</p>}
          <button
            type="button"
            disabled={!themeId || !platforms.length || !languages.length || total > MAX_POSTS || flow.busy}
            onClick={() => flow.run(mode ?? settings?.default_ai ?? 'chat')}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-semibold text-on-accent disabled:opacity-50"
          >
            {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
            {flow.busy ? t('ai.working') : t('generator.generate')}
          </button>
        </div>
      </Card>
      )}

      {flow.phase === 'handoff' && flow.handoff && (
        <Modal title={t('generator.handoffTitle')} onClose={flow.reset} wide>
          <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
        </Modal>
      )}

      <GenerationResults batchId={batchId} />
    </div>
  )
}
