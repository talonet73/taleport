import { ArrowLeft, Plus, Sparkles, Trash2 } from 'lucide-react'
import { type ReactNode, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { useSaveTopic, useTopic, useTopicsMeta } from '../../api/hooks'
import {
  LANGUAGES,
  type Language,
  PLATFORMS,
  SOURCE_KINDS,
  type SourceKind,
  type Topic,
  type TopicData,
  type TopicSuggestion,
} from '../../api/types'
import { Card } from '../../components/Card'
import { TagInput } from '../../components/TagInput'
import { Toggle } from '../../components/Toggle'
import { useErrorMessage } from '../../components/useErrorMessage'
import { countryName } from './editionLabel'
import { TopicAiDialog } from './TopicAiDialog'
import { TopicItems } from './TopicItems'

const EMPTY_TOPIC: TopicData = {
  name: '',
  description: '',
  active: true,
  editions: ['it-IT'],
  keywords: {},
  exclude: [],
  hashtags: [],
  sources: [],
  audience: '',
  tone: '',
  platforms: [],
  style_examples: [],
}

const inputClass =
  'w-full rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none placeholder:text-muted focus:border-accent'

export function TopicEditor() {
  const { id } = useParams()
  const topicId = id ? Number(id) : undefined
  const { data: topic } = useTopic(topicId)
  const { t } = useTranslation()
  const navigate = useNavigate()
  const save = useSaveTopic()
  const errorMessage = useErrorMessage()
  const [draft, setDraft] = useState<TopicData>(EMPTY_TOPIC)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  useEffect(() => {
    if (topic) {
      const { id: _id, position: _p, created_at: _c, updated_at: _u, items_today: _i, ...data } = topic
      setDraft(data)
    }
  }, [topic])

  const update = (changes: Partial<TopicData>) => {
    setDraft((current) => ({ ...current, ...changes }))
    setSavedAt(null)
  }

  const submit = () =>
    save.mutate(
      { id: topicId, data: draft },
      {
        onSuccess: (saved) => {
          setSavedAt(Date.now())
          if (!topicId) navigate(`/topics/${saved.id}`, { replace: true })
        },
      },
    )

  if (topicId && !topic) return null

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to="/topics"
          aria-label={t('common.back')}
          className="rounded-full p-2 text-muted hover:bg-surface hover:text-ink"
        >
          <ArrowLeft className="size-5" aria-hidden />
        </Link>
        <h1 className="text-3xl font-bold text-ink">
          {topicId ? draft.name || t('topics.untitled') : t('topics.new')}
        </h1>
      </div>

      <GeneralSection draft={draft} update={update} />
      <EditionsSection draft={draft} update={update} />
      <KeywordsSection draft={draft} update={update} />
      <SourcesSection draft={draft} update={update} />
      <AudienceSection draft={draft} update={update} />
      <StyleSection draft={draft} update={update} />
      {topicId && <TopicItems topicId={topicId} />}

      {/* Left-aligned so it never sits under the scan progress panel (bottom right). */}
      <div className="sticky bottom-4 z-10 flex w-fit items-center gap-3 rounded-full border border-line bg-surface-raised px-4 py-2 shadow-card">
        <button
          type="button"
          onClick={submit}
          disabled={save.isPending}
          className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-50"
        >
          {t('common.save')}
        </button>
        <Link to="/topics" className="rounded-full px-4 py-2 font-medium text-ink hover:bg-surface">
          {t('common.cancel')}
        </Link>
        {save.isError && <span className="text-red-400">{errorMessage(save.error)}</span>}
        {savedAt && !save.isError && <span className="text-accent-text">{t('settings.saved')}</span>}
      </div>
    </div>
  )
}

/** The essential fields of a new topic, for the first-run wizard (full editor: Topics). */
export function NewTopicForm({ onSaved }: { onSaved: (topic: Topic) => void }) {
  const { t } = useTranslation()
  const save = useSaveTopic()
  const errorMessage = useErrorMessage()
  const [draft, setDraft] = useState<TopicData>(EMPTY_TOPIC)
  const update = (changes: Partial<TopicData>) => setDraft((current) => ({ ...current, ...changes }))

  return (
    <div className="space-y-6">
      <GeneralSection draft={draft} update={update} />
      <EditionsSection draft={draft} update={update} />
      <KeywordsSection draft={draft} update={update} />
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => save.mutate({ data: draft }, { onSuccess: onSaved })}
          disabled={save.isPending || !draft.name.trim()}
          className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-50"
        >
          {t('welcome.topic.save')}
        </button>
        {save.isError && <span className="text-red-400">{errorMessage(save.error)}</span>}
      </div>
    </div>
  )
}

interface SectionProps {
  draft: TopicData
  update: (changes: Partial<TopicData>) => void
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="text-sm text-muted">{hint}</span>}
    </div>
  )
}

/** Fill the draft from an AI proposal: text fields and keywords replaced, lists merged. */
function applySuggestion(draft: TopicData, s: TopicSuggestion): Partial<TopicData> {
  const merge = <T,>(a: T[], b: T[], key: (x: T) => string) => {
    const seen = new Set(a.map(key))
    return [...a, ...b.filter((x) => !seen.has(key(x)) && seen.add(key(x)))]
  }
  return {
    name: s.name || draft.name,
    description: s.description || draft.description,
    audience: s.audience || draft.audience,
    tone: s.tone || draft.tone,
    keywords: { ...draft.keywords, ...s.keywords },
    exclude: merge(draft.exclude, s.exclude, (x) => x.toLowerCase()),
    hashtags: merge(draft.hashtags, s.hashtags.map((h) => h.replace(/^#/, '')), (x) => x.toLowerCase()),
    sources: merge(draft.sources, s.sources, (x) => `${x.kind}:${x.value.toLowerCase()}`),
    platforms: s.platforms.length ? s.platforms : draft.platforms,
  }
}

function GeneralSection({ draft, update }: SectionProps) {
  const { t } = useTranslation()
  const [aiOpen, setAiOpen] = useState(false)
  return (
    <Card
      title={t('topics.sections.general')}
      actions={
        <button
          type="button"
          onClick={() => setAiOpen(true)}
          className="flex items-center gap-2 rounded-full bg-accent-gradient px-4 py-2 font-semibold text-on-accent"
        >
          <Sparkles className="size-4" aria-hidden />
          {t('topics.createWithAi')}
        </button>
      }
    >
      {aiOpen && (
        <TopicAiDialog
          editions={draft.editions}
          onApply={(s) => update(applySuggestion(draft, s))}
          onClose={() => setAiOpen(false)}
        />
      )}
      <div className="space-y-5">
        <label className="block">
          <Field label={t('topics.fields.name')}>
            <input
              value={draft.name}
              maxLength={80}
              onChange={(e) => update({ name: e.target.value })}
              placeholder={t('topics.placeholders.name')}
              className={inputClass}
            />
          </Field>
        </label>
        <label className="block">
          <Field label={t('topics.fields.description')}>
            <textarea
              value={draft.description}
              rows={3}
              onChange={(e) => update({ description: e.target.value })}
              placeholder={t('topics.placeholders.description')}
              className={inputClass}
            />
          </Field>
        </label>
        <label className="flex items-center gap-3">
          <Toggle
            checked={draft.active}
            onChange={(active) => update({ active })}
            label={t('topics.fields.active')}
          />
          <span className="text-ink">{t('topics.fields.active')}</span>
        </label>
      </div>
    </Card>
  )
}

function EditionsSection({ draft, update }: SectionProps) {
  const { t, i18n } = useTranslation()
  const { data: meta } = useTopicsMeta()
  const toggle = (code: string) =>
    update({
      editions: draft.editions.includes(code)
        ? draft.editions.filter((c) => c !== code)
        : [...draft.editions, code],
    })

  return (
    <Card title={t('topics.sections.editions')} description={t('topics.hints.editions')}>
      <div className="grid gap-5 md:grid-cols-3">
        {LANGUAGES.map((language) => (
          <fieldset key={language} className="space-y-2">
            <legend className="mb-2 font-medium text-ink">{t(`languages.${language}`)}</legend>
            {meta?.editions
              .filter((e) => e.language === language)
              .map((edition) => (
                <label key={edition.code} className="flex items-center gap-2 text-ink">
                  <input
                    type="checkbox"
                    checked={draft.editions.includes(edition.code)}
                    onChange={() => toggle(edition.code)}
                    className="size-4 accent-cyan"
                  />
                  {countryName(edition.country, i18n.language)}
                </label>
              ))}
          </fieldset>
        ))}
      </div>
    </Card>
  )
}

function selectedLanguages(editions: string[]): Language[] {
  return LANGUAGES.filter((lang) => editions.some((code) => code.startsWith(`${lang}-`)))
}

function KeywordsSection({ draft, update }: SectionProps) {
  const { t } = useTranslation()
  const languages = selectedLanguages(draft.editions)

  return (
    <Card title={t('topics.sections.keywords')} description={t('topics.hints.keywords')}>
      <div className="space-y-5">
        {languages.length === 0 && <p className="text-muted">{t('topics.hints.pickEdition')}</p>}
        {languages.map((language) => (
          <Field key={language} label={t('topics.fields.keywordsIn', { language: t(`languages.${language}`) })}>
            <TagInput
              values={draft.keywords[language] ?? []}
              onChange={(values) => update({ keywords: { ...draft.keywords, [language]: values } })}
              placeholder={t('topics.placeholders.keywords')}
              label={t('topics.fields.keywordsIn', { language: t(`languages.${language}`) })}
            />
          </Field>
        ))}
        <Field label={t('topics.fields.exclude')} hint={t('topics.hints.exclude')}>
          <TagInput
            values={draft.exclude}
            onChange={(exclude) => update({ exclude })}
            placeholder={t('topics.placeholders.exclude')}
            label={t('topics.fields.exclude')}
          />
        </Field>
        <Field label={t('topics.fields.hashtags')}>
          <TagInput
            values={draft.hashtags}
            onChange={(hashtags) => update({ hashtags })}
            placeholder={t('topics.placeholders.hashtags')}
            label={t('topics.fields.hashtags')}
            prefix="#"
          />
        </Field>
      </div>
    </Card>
  )
}

function SourcesSection({ draft, update }: SectionProps) {
  const { t } = useTranslation()
  const [kind, setKind] = useState<SourceKind>('rss')
  const [value, setValue] = useState('')

  const add = () => {
    if (!value.trim()) return
    update({ sources: [...draft.sources, { kind, value: value.trim() }] })
    setValue('')
  }

  return (
    <Card title={t('topics.sections.sources')} description={t('topics.hints.sources')}>
      {draft.sources.length > 0 && (
        <ul className="mb-4 divide-y divide-line rounded-xl border border-line">
          {draft.sources.map((source, index) => (
            <li key={`${source.kind}:${source.value}`} className="flex items-center gap-3 px-4 py-2.5">
              <span className="w-36 shrink-0 text-sm text-muted">{t(`topics.sourceKinds.${source.kind}`)}</span>
              <span className="min-w-0 flex-1 truncate text-ink">{source.value}</span>
              <button
                type="button"
                onClick={() => update({ sources: draft.sources.filter((_, i) => i !== index) })}
                aria-label={t('common.removeItem', { item: source.value })}
                className="rounded-lg p-1.5 text-muted hover:bg-surface-raised hover:text-ink"
              >
                <Trash2 className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as SourceKind)}
          aria-label={t('topics.fields.sourceKind')}
          className={`${inputClass} w-48`}
        >
          {SOURCE_KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`topics.sourceKinds.${k}`)}
            </option>
          ))}
        </select>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              add()
            }
          }}
          placeholder={t(`topics.placeholders.source_${kind}`)}
          aria-label={t('topics.fields.sourceValue')}
          className={inputClass}
        />
        <button
          type="button"
          onClick={add}
          className="flex shrink-0 items-center gap-2 rounded-xl border border-line px-4 font-medium text-ink hover:bg-surface-raised"
        >
          <Plus className="size-4" aria-hidden />
          {t('common.add')}
        </button>
      </div>
    </Card>
  )
}

function AudienceSection({ draft, update }: SectionProps) {
  const { t } = useTranslation()
  const togglePlatform = (p: (typeof PLATFORMS)[number]) =>
    update({
      platforms: draft.platforms.includes(p)
        ? draft.platforms.filter((x) => x !== p)
        : [...draft.platforms, p],
    })

  return (
    <Card title={t('topics.sections.audience')}>
      <div className="space-y-5">
        <label className="block">
          <Field label={t('topics.fields.audience')}>
            <textarea
              value={draft.audience}
              rows={2}
              onChange={(e) => update({ audience: e.target.value })}
              placeholder={t('topics.placeholders.audience')}
              className={inputClass}
            />
          </Field>
        </label>
        <label className="block">
          <Field label={t('topics.fields.tone')}>
            <input
              value={draft.tone}
              onChange={(e) => update({ tone: e.target.value })}
              placeholder={t('topics.placeholders.tone')}
              className={inputClass}
            />
          </Field>
        </label>
        <Field label={t('topics.fields.platforms')}>
          <div className="flex flex-wrap gap-2">
            {PLATFORMS.map((p) => {
              const active = draft.platforms.includes(p)
              return (
                <button
                  key={p}
                  type="button"
                  aria-pressed={active}
                  onClick={() => togglePlatform(p)}
                  className={`rounded-full px-4 py-2 font-medium ${
                    active
                      ? 'bg-accent-gradient text-on-accent'
                      : 'border border-line bg-surface-raised text-ink hover:border-accent'
                  }`}
                >
                  {t(`platforms.${p}`)}
                </button>
              )
            })}
          </div>
        </Field>
      </div>
    </Card>
  )
}

function StyleSection({ draft, update }: SectionProps) {
  const { t } = useTranslation()
  const { data: meta } = useTopicsMeta()
  const max = meta?.max_style_examples ?? 5
  const examples = draft.style_examples

  return (
    <Card title={t('topics.sections.style')} description={t('topics.hints.style', { max })}>
      <div className="space-y-3">
        {examples.map((text, index) => (
          <div key={index} className="flex gap-2">
            <textarea
              value={text}
              rows={4}
              onChange={(e) =>
                update({ style_examples: examples.map((x, i) => (i === index ? e.target.value : x)) })
              }
              aria-label={t('topics.fields.styleExample', { n: index + 1 })}
              placeholder={t('topics.placeholders.style')}
              className={inputClass}
            />
            <button
              type="button"
              onClick={() => update({ style_examples: examples.filter((_, i) => i !== index) })}
              aria-label={t('common.removeItem', { item: t('topics.fields.styleExample', { n: index + 1 }) })}
              className="self-start rounded-lg p-2 text-muted hover:bg-surface-raised hover:text-ink"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </div>
        ))}
        {examples.length < max && (
          <button
            type="button"
            onClick={() => update({ style_examples: [...examples, ''] })}
            className="flex items-center gap-2 rounded-xl border border-dashed border-line px-4 py-2.5 font-medium text-ink hover:bg-surface-raised"
          >
            <Plus className="size-4" aria-hidden />
            {t('topics.addStyleExample')}
          </button>
        )}
      </div>
    </Card>
  )
}
