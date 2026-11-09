import { BookmarkPlus, Loader2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { aiPost, useSettings, useTopics } from '../../api/hooks'
import type { AiMode, Language, Platform } from '../../api/types'
import type { VoiceProfile, VoiceSuggestion } from '../../api/voices'
import { AiModeSelect } from '../../components/ai/AiModeSelect'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { LanguagePicker, PlatformPicker } from '../../components/drafts/Pickers'
import { Modal } from '../../components/Modal'
import { useErrorMessage } from '../../components/useErrorMessage'
import { DocumentsPicker } from '../../components/voices/DocumentsPicker'
import { useDocuments } from '../../components/voices/useDocuments'
import { VoiceSelect } from '../../components/voices/VoiceSelect'

const MAX_POSTS = 12
const fieldClass =
  'w-full rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none placeholder:text-muted focus:border-accent'
const REFERENCE = 'reference'

interface ReferenceOutcome {
  batch_id?: string
  topics?: string[]
  voice?: VoiceSuggestion | null
  voice_profile?: VoiceProfile | null
}

/** Posts from uploaded documents: their topics, written in their voice (or a saved one). */
export function ReferenceSource({ onBatch }: { onBatch: (batchId: string | null) => void }) {
  const { t, i18n } = useTranslation()
  const { data: settings } = useSettings()
  const { data: topics = [] } = useTopics()
  const errorMessage = useErrorMessage()
  const docs = useDocuments()

  const [platforms, setPlatforms] = useState<Platform[]>(['instagram'])
  const [languages, setLanguages] = useState<Language[]>([(i18n.language as Language) ?? 'it'])
  const [count, setCount] = useState(2)
  const [voice, setVoice] = useState(REFERENCE)
  const [topicId, setTopicId] = useState<number | null>(null)
  const [saveVoice, setSaveVoice] = useState(false)
  const [voiceName, setVoiceName] = useState('')
  const [mode, setMode] = useState<AiMode | null>(null)
  const [outcome, setOutcome] = useState<ReferenceOutcome | null>(null)

  const total = count * platforms.length * Math.max(languages.length, 1)
  const fromReference = voice === REFERENCE
  const request = {
    documents: docs.payload,
    platforms,
    languages,
    count,
    voice: fromReference ? 'reference' : voice ? 'profile' : 'topic',
    voice_id: !fromReference && voice ? Number(voice) : null,
    topic_id: topicId,
    save_voice: fromReference && saveVoice ? voiceName : null,
  }
  const flow = useAiFlow<never>({
    start: (m) => aiPost('/generator/reference', { ...request, mode: m }),
    parse: (text) => aiPost('/generator/reference/parse', { ...request, text }),
    onDone: (envelope) => {
      const result = envelope as unknown as ReferenceOutcome
      setOutcome(result)
      onBatch(result.batch_id ?? null)
    },
  })

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <p className="font-medium text-ink">{t('generator.reference.documents')}</p>
        <p className="text-sm text-muted">{t('generator.reference.documentsHint')}</p>
        <DocumentsPicker docs={docs} />
      </div>

      <PlatformPicker value={platforms} onChange={setPlatforms} />
      <LanguagePicker value={languages} onChange={setLanguages} />

      <div className="grid gap-4 md:grid-cols-2">
        <VoiceSelect
          value={voice}
          onChange={setVoice}
          extra={{ value: REFERENCE, label: t('voices.select.reference') }}
        />
        <label className="flex flex-col gap-2">
          <span className="font-medium text-ink">{t('generator.reference.audience')}</span>
          <select
            value={topicId ?? ''}
            onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : null)}
            className={fieldClass}
          >
            <option value="">{t('longContent.noTopic')}</option>
            {topics.map((tp) => (
              <option key={tp.id} value={tp.id}>
                {tp.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {fromReference && (
        <div className="space-y-2 rounded-2xl bg-surface-raised p-4">
          <label className="flex items-center gap-2 font-medium text-ink">
            <input type="checkbox" checked={saveVoice} onChange={(e) => setSaveVoice(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
            <BookmarkPlus className="size-4 text-accent-text" aria-hidden />
            {t('generator.reference.saveVoice')}
          </label>
          {saveVoice && (
            <input
              value={voiceName}
              onChange={(e) => setVoiceName(e.target.value)}
              maxLength={80}
              placeholder={t('generator.reference.voiceNamePlaceholder')}
              aria-label={t('generator.reference.voiceNamePlaceholder')}
              className={fieldClass}
            />
          )}
          <p className="text-sm text-muted">{t('generator.reference.saveVoiceHint')}</p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-2">
          <span className="font-medium text-ink">{t('generator.reference.count')}</span>
          <select value={count} onChange={(e) => setCount(Number(e.target.value))} className={fieldClass}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <AiModeSelect value={mode ?? settings?.default_ai ?? 'chat'} onChange={setMode} />
      </div>

      <p className={`text-sm ${total > MAX_POSTS ? 'text-red-400' : 'text-muted'}`}>
        {t('generator.count', { count: total, max: MAX_POSTS })}
      </p>
      {flow.error !== null && flow.phase !== 'handoff' && <p className="text-red-400">{errorMessage(flow.error)}</p>}
      <button
        type="button"
        disabled={!docs.documents.length || docs.reading || !platforms.length || !languages.length || total > MAX_POSTS || flow.busy}
        onClick={() => flow.run(mode ?? settings?.default_ai ?? 'chat')}
        className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-semibold text-on-accent disabled:opacity-50"
      >
        {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
        {flow.busy ? t('ai.working') : t('generator.reference.generate')}
      </button>

      {outcome && (outcome.topics?.length || outcome.voice_profile) ? (
        <div className="space-y-1 rounded-2xl border border-line p-4 text-sm" role="status">
          {outcome.topics && outcome.topics.length > 0 && (
            <p className="text-ink">
              <b>{t('generator.reference.topicsFound')}:</b> {outcome.topics.join(' · ')}
            </p>
          )}
          {outcome.voice_profile && (
            <p className="text-accent-text">{t('generator.reference.voiceSaved', { name: outcome.voice_profile.name })}</p>
          )}
        </div>
      ) : null}

      {flow.phase === 'handoff' && flow.handoff && (
        <Modal title={t('generator.handoffTitle')} onClose={flow.reset} wide>
          <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
        </Modal>
      )}
    </div>
  )
}
