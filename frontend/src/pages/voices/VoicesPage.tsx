import { FileSearch, Loader2, Pencil, Plus, Quote, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { aiPost, useSettings, useTopics } from '../../api/hooks'
import type { AiMode } from '../../api/types'
import {
  useDeleteVoice,
  useSaveVoice,
  useVoices,
  type VoiceProfile,
  type VoiceProfileInput,
  type VoiceSuggestion,
} from '../../api/voices'
import { AiModeSelect } from '../../components/ai/AiModeSelect'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { Card } from '../../components/Card'
import { Modal } from '../../components/Modal'
import { useErrorMessage } from '../../components/useErrorMessage'
import { DocumentsPicker } from '../../components/voices/DocumentsPicker'
import { useDocuments } from '../../components/voices/useDocuments'

const fieldClass =
  'w-full rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none placeholder:text-muted focus:border-accent'

const EMPTY: VoiceProfileInput = { name: '', guide: '', examples: [], topic_ids: [], sources: [] }

/** Name, instructions, examples and linked topics of one profile. */
function VoiceEditor({
  id,
  initial,
  onClose,
}: {
  id: number | null
  initial: VoiceProfileInput
  onClose: () => void
}) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: topics = [] } = useTopics()
  const { data: voices = [] } = useVoices()
  const save = useSaveVoice()
  const [name, setName] = useState(initial.name)
  const [guide, setGuide] = useState(initial.guide)
  const [examples, setExamples] = useState(initial.examples.join('\n\n'))
  const [topicIds, setTopicIds] = useState<number[]>(initial.topic_ids)

  const ownerOf = (topicId: number) => voices.find((v) => v.id !== id && v.topic_ids.includes(topicId))

  const submit = () =>
    save.mutate(
      {
        id,
        data: {
          name,
          guide,
          examples: examples.split(/\n\s*\n/).map((e) => e.trim()).filter(Boolean),
          topic_ids: topicIds,
          sources: initial.sources,
        },
      },
      { onSuccess: onClose },
    )

  return (
    <div className="space-y-4">
      <label className="flex flex-col gap-2">
        <span className="font-medium text-ink">{t('voices.editor.name')}</span>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder={t('voices.editor.namePlaceholder')} className={fieldClass} />
      </label>
      <label className="flex flex-col gap-2">
        <span className="font-medium text-ink">{t('voices.editor.guide')}</span>
        <textarea value={guide} onChange={(e) => setGuide(e.target.value)} rows={9} placeholder={t('voices.editor.guidePlaceholder')} className={fieldClass} />
        <span className="text-xs text-muted">{t('voices.editor.guideHint')}</span>
      </label>
      <label className="flex flex-col gap-2">
        <span className="font-medium text-ink">{t('voices.editor.examples')}</span>
        <textarea value={examples} onChange={(e) => setExamples(e.target.value)} rows={5} placeholder={t('voices.editor.examplesPlaceholder')} className={fieldClass} />
        <span className="text-xs text-muted">{t('voices.editor.examplesHint')}</span>
      </label>
      <fieldset className="space-y-2">
        <legend className="font-medium text-ink">{t('voices.editor.topics')}</legend>
        <p className="text-xs text-muted">{t('voices.editor.topicsHint')}</p>
        {topics.length === 0 ? (
          <p className="text-sm text-muted">{t('voices.editor.noTopics')}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {topics.map((tp) => {
              const on = topicIds.includes(tp.id)
              const owner = ownerOf(tp.id)
              return (
                <label
                  key={tp.id}
                  className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
                    on ? 'border-accent bg-surface-raised text-ink' : 'border-line text-muted'
                  }`}
                  title={owner && !on ? t('voices.editor.topicTaken', { name: owner.name }) : undefined}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => setTopicIds(on ? topicIds.filter((x) => x !== tp.id) : [...topicIds, tp.id])}
                    className="size-3.5 accent-[var(--color-accent)]"
                  />
                  {tp.name}
                  {owner && !on && <span className="text-xs">({owner.name})</span>}
                </label>
              )
            })}
          </div>
        )}
      </fieldset>
      {initial.sources.length > 0 && (
        <p className="text-xs text-muted">{t('voices.editor.sources', { files: initial.sources.join(', ') })}</p>
      )}
      {save.isError && <p className="text-red-400">{errorMessage(save.error)}</p>}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="rounded-full border border-line px-4 py-2 text-ink hover:bg-surface-raised">
          {t('common.cancel')}
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={!name.trim() || save.isPending}
          className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-50"
        >
          {t('common.save')}
        </button>
      </div>
    </div>
  )
}

/** Documents → the AI reads their voice → editable suggestion. */
function LearnFromDocuments({ onSuggestion }: { onSuggestion: (voice: VoiceSuggestion) => void }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: settings } = useSettings()
  const docs = useDocuments()
  const [mode, setMode] = useState<AiMode | null>(null)
  const flow = useAiFlow<never>({
    start: (m) => aiPost('/voices/analyze', { documents: docs.payload, mode: m }),
    parse: (text) => aiPost('/voices/analyze/parse', { names: docs.documents.map((d) => d.name), text }),
    onDone: (envelope) => {
      const voice = (envelope as unknown as { voice?: VoiceSuggestion }).voice
      if (voice) onSuggestion(voice)
    },
  })

  if (flow.phase === 'handoff' && flow.handoff) {
    return <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
  }
  return (
    <div className="space-y-4">
      <p className="text-muted">{t('voices.learn.hint')}</p>
      <DocumentsPicker docs={docs} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <AiModeSelect value={mode ?? settings?.default_ai ?? 'chat'} onChange={setMode} />
        </div>
        <button
          type="button"
          disabled={!docs.documents.length || docs.reading || flow.busy}
          onClick={() => flow.run(mode ?? settings?.default_ai ?? 'chat')}
          className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-semibold text-on-accent disabled:opacity-50"
        >
          {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FileSearch className="size-4" aria-hidden />}
          {flow.busy ? t('ai.working') : t('voices.learn.analyze')}
        </button>
      </div>
      {flow.error !== null && <p className="text-red-400">{errorMessage(flow.error)}</p>}
    </div>
  )
}

type Dialog =
  | { kind: 'learn' }
  | { kind: 'edit'; id: number | null; initial: VoiceProfileInput }
  | null

export function VoicesPage() {
  const { t } = useTranslation()
  const { data: voices = [], isLoading } = useVoices()
  const { data: topics = [] } = useTopics()
  const remove = useDeleteVoice()
  const [dialog, setDialog] = useState<Dialog>(null)
  const topicName = (id: number) => topics.find((tp) => tp.id === id)?.name

  const edit = (v: VoiceProfile) =>
    setDialog({ kind: 'edit', id: v.id, initial: { name: v.name, guide: v.guide, examples: v.examples, topic_ids: v.topic_ids, sources: v.sources } })

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('nav.voices')}</h1>
          <p className="mt-1 max-w-prose text-muted">{t('voices.subtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDialog({ kind: 'learn' })}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-semibold text-on-accent"
          >
            <FileSearch className="size-4" aria-hidden />
            {t('voices.fromDocuments')}
          </button>
          <button
            type="button"
            onClick={() => setDialog({ kind: 'edit', id: null, initial: EMPTY })}
            className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2.5 font-semibold text-ink shadow-card hover:bg-surface-raised"
          >
            <Plus className="size-4" aria-hidden />
            {t('voices.manual')}
          </button>
        </div>
      </div>

      {!isLoading && voices.length === 0 && (
        <Card title={t('voices.empty.title')}>
          <p className="max-w-prose text-muted">{t('voices.empty.text')}</p>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {voices.map((v) => (
          <article key={v.id} className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-card">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold text-ink">{v.name}</h2>
              <div className="flex gap-1">
                <button type="button" onClick={() => edit(v)} aria-label={t('voices.edit', { name: v.name })} className="rounded-full p-1.5 text-muted hover:bg-surface-raised hover:text-ink">
                  <Pencil className="size-4" aria-hidden />
                </button>
                <button
                  type="button"
                  onClick={() => window.confirm(t('voices.confirmDelete', { name: v.name })) && remove.mutate(v.id)}
                  aria-label={t('voices.delete', { name: v.name })}
                  className="rounded-full p-1.5 text-muted hover:bg-surface-raised hover:text-ink"
                >
                  <Trash2 className="size-4" aria-hidden />
                </button>
              </div>
            </div>
            {v.guide && <p className="line-clamp-5 whitespace-pre-line text-sm text-ink/90">{v.guide}</p>}
            {v.examples[0] && (
              <p className="flex gap-2 text-sm italic text-muted">
                <Quote className="mt-0.5 size-4 shrink-0 text-accent-text" aria-hidden />
                {v.examples[0]}
              </p>
            )}
            <p className="mt-auto text-sm text-accent-text">
              {v.topic_ids.length
                ? t('voices.usedFor', { topics: v.topic_ids.map(topicName).filter(Boolean).join(', ') })
                : t('voices.notLinked')}
            </p>
          </article>
        ))}
      </div>

      {dialog?.kind === 'learn' && (
        <Modal title={t('voices.fromDocuments')} onClose={() => setDialog(null)} wide>
          <LearnFromDocuments onSuggestion={(voice) => setDialog({ kind: 'edit', id: null, initial: { ...voice, topic_ids: [] } })} />
        </Modal>
      )}
      {dialog?.kind === 'edit' && (
        <Modal title={dialog.id === null ? t('voices.newTitle') : t('voices.editTitle')} onClose={() => setDialog(null)} wide>
          <VoiceEditor id={dialog.id} initial={dialog.initial} onClose={() => setDialog(null)} />
        </Modal>
      )}
    </div>
  )
}
