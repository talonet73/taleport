import { FileDown, FolderOpen, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { openReport, type ReportKind, useGenerateReport } from '../../api/reports'
import { useErrorMessage } from '../useErrorMessage'

/** "Export PDF" for a screen: builds the report and offers to open the saved file. */
export function ExportPdfButton({ kind, body, disabled }: { kind: ReportKind; body: unknown; disabled?: boolean }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const generate = useGenerateReport()

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        type="button"
        disabled={disabled || generate.isPending}
        onClick={() => generate.mutate({ kind, body })}
        className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 font-semibold text-ink shadow-card hover:bg-surface-raised disabled:opacity-60"
      >
        {generate.isPending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <FileDown className="size-4" aria-hidden />
        )}
        {generate.isPending ? t('reports.generating') : t('reports.exportPdf')}
      </button>
      {generate.data && <SavedNotice file={generate.data} />}
      {generate.isError && <p className="text-sm text-red-400">{errorMessage(generate.error)}</p>}
    </div>
  )
}

/** The file just created, with "Open" and "Show in folder". */
export function SavedNotice({ file }: { file: { name: string } }) {
  const { t } = useTranslation()
  return (
    <p role="status" className="flex flex-wrap items-center justify-end gap-2 text-sm text-muted">
      <span>{t('reports.saved', { name: file.name })}</span>
      <button type="button" onClick={() => void openReport(file.name)} className="font-semibold text-accent-text hover:underline">
        {t('reports.open')}
      </button>
      <button
        type="button"
        onClick={() => void openReport(file.name, true)}
        className="flex items-center gap-1 text-accent-text hover:underline"
      >
        <FolderOpen className="size-3.5" aria-hidden />
        {t('reports.showFolder')}
      </button>
    </p>
  )
}
