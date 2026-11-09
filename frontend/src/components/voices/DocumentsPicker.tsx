import { FileText, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { DOCUMENT_EXTENSIONS, MAX_DOCUMENTS } from '../../api/voices'
import { DropZone } from '../DropZone'
import { useErrorMessage } from '../useErrorMessage'
import type { useDocuments } from './useDocuments'

/** Drop or choose up to 5 reference documents; shows what was read from each. */
export function DocumentsPicker({ docs }: { docs: ReturnType<typeof useDocuments> }) {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const number = new Intl.NumberFormat(i18n.language)
  const full = docs.documents.length >= MAX_DOCUMENTS

  return (
    <div className="space-y-3">
      {!full && (
        <DropZone
          compact={docs.documents.length > 0}
          accept={DOCUMENT_EXTENSIONS}
          busy={docs.reading}
          label={docs.reading ? t('voices.documents.reading') : t('voices.documents.drop')}
          hint={t('voices.documents.formats', { max: MAX_DOCUMENTS })}
          onFiles={(files) => void docs.add(files)}
        />
      )}
      {docs.error !== null && <p className="text-red-400">{errorMessage(docs.error)}</p>}
      {docs.documents.length > 0 && (
        <ul className="space-y-2">
          {docs.documents.map((d) => (
            <li key={d.name} className="flex items-center gap-3 rounded-xl bg-surface-raised px-3 py-2">
              <FileText className="size-4 shrink-0 text-accent-text" aria-hidden />
              <span className="min-w-0 flex-1 truncate text-ink" title={d.name}>
                {d.name}
              </span>
              <span className="text-sm text-muted">
                {t('voices.documents.characters', { value: number.format(d.characters) })}
                {d.truncated && ` · ${t('voices.documents.truncated')}`}
              </span>
              <button
                type="button"
                onClick={() => docs.remove(d.name)}
                aria-label={t('voices.documents.remove', { name: d.name })}
                className="rounded-full p-1 text-muted hover:bg-surface hover:text-ink"
              >
                <X className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
