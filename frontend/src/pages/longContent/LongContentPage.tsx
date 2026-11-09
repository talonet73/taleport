import { FileUp, Loader2, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { readAsBase64 } from '../../api/files'
import { aiPost, extractFile, useSettings, useTopics } from '../../api/hooks'
import type { AiMode, Language, Platform } from '../../api/types'
import { AiModeSelect } from '../../components/ai/AiModeSelect'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { Card } from '../../components/Card'
import { GenerationResults } from '../../components/drafts/GenerationPanel'
import { LanguagePicker, PlatformPicker } from '../../components/drafts/Pickers'
import { Modal } from '../../components/Modal'
import { useErrorMessage } from '../../components/useErrorMessage'
import { useTopicVoice, VoiceSelect } from '../../components/voices/VoiceSelect'

const fieldClass =
  'w-full rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none placeholder:text-muted focus:border-accent'

export function LongContentPage() {
  const { t, i18n } = useTranslation()
  const { data: settings } = useSettings()
  const { data: topics = [] } = useTopics()
  const errorMessage = useErrorMessage()
  const fileInput = useRef<HTMLInputElement>(null)

  const [content, setContent] = useState('')
  const [title, setTitle] = useState('')
  const [count, setCount] = useState(3)
  const [platforms, setPlatforms] = useState<Platform[]>(['linkedin'])
  const [languages, setLanguages] = useState<Language[]>([(i18n.language as Language) ?? 'it'])
  const [topicId, setTopicId] = useState<number | null>(null)
  const [mode, setMode] = useState<AiMode | null>(null)
  const [batchId, setBatchId] = useState<string | null>(null)
  const [truncated, setTruncated] = useState(false)
  const [fileError, setFileError] = useState<unknown>(null)
  const [reading, setReading] = useState(false)
  const [voice, setVoice] = useState('')
  const topicVoice = useTopicVoice(topicId)
  useEffect(() => setVoice(topicVoice), [topicVoice])

  const request = {
    content,
    title,
    count,
    platforms,
    language: languages[0],
    topic_id: topicId,
    voice_id: voice ? Number(voice) : null,
  }
  const flow = useAiFlow<never>({
    start: (m) => aiPost('/generator/long', { ...request, mode: m }),
    parse: (text) => aiPost('/generator/long/parse', { ...request, text }),
    onDone: (envelope) => {
      setBatchId(envelope.batch_id ?? null)
      setTruncated(!!envelope.truncated)
    },
  })

  const onFile = async (file: File | undefined) => {
    if (!file) return
    setFileError(null)
    setReading(true)
    try {
      const result = await extractFile(file.name, await readAsBase64(file))
      setContent(result.text)
      setTruncated(result.truncated)
      if (!title) setTitle(file.name.replace(/\.[^.]+$/, ''))
    } catch (err) {
      setFileError(err)
    } finally {
      setReading(false)
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">{t('nav.longContent')}</h1>
        <p className="mt-1 max-w-prose text-muted">{t('longContent.subtitle')}</p>
      </div>

      <Card>
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              className="flex items-center gap-2 rounded-full border border-line px-4 py-2 font-medium text-ink hover:bg-surface-raised"
            >
              {reading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FileUp className="size-4" aria-hidden />}
              {t('longContent.upload')}
            </button>
            <span className="text-sm text-muted">{t('longContent.formats')}</span>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.docx,.pptx,.txt,.md"
              className="hidden"
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
          </div>
          {fileError !== null && <p className="text-red-400">{errorMessage(fileError)}</p>}

          <label className="flex flex-col gap-2">
            <span className="font-medium text-ink">{t('longContent.title')}</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className={fieldClass} />
          </label>
          <label className="flex flex-col gap-2">
            <span className="font-medium text-ink">{t('longContent.content')}</span>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={10}
              placeholder={t('longContent.placeholder')}
              className={fieldClass}
            />
            <span className="text-sm text-muted">
              {t('longContent.characters', { count: content.length })}
              {truncated && ` · ${t('longContent.truncated')}`}
            </span>
          </label>

          <PlatformPicker value={platforms} onChange={setPlatforms} />
          <LanguagePicker value={languages} onChange={setLanguages} single />

          <div className="grid gap-4 md:grid-cols-3">
            <label className="flex flex-col gap-2">
              <span className="font-medium text-ink">{t('longContent.count')}</span>
              <select value={count} onChange={(e) => setCount(Number(e.target.value))} className={fieldClass}>
                {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2">
              <span className="font-medium text-ink">{t('longContent.styleFrom')}</span>
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
            <AiModeSelect value={mode ?? settings?.default_ai ?? 'chat'} onChange={setMode} />
          </div>
          <VoiceSelect value={voice} onChange={setVoice} />

          {flow.error !== null && flow.phase !== 'handoff' && <p className="text-red-400">{errorMessage(flow.error)}</p>}
          <button
            type="button"
            disabled={content.trim().length < 200 || !platforms.length || flow.busy}
            onClick={() => flow.run(mode ?? settings?.default_ai ?? 'chat')}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-semibold text-on-accent disabled:opacity-50"
          >
            {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
            {flow.busy ? t('ai.working') : t('longContent.generate', { count: count * platforms.length })}
          </button>
          {content.trim().length > 0 && content.trim().length < 200 && (
            <p className="text-sm text-muted">{t('longContent.tooShort')}</p>
          )}
        </div>
      </Card>

      {flow.phase === 'handoff' && flow.handoff && (
        <Modal title={t('generator.handoffTitle')} onClose={flow.reset} wide>
          <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
        </Modal>
      )}

      <GenerationResults batchId={batchId} truncated={truncated && !!batchId} />
    </div>
  )
}
