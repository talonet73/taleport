import { ClipboardCheck, ClipboardCopy, ExternalLink, Info } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { copyToClipboard, openExternal } from '../../api/hooks'
import type { Handoff } from '../../api/types'
import { useErrorMessage } from '../useErrorMessage'

interface HandoffPanelProps {
  handoff: Handoff
  fallback: string | null
  error: unknown
  onSubmit: (text: string) => void
  submitLabel?: string
}

/** "Open in chat": the prompt is on the clipboard, the site is open, paste the answer here. */
export function HandoffPanel({ handoff, fallback, error, onSubmit, submitLabel }: HandoffPanelProps) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const [answer, setAnswer] = useState('')
  const [copied, setCopied] = useState(handoff.copied)
  const site = t(`ai.sites.${handoff.site}`)

  return (
    <div className="space-y-4">
      {fallback && (
        <p className="flex gap-2 rounded-xl bg-surface-raised p-3 text-sm text-ink">
          <Info className="mt-0.5 size-4 shrink-0 text-accent-text" aria-hidden />
          {t('ai.fallback', { reason: errorMessage({ code: fallback }) })}
        </p>
      )}
      <ol className="list-decimal space-y-1 pl-5 text-ink">
        <li>
          {copied ? t('ai.steps.copied') : t('ai.steps.copyFailed')}
          {handoff.prefilled && ` ${t('ai.steps.prefilled')}`}
        </li>
        <li>{t('ai.steps.send', { site })}</li>
        <li>{t('ai.steps.paste')}</li>
      </ol>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => openExternal(handoff.url)}
          className="flex items-center gap-2 rounded-full bg-accent-gradient px-4 py-2 font-semibold text-on-accent"
        >
          <ExternalLink className="size-4" aria-hidden />
          {t('ai.openSite', { site })}
        </button>
        <button
          type="button"
          onClick={() => copyToClipboard(handoff.prompt).then((r) => setCopied(r.copied))}
          className="flex items-center gap-2 rounded-full border border-line px-4 py-2 font-medium text-ink hover:bg-surface-raised"
        >
          {copied ? <ClipboardCheck className="size-4" aria-hidden /> : <ClipboardCopy className="size-4" aria-hidden />}
          {t('ai.copyAgain')}
        </button>
      </div>
      <details className="rounded-xl border border-line p-3">
        <summary className="cursor-pointer text-sm text-muted">{t('ai.showPrompt')}</summary>
        <pre className="mt-2 max-h-48 overflow-auto text-xs whitespace-pre-wrap text-muted">{handoff.prompt}</pre>
      </details>
      <label className="flex flex-col gap-2">
        <span className="font-medium text-ink">{t('ai.pasteHere')}</span>
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          aria-label={t('ai.pasteHere')}
          rows={8}
          className="rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent"
        />
      </label>
      {error !== null && <p className="text-red-400">{errorMessage(error)}</p>}
      <button
        type="button"
        disabled={!answer.trim()}
        onClick={() => onSubmit(answer)}
        className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-50"
      >
        {submitLabel ?? t('ai.useAnswer')}
      </button>
    </div>
  )
}
