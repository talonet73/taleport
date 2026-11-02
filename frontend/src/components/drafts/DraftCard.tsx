import {
  BarChart3,
  CalendarPlus,
  CheckCircle2,
  ClipboardCopy,
  ExternalLink,
  ImageIcon,
  Pencil,
  RefreshCw,
  Trash2,
  TriangleAlert,
} from 'lucide-react'
import type { TFunction } from 'i18next'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { copyToClipboard, openExternal, useDraftAction } from '../../api/hooks'
import type { Draft } from '../../api/types'
import { ResultsForm, ResultsLine } from '../results/ResultsForm'
import { useErrorMessage } from '../useErrorMessage'
import { RegenerateDialog } from './RegenerateDialog'

const buttonClass =
  'flex items-center gap-1.5 rounded-xl border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-raised disabled:opacity-50'

export function DraftCard({ draft }: { draft: Draft }) {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const action = useDraftAction()
  const [copied, setCopied] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(draft.text)
  const [panel, setPanel] = useState<'schedule' | 'publish' | 'regenerate' | 'results' | null>(null)
  const [when, setWhen] = useState(draft.scheduled_at ?? defaultSchedule())
  const [url, setUrl] = useState('')

  const copy = (key: string, value: string) =>
    copyToClipboard(value).then((r) => r.copied && setCopied(key))

  const run = (path: string, method: string, body?: unknown, after?: () => void) =>
    action.mutate({ path: `/drafts/${draft.id}${path}`, method, body }, { onSuccess: () => after?.() })

  return (
    <article className="rounded-card border border-line bg-surface p-5 shadow-card">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-accent-gradient px-3 py-0.5 text-sm font-semibold text-on-accent">
          {t(`platforms.${draft.platform}`)}
        </span>
        <span className="rounded-full bg-surface-raised px-2.5 py-0.5 text-sm text-ink">
          {t(`languages.${draft.language}`)}
        </span>
        <span className="text-sm text-muted">
          {draft.series_index
            ? t('drafts.seriesIndex', { n: draft.series_index })
            : t('drafts.variant', { n: draft.variant })}
          {' · '}
          {draft.source_label}
        </span>
        <span className="ml-auto text-sm font-medium text-accent-text">{statusLabel(draft, t, i18n.language)}</span>
      </header>

      {editing ? (
        <div className="space-y-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={12}
            aria-label={t('drafts.editText')}
            className="w-full rounded-xl border border-line bg-surface-raised px-3 py-2 text-[15px] text-ink outline-none focus:border-accent"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => run('', 'PATCH', { text }, () => setEditing(false))}
              className="rounded-xl bg-accent-gradient px-4 py-1.5 font-semibold text-on-accent"
            >
              {t('common.save')}
            </button>
            <button type="button" onClick={() => setEditing(false)} className={buttonClass}>
              {t('common.cancel')}
            </button>
          </div>
        </div>
      ) : draft.edited ? (
        <p className="max-w-prose text-[15px] leading-relaxed whitespace-pre-wrap text-ink">{draft.text}</p>
      ) : (
        <StructuredView draft={draft} onCopy={copy} copied={copied} />
      )}

      {draft.fact_warnings.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-400/40 bg-amber-400/10 p-3">
          <p className="mb-1 flex items-center gap-2 font-semibold text-ink">
            <TriangleAlert className="size-4 text-amber-500" aria-hidden />
            {t('drafts.factCheck')}
          </p>
          <ul className="flex flex-wrap gap-1.5 text-sm">
            {draft.fact_warnings.map((w) => (
              <li key={`${w.kind}:${w.value}`} className="rounded-full bg-surface px-2.5 py-0.5 text-ink">
                {t(`drafts.warning.${w.kind}`)}: «{w.value}»
              </li>
            ))}
          </ul>
        </div>
      )}

      {(draft.image_idea || draft.image_prompt) && (
        <div className="mt-4 rounded-xl bg-surface-raised p-3 text-sm">
          <p className="flex items-center gap-2 font-semibold text-ink">
            <ImageIcon className="size-4 text-accent-text" aria-hidden />
            {t('drafts.imageIdea')}
          </p>
          {draft.image_idea && <p className="mt-1 text-ink">{draft.image_idea}</p>}
          {draft.image_prompt && (
            <div className="mt-2 flex items-start gap-2">
              <code className="flex-1 text-muted">{draft.image_prompt}</code>
              <button type="button" onClick={() => copy('prompt', draft.image_prompt)} className={buttonClass}>
                <ClipboardCopy className="size-3.5" aria-hidden />
                {copied === 'prompt' ? t('drafts.copied') : t('drafts.copyPrompt')}
              </button>
            </div>
          )}
        </div>
      )}

      {draft.sources.length > 0 && (
        <div className="mt-4 text-sm">
          <p className="mb-1 font-semibold text-ink">{t('drafts.sources')}</p>
          <ul className="space-y-0.5">
            {draft.sources.map((s) => (
              <li key={s.url}>
                <button type="button" onClick={() => openExternal(s.url)} className="text-left text-muted hover:underline">
                  {s.title}
                  <ExternalLink className="ml-1 inline size-3" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <footer className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
        <button
          type="button"
          onClick={() => copy('text', draft.text)}
          className="flex items-center gap-1.5 rounded-xl bg-accent-gradient px-3 py-1.5 text-sm font-semibold text-on-accent"
        >
          <ClipboardCopy className="size-4" aria-hidden />
          {copied === 'text' ? t('drafts.copied') : t('drafts.copy')}
        </button>
        <button type="button" onClick={() => setPanel('regenerate')} className={buttonClass}>
          <RefreshCw className="size-4" aria-hidden />
          {t('drafts.regenerate')}
        </button>
        <button
          type="button"
          onClick={() => {
            setText(draft.text)
            setEditing(true)
          }}
          className={buttonClass}
        >
          <Pencil className="size-4" aria-hidden />
          {t('drafts.edit')}
        </button>
        <button type="button" onClick={() => setPanel(panel === 'schedule' ? null : 'schedule')} className={buttonClass}>
          <CalendarPlus className="size-4" aria-hidden />
          {t('drafts.schedule')}
        </button>
        {draft.status === 'published' ? (
          <>
            <button type="button" onClick={() => setPanel(panel === 'results' ? null : 'results')} className={buttonClass}>
              <BarChart3 className="size-4" aria-hidden />
              {t('results.enter')}
            </button>
            <button type="button" onClick={() => run('/publish', 'DELETE')} className={buttonClass}>
              {t('drafts.unpublish')}
            </button>
          </>
        ) : (
          <button type="button" onClick={() => setPanel(panel === 'publish' ? null : 'publish')} className={buttonClass}>
            <CheckCircle2 className="size-4" aria-hidden />
            {t('drafts.markPublished')}
          </button>
        )}
        <button
          type="button"
          onClick={() => run('', 'DELETE')}
          aria-label={t('drafts.delete')}
          className="ml-auto rounded-xl p-2 text-muted hover:bg-surface-raised hover:text-ink"
        >
          <Trash2 className="size-4" aria-hidden />
        </button>
      </footer>

      {panel === 'schedule' && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            type="datetime-local"
            value={when}
            onChange={(e) => setWhen(e.target.value)}
            aria-label={t('drafts.scheduleWhen')}
            className="rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-ink"
          />
          <button type="button" onClick={() => run('/schedule', 'PUT', { scheduled_at: when }, () => setPanel(null))} className={buttonClass}>
            {t('common.save')}
          </button>
          {draft.scheduled_at && (
            <button type="button" onClick={() => run('/schedule', 'PUT', { scheduled_at: null }, () => setPanel(null))} className={buttonClass}>
              {t('drafts.unschedule')}
            </button>
          )}
        </div>
      )}
      {panel === 'publish' && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={t('drafts.publishedUrl')}
            aria-label={t('drafts.publishedUrl')}
            className="w-80 rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-ink placeholder:text-muted"
          />
          <button type="button" onClick={() => run('/publish', 'POST', { url: url.trim() || null }, () => setPanel(null))} className={buttonClass}>
            {t('drafts.confirmPublished')}
          </button>
        </div>
      )}
      {draft.status === 'published' && panel !== 'results' && <div className="mt-3"><ResultsLine results={draft.results} /></div>}
      {panel === 'results' && (
        <div className="mt-3">
          <ResultsForm draftId={draft.id} initial={draft.results} onDone={() => setPanel(null)} />
        </div>
      )}
      {panel === 'regenerate' && <RegenerateDialog draftId={draft.id} onClose={() => setPanel(null)} />}
      {action.isError && <p className="mt-2 text-sm text-red-400">{errorMessage(action.error)}</p>}
    </article>
  )
}

function defaultSchedule(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  d.setHours(9, 0, 0, 0)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T09:00`
}

function statusLabel(draft: Draft, t: TFunction, lang: string): string {
  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(lang, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
  if (draft.status === 'published' && draft.publication)
    return t('drafts.status.published', { date: fmt(draft.publication.published_at) })
  if (draft.status === 'scheduled' && draft.scheduled_at)
    return t('drafts.status.scheduled', { date: fmt(draft.scheduled_at) })
  return t('drafts.status.draft')
}

function StructuredView({
  draft,
  onCopy,
  copied,
}: {
  draft: Draft
  onCopy: (key: string, value: string) => void
  copied: string | null
}) {
  const { t } = useTranslation()
  const c = draft.content
  // Hashtags the AI already wrote inside the text are not repeated below it.
  const extraTags = c.hashtags.filter((h) => !c.text.toLowerCase().includes(`#${h.toLowerCase()}`))
  const paragraph = 'max-w-prose text-[15px] leading-relaxed whitespace-pre-wrap text-ink'
  return (
    <div className="space-y-3">
      {c.title && <h3 className="text-lg font-semibold text-ink">{c.title}</h3>}
      {c.hook && draft.platform !== 'tiktok' && !c.text.startsWith(c.hook) && (
        <p className={`${paragraph} font-semibold`}>{c.hook}</p>
      )}
      {draft.platform === 'tiktok' && (
        <>
          {c.hook && (
            <p className="text-ink">
              <span className="font-semibold">{t('drafts.hook')}:</span> {c.hook}
            </p>
          )}
          {c.script.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted">
                  <th className="py-1 pr-2 font-medium">{t('drafts.time')}</th>
                  <th className="py-1 pr-2 font-medium">{t('drafts.scene')}</th>
                  <th className="py-1 font-medium">{t('drafts.voiceover')}</th>
                </tr>
              </thead>
              <tbody>
                {c.script.map((line, i) => (
                  <tr key={i} className="border-t border-line align-top text-ink">
                    <td className="py-1.5 pr-2 whitespace-nowrap">{line.time}</td>
                    <td className="py-1.5 pr-2 text-muted">{line.scene}</td>
                    <td className="py-1.5">{line.voiceover}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
      {c.text && <p className={paragraph}>{c.text}</p>}
      {extraTags.length > 0 && <p className="text-accent-text">{extraTags.map((h) => `#${h}`).join(' ')}</p>}
      {c.carousel.length > 0 && (
        <div>
          <div className="mb-1 flex items-center justify-between">
            <p className="font-semibold text-ink">{t('drafts.carousel')}</p>
            <button
              type="button"
              onClick={() => onCopy('carousel', c.carousel.map((s, i) => `${i + 1}. ${s}`).join('\n'))}
              className="text-sm text-muted hover:text-ink"
            >
              {copied === 'carousel' ? t('drafts.copied') : t('drafts.copySlides')}
            </button>
          </div>
          <ol className="grid gap-2 sm:grid-cols-2">
            {c.carousel.map((slide, i) => (
              <li key={i} className="rounded-xl bg-surface-raised p-3 text-sm text-ink">
                <span className="mr-1 font-semibold text-accent-text">{i + 1}.</span>
                {slide}
              </li>
            ))}
          </ol>
        </div>
      )}
      {c.outline.length > 0 && (
        <div>
          <p className="mb-1 font-semibold text-ink">{t('drafts.outline')}</p>
          <ol className="list-decimal space-y-0.5 pl-5 text-ink">
            {c.outline.map((o, i) => (
              <li key={i}>{o}</li>
            ))}
          </ol>
        </div>
      )}
      {c.thumbnail_idea && (
        <p className="text-ink">
          <span className="font-semibold">{t('drafts.thumbnail')}:</span> {c.thumbnail_idea}
        </p>
      )}
    </div>
  )
}
