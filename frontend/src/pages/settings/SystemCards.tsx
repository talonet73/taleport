import { Download, FileUp, Loader2, RefreshCw, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useSettings, useUpdateSettings } from '../../api/hooks'
import {
  type ImportPreview,
  type ImportResult,
  type LogLevel,
  openRelease,
  previewImport,
  useCheckUpdates,
  useCleanup,
  useExportBackup,
  useImportBackup,
  useLogActions,
  useLogs,
  useUpdates,
} from '../../api/system'
import { Card } from '../../components/Card'
import { Modal } from '../../components/Modal'
import { SavedNotice } from '../../components/reports/ExportPdfButton'
import { Toggle } from '../../components/Toggle'
import { useErrorMessage } from '../../components/useErrorMessage'

const fieldClass = 'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'
const buttonClass =
  'flex items-center gap-2 rounded-full border border-line px-4 py-1.5 text-sm font-semibold text-ink hover:bg-surface-raised disabled:opacity-60'

// -- backup and import ---------------------------------------------------------------

export function BackupCard() {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const backup = useExportBackup()
  return (
    <div id="backup">
      <Card title={t('system.backup.title')} description={t('system.backup.description')}>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => backup.mutate()} disabled={backup.isPending} className={buttonClass}>
            {backup.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Download className="size-4" aria-hidden />}
            {t('system.backup.export')}
          </button>
          <ImportButton />
        </div>
        {backup.data && (
          <div className="mt-3">
            <SavedNotice file={backup.data} />
          </div>
        )}
        {backup.isError && <p className="mt-2 text-sm text-red-400">{errorMessage(backup.error)}</p>}
        <p className="mt-3 max-w-prose text-sm text-muted">{t('system.backup.keysHint')}</p>
      </Card>
    </div>
  )
}

/** "Import from file": a full backup or a single shared topic; preview, then confirm. */
export function ImportButton({ label }: { label?: string }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const [file, setFile] = useState<{ name: string; text: string; preview: ImportPreview } | null>(null)
  const [error, setError] = useState<unknown>(null)

  return (
    <>
      <label className={`${buttonClass} relative cursor-pointer focus-within:border-accent`}>
        <FileUp className="size-4" aria-hidden />
        {label ?? t('system.backup.import')}
        <input
          type="file"
          accept=".json,application/json"
          className="sr-only"
          onChange={async (e) => {
            const chosen = e.target.files?.[0]
            e.target.value = ''
            if (!chosen) return
            setError(null)
            try {
              const text = await chosen.text()
              setFile({ name: chosen.name, text, preview: await previewImport(text) })
            } catch (err) {
              setError(err)
            }
          }}
        />
      </label>
      {error !== null && <p className="basis-full text-sm text-red-400">{errorMessage(error)}</p>}
      {file && <ImportDialog file={file} onClose={() => setFile(null)} />}
    </>
  )
}

function ImportDialog({
  file,
  onClose,
}: {
  file: { name: string; text: string; preview: ImportPreview }
  onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const run = useImportBackup()
  const [withSettings, setWithSettings] = useState(true)
  const { preview } = file
  const result: ImportResult | undefined = run.data

  return (
    <Modal title={t('system.import.title')} onClose={onClose}>
      <p className="text-ink">{file.name}</p>
      <p className="mb-4 text-sm text-muted">
        {t(preview.format === 'taleport-topic' ? 'system.import.kindTopic' : 'system.import.kindBackup')}
        {preview.created_at &&
          ` · ${new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(preview.created_at))}`}
        {preview.app_version && ` · TALeport ${preview.app_version}`}
      </p>
      {result ? (
        <div className="space-y-2 text-ink" role="status">
          <p>{t('system.import.doneTopics', { count: result.topics.length, names: result.topics.join(', ') })}</p>
          {result.settings && <p>{t('system.import.doneSettings')}</p>}
          {result.templates > 0 && <p>{t('system.import.doneTemplates', { count: result.templates })}</p>}
          {result.skipped.map((s) => (
            <p key={s.name} className="text-sm text-amber-500">
              {t(`system.import.skipped.${s.reason}`, { name: s.name })}
            </p>
          ))}
          <button type="button" onClick={onClose} className="mt-2 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent">
            {t('common.close')}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="font-medium text-ink">{t('system.import.topics', { count: preview.topics.length })}</p>
            {preview.topics.length > 0 && <p className="text-sm text-muted">{preview.topics.join(', ')}</p>}
            {preview.templates > 0 && <p className="text-sm text-muted">{t('system.import.templates', { count: preview.templates })}</p>}
          </div>
          {preview.has_settings && (
            <div className="flex items-start gap-3">
              <Toggle checked={withSettings} onChange={setWithSettings} label={t('system.import.withSettings')} />
              <div>
                <p className="text-ink">{t('system.import.withSettings')}</p>
                <p className="text-sm text-muted">{t('system.import.withSettingsHint')}</p>
              </div>
            </div>
          )}
          <p className="text-sm text-muted">{t('system.import.noOverwrite')}</p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={run.isPending}
              onClick={() => run.mutate({ text: file.text, settings: withSettings })}
              className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-60"
            >
              {t('system.import.confirm')}
            </button>
            <button type="button" onClick={onClose} className="rounded-full border border-line px-4 py-2 text-ink hover:bg-surface-raised">
              {t('common.cancel')}
            </button>
          </div>
          {run.isError && <p className="text-sm text-red-400">{errorMessage(run.error)}</p>}
        </div>
      )}
    </Modal>
  )
}

// -- updates -------------------------------------------------------------------------

export function UpdatesCard() {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const { data: status } = useUpdates()
  const check = useCheckUpdates()
  const [url, setUrl] = useState('')
  useEffect(() => setUrl(settings?.update_url ?? ''), [settings?.update_url])
  if (!settings || !status) return null

  return (
    <div id="updates">
      <Card title={t('system.updates.title')} description={t('system.updates.description')}>
        <div className="space-y-4">
          <p className="text-ink">{t('system.updates.current', { version: status.current })}</p>
          <label className="block text-sm font-medium text-ink">
            {t('system.updates.url')}
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onBlur={() => url.trim() !== settings.update_url && update.mutate({ update_url: url.trim() })}
              placeholder="https://api.github.com/repos/…/taleport/releases/latest"
              className={`${fieldClass} mt-1.5 block w-full max-w-2xl`}
            />
          </label>
          {update.isError && <p className="text-sm text-red-400">{errorMessage(update.error)}</p>}
          <div className="flex items-start gap-3">
            <Toggle checked={settings.check_updates} onChange={(v) => update.mutate({ check_updates: v })} label={t('system.updates.auto')} />
            <p className="text-ink">{t('system.updates.auto')}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" onClick={() => check.mutate()} disabled={!settings.update_url || check.isPending} className={buttonClass}>
              {check.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <RefreshCw className="size-4" aria-hidden />}
              {t('system.updates.check')}
            </button>
            {status.checked_at && (
              <span className="text-sm text-muted">
                {t('system.updates.checkedAt', {
                  date: new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(
                    new Date(status.checked_at),
                  ),
                })}
              </span>
            )}
          </div>
          {!settings.update_url && <p className="text-sm text-muted">{t('system.updates.notConfigured')}</p>}
          {check.isError && <p className="text-sm text-red-400">{errorMessage(check.error)}</p>}
          {status.latest && (
            <div className="rounded-xl bg-surface-raised p-4" role="status">
              {status.available ? (
                <>
                  <p className="font-semibold text-ink">{t('system.updates.available', { version: status.latest.version })}</p>
                  {status.latest.notes && (
                    <p className="mt-1 line-clamp-6 max-w-prose text-sm whitespace-pre-wrap text-muted">{status.latest.notes}</p>
                  )}
                  <button
                    type="button"
                    onClick={() => void openRelease()}
                    className="mt-3 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent"
                  >
                    {t('system.updates.open')}
                  </button>
                  <p className="mt-2 text-xs text-muted">{t('system.updates.manual')}</p>
                </>
              ) : (
                <p className="text-ink">{t('system.updates.upToDate')}</p>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

// -- error log -----------------------------------------------------------------------

export function ErrorLogCard() {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const [level, setLevel] = useState<LogLevel | ''>('')
  const { data } = useLogs(level)
  const { exportLog, clear } = useLogActions()
  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(iso))

  return (
    <div id="log">
      <Card
        title={t('system.log.title')}
        description={t('system.log.description')}
        actions={
          <div className="flex gap-2">
            <button type="button" onClick={() => exportLog.mutate()} disabled={exportLog.isPending} className={buttonClass}>
              <Download className="size-4" aria-hidden />
              {t('system.log.export')}
            </button>
            <button
              type="button"
              onClick={() => clear.mutate()}
              disabled={!data?.rows.length}
              aria-label={t('system.log.clear')}
              className="rounded-xl p-2 text-muted hover:bg-surface-raised hover:text-ink disabled:opacity-40"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </div>
        }
      >
        {exportLog.data && (
          <div className="mb-3">
            <SavedNotice file={exportLog.data} />
          </div>
        )}
        {exportLog.isError && <p className="mb-3 text-sm text-red-400">{errorMessage(exportLog.error)}</p>}
        <div role="radiogroup" aria-label={t('system.log.filter')} className="mb-3 flex flex-wrap gap-1">
          {(['', 'error', 'warning', 'info'] as const).map((value) => (
            <button
              key={value || 'all'}
              type="button"
              role="radio"
              aria-checked={level === value}
              onClick={() => setLevel(value)}
              className={`rounded-full px-3 py-1 text-sm font-medium ${
                level === value ? 'bg-accent-gradient text-on-accent' : 'border border-line text-ink hover:bg-surface-raised'
              }`}
            >
              {t(`system.log.levels.${value || 'all'}`)}
              {value && data ? ` (${data.counts[value]})` : ''}
            </button>
          ))}
        </div>
        {!data?.rows.length ? (
          <p className="text-muted">{t('system.log.empty')}</p>
        ) : (
          <ul className="max-h-96 divide-y divide-line overflow-y-auto text-sm">
            {data.rows.map((row) => (
              <li key={row.id} className="flex gap-3 py-2">
                <span
                  className={`mt-0.5 h-fit shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                    row.level === 'error'
                      ? 'bg-red-500/15 text-red-400'
                      : row.level === 'warning'
                        ? 'bg-amber-400/15 text-amber-500'
                        : 'bg-surface-raised text-muted'
                  }`}
                >
                  {t(`system.log.levels.${row.level}`)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-ink">
                    {i18n.exists(`errors.${row.code}`) ? errorMessage({ code: row.code, params: row.params }) : row.code}
                  </span>
                  <span className="block text-xs text-muted">
                    {fmt(row.created_at)} · {row.source}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

// -- data and clean-up ---------------------------------------------------------------

export function DataCard() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const cleanup = useCleanup()
  if (!settings) return null
  return (
    <Card title={t('system.data.title')} description={t('system.data.description')}>
      <div className="space-y-4">
        <label className="flex flex-wrap items-center gap-3">
          <span className="font-medium text-ink">{t('system.data.retention')}</span>
          <select
            value={settings.retention_months}
            onChange={(e) => update.mutate({ retention_months: Number(e.target.value) as 0 | 3 | 6 | 12 | 24 })}
            className={fieldClass}
          >
            {[3, 6, 12, 24, 0].map((m) => (
              <option key={m} value={m}>
                {m ? t('system.data.months', { count: m }) : t('system.data.forever')}
              </option>
            ))}
          </select>
        </label>
        <p className="max-w-prose text-sm text-muted">{t('system.data.hint')}</p>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => cleanup.mutate()} disabled={cleanup.isPending} className={buttonClass}>
            <Trash2 className="size-4" aria-hidden />
            {t('system.data.cleanNow')}
          </button>
          {cleanup.data && (
            <span className="text-sm text-muted" role="status">
              {t('system.data.cleaned', { items: cleanup.data.items, logs: cleanup.data.logs })}
            </span>
          )}
        </div>
        <div className="border-t border-line pt-4">
          <button type="button" onClick={() => update.mutate({ first_run_completed: false })} className={buttonClass}>
            {t('system.data.rerunWizard')}
          </button>
        </div>
      </div>
    </Card>
  )
}
