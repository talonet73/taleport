import { CalendarDays, CalendarRange, FileDown, FolderOpen, Loader2, Play, Save, Sun, Trash2, TrendingUp } from 'lucide-react'
import { type ReactNode, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useSettings, useTopics } from '../../api/hooks'
import {
  type CustomReportParams,
  openReport,
  REPORT_SECTIONS,
  type ReportKind,
  type ReportSection,
  type ReportTemplate,
  type ReportTheme,
  reportUrl,
  type SavedReport,
  useDeleteTemplate,
  useGenerateReport,
  useReportFiles,
  useReportTemplates,
  useRunTemplate,
  useSaveTemplate,
} from '../../api/reports'
import { LANGUAGES } from '../../api/types'
import { Card } from '../../components/Card'
import { SavedNotice } from '../../components/reports/ExportPdfButton'
import { useErrorMessage } from '../../components/useErrorMessage'

const field = 'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'
const PERIODS = ['last_7_days', 'last_30_days', 'this_month', 'last_week', 'custom'] as const

const EMPTY: CustomReportParams = {
  title: '',
  period: { preset: 'last_7_days' },
  filters: {},
  sections: ['summary', 'themes', 'keywords', 'trend'],
}

export function ReportsPage() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const [theme, setTheme] = useState<ReportTheme>('light')
  const [last, setLast] = useState<SavedReport | null>(null)
  const [form, setForm] = useState<CustomReportParams>(EMPTY)
  const [editing, setEditing] = useState<ReportTemplate | null>(null)

  useEffect(() => {
    if (settings) setTheme(settings.report_theme)
  }, [settings])

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('nav.reports')}</h1>
          <p className="mt-1 max-w-prose text-muted">{t('reports.subtitle')}</p>
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-ink">{t('reports.theme')}</legend>
          <div role="radiogroup" className="flex gap-1">
            {(['light', 'dark'] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={theme === value}
                onClick={() => setTheme(value)}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold ${
                  theme === value ? 'bg-accent-gradient text-on-accent' : 'border border-line text-ink hover:bg-surface-raised'
                }`}
              >
                {t(`reports.themes.${value}`)}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      {last && (
        <div className="rounded-card border border-line bg-surface p-4">
          <SavedNotice file={last} />
        </div>
      )}

      <QuickReports theme={theme} onSaved={setLast} />
      <CustomReportCard
        form={form}
        setForm={setForm}
        editing={editing}
        onEditDone={() => setEditing(null)}
        theme={theme}
        onSaved={setLast}
      />
      <TemplatesCard
        onEdit={(template) => {
          setEditing(template)
          setForm({ ...EMPTY, ...template.params })
          document.getElementById('custom-report')?.scrollIntoView({ block: 'start' })
        }}
        onSaved={setLast}
      />
      <RecentFiles />
    </div>
  )
}

function QuickReports({ theme, onSaved }: { theme: ReportTheme; onSaved: (file: SavedReport) => void }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const generate = useGenerateReport()
  const [running, setRunning] = useState<string | null>(null)
  const items: { key: string; kind: ReportKind; body: object; icon: ReactNode }[] = [
    { key: 'daily', kind: 'daily', body: {}, icon: <Sun className="size-5" aria-hidden /> },
    { key: 'weekly', kind: 'weekly', body: {}, icon: <CalendarRange className="size-5" aria-hidden /> },
    { key: 'trends7', kind: 'trends', body: { period: 'last_7_days' }, icon: <TrendingUp className="size-5" aria-hidden /> },
    { key: 'trends30', kind: 'trends', body: { period: 'last_30_days' }, icon: <CalendarDays className="size-5" aria-hidden /> },
  ]
  return (
    <Card title={t('reports.quickTitle')} description={t('reports.quickText')}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            disabled={generate.isPending}
            onClick={() => {
              setRunning(item.key)
              generate.mutate({ kind: item.kind, body: { ...item.body, theme } }, { onSuccess: onSaved })
            }}
            className="flex items-start gap-3 rounded-card border border-line bg-surface-raised p-4 text-left hover:border-accent disabled:opacity-60"
          >
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-gradient text-on-accent">
              {generate.isPending && running === item.key ? <Loader2 className="size-5 animate-spin" aria-hidden /> : item.icon}
            </span>
            <span>
              <span className="block font-semibold text-ink">{t(`reports.quick.${item.key}.title`)}</span>
              <span className="block text-sm text-muted">{t(`reports.quick.${item.key}.text`)}</span>
            </span>
          </button>
        ))}
      </div>
      {generate.isError && <p className="mt-3 text-sm text-red-400">{errorMessage(generate.error)}</p>}
    </Card>
  )
}

function CustomReportCard({
  form,
  setForm,
  editing,
  onEditDone,
  theme,
  onSaved,
}: {
  form: CustomReportParams
  setForm: (f: CustomReportParams) => void
  editing: ReportTemplate | null
  onEditDone: () => void
  theme: ReportTheme
  onSaved: (file: SavedReport) => void
}) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: topics = [] } = useTopics()
  const generate = useGenerateReport()
  const saveTemplate = useSaveTemplate()
  const [name, setName] = useState('')
  useEffect(() => setName(editing?.name ?? ''), [editing])

  const toggle = <T,>(list: T[] | null | undefined, value: T): T[] =>
    (list ?? []).includes(value) ? (list ?? []).filter((x) => x !== value) : [...(list ?? []), value]
  const custom = form.period.preset === 'custom'
  const invalid = !form.sections.length || (custom && !(form.period.start && form.period.end))
  const params: CustomReportParams = {
    ...form,
    period: custom ? form.period : { preset: form.period.preset },
    filters: {
      topics: form.filters.topics?.length ? form.filters.topics : null,
      languages: form.filters.languages?.length ? form.filters.languages : null,
    },
  }

  return (
    <div id="custom-report">
      <Card title={t('reports.customTitle')} description={t('reports.customText')}>
        <div className="space-y-5">
          <label className="block text-sm font-medium text-ink">
            {t('reports.reportTitle')}
            <input
              value={form.title}
              maxLength={120}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder={t('reports.reportTitlePlaceholder')}
              className={`${field} mt-1.5 block w-full max-w-xl`}
            />
          </label>

          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-ink">{t('reports.period')}</legend>
            <div className="flex flex-wrap items-center gap-2" role="radiogroup">
              {PERIODS.map((p) => (
                <button
                  key={p}
                  type="button"
                  role="radio"
                  aria-checked={form.period.preset === p}
                  onClick={() => setForm({ ...form, period: { ...form.period, preset: p } })}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium ${
                    form.period.preset === p ? 'bg-accent-gradient text-on-accent' : 'border border-line text-ink hover:bg-surface-raised'
                  }`}
                >
                  {t(`reports.periods.${p}`)}
                </button>
              ))}
              {custom && (
                <>
                  <input
                    type="date"
                    aria-label={t('archive.from')}
                    value={form.period.start ?? ''}
                    onChange={(e) => setForm({ ...form, period: { ...form.period, start: e.target.value } })}
                    className={field}
                  />
                  <input
                    type="date"
                    aria-label={t('archive.to')}
                    value={form.period.end ?? ''}
                    onChange={(e) => setForm({ ...form, period: { ...form.period, end: e.target.value } })}
                    className={field}
                  />
                </>
              )}
            </div>
          </fieldset>

          {topics.length > 1 && (
            <CheckGroup legend={t('reports.topics')} hint={t('reports.allIfNone')}>
              {topics.map((topic) => (
                <Check
                  key={topic.id}
                  label={topic.name}
                  checked={form.filters.topics?.includes(topic.id) ?? false}
                  onChange={() => setForm({ ...form, filters: { ...form.filters, topics: toggle(form.filters.topics, topic.id) } })}
                />
              ))}
            </CheckGroup>
          )}

          <CheckGroup legend={t('reports.languages')} hint={t('reports.allIfNone')}>
            {LANGUAGES.map((lang) => (
              <Check
                key={lang}
                label={t(`languages.${lang}`)}
                checked={form.filters.languages?.includes(lang) ?? false}
                onChange={() => setForm({ ...form, filters: { ...form.filters, languages: toggle(form.filters.languages, lang) } })}
              />
            ))}
          </CheckGroup>

          <CheckGroup legend={t('reports.sections')}>
            {REPORT_SECTIONS.map((section) => (
              <Check
                key={section}
                label={t(`reports.sectionNames.${section}`)}
                checked={form.sections.includes(section)}
                onChange={() => setForm({ ...form, sections: toggle<ReportSection>(form.sections, section) })}
              />
            ))}
          </CheckGroup>

          <div className="flex flex-wrap items-end gap-3 border-t border-line pt-4">
            <button
              type="button"
              disabled={invalid || generate.isPending}
              onClick={() => generate.mutate({ kind: 'custom', body: { ...params, theme } }, { onSuccess: onSaved })}
              className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-60"
            >
              {generate.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FileDown className="size-4" aria-hidden />}
              {t('reports.generate')}
            </button>
            <label className="text-sm font-medium text-ink">
              {t('reports.templateName')}
              <input
                value={name}
                maxLength={80}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('reports.templateNamePlaceholder')}
                className={`${field} mt-1.5 block w-64`}
              />
            </label>
            <button
              type="button"
              disabled={invalid || !name.trim() || saveTemplate.isPending}
              onClick={() =>
                saveTemplate.mutate(
                  { id: editing?.id, name: name.trim(), params: { ...params, theme } },
                  { onSuccess: onEditDone },
                )
              }
              className="flex items-center gap-2 rounded-full border border-line px-4 py-2 font-semibold text-ink hover:bg-surface-raised disabled:opacity-60"
            >
              <Save className="size-4" aria-hidden />
              {editing ? t('reports.updateTemplate') : t('reports.saveTemplate')}
            </button>
            {editing && (
              <button type="button" onClick={onEditDone} className="text-sm text-muted hover:text-ink">
                {t('common.cancel')}
              </button>
            )}
          </div>
          {!form.sections.length && <p className="text-sm text-amber-500">{t('reports.pickSection')}</p>}
          {(generate.isError || saveTemplate.isError) && (
            <p className="text-sm text-red-400">{errorMessage(generate.error ?? saveTemplate.error)}</p>
          )}
          {saveTemplate.isSuccess && <p className="text-sm text-muted" role="status">{t('reports.templateSaved')}</p>}
        </div>
      </Card>
    </div>
  )
}

function CheckGroup({ legend, hint, children }: { legend: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-ink">
        {legend}
        {hint && <span className="ml-2 font-normal text-muted">{hint}</span>}
      </legend>
      <div className="flex flex-wrap gap-2">{children}</div>
    </fieldset>
  )
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label
      className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
        checked ? 'border-accent bg-surface-raised text-ink' : 'border-line text-muted hover:text-ink'
      }`}
    >
      <input type="checkbox" checked={checked} onChange={onChange} className="accent-[var(--tp-accent)]" />
      {label}
    </label>
  )
}

function TemplatesCard({
  onEdit,
  onSaved,
}: {
  onEdit: (template: ReportTemplate) => void
  onSaved: (file: SavedReport) => void
}) {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: templates = [] } = useReportTemplates()
  const run = useRunTemplate()
  const remove = useDeleteTemplate()
  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))

  return (
    <Card title={t('reports.templatesTitle')} description={t('reports.templatesText')}>
      {templates.length === 0 ? (
        <p className="text-muted">{t('reports.noTemplates')}</p>
      ) : (
        <ul className="divide-y divide-line">
          {templates.map((template) => (
            <li key={template.id} className="flex flex-wrap items-center gap-3 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">{template.name}</p>
                <p className="text-sm text-muted">
                  {t(`reports.periods.${template.params.period.preset}`)} ·{' '}
                  {template.params.sections.map((s) => t(`reports.sectionNames.${s}`)).join(', ')}
                </p>
                <p className="text-xs text-muted">
                  {template.last_run_at ? t('reports.lastRun', { date: fmt(template.last_run_at) }) : t('reports.neverRun')}
                </p>
              </div>
              <button
                type="button"
                disabled={run.isPending}
                onClick={() => run.mutate(template.id, { onSuccess: onSaved })}
                className="flex items-center gap-1.5 rounded-full bg-accent-gradient px-4 py-1.5 text-sm font-semibold text-on-accent disabled:opacity-60"
              >
                {run.isPending && run.variables === template.id ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Play className="size-4" aria-hidden />
                )}
                {t('reports.regenerate')}
              </button>
              <button type="button" onClick={() => onEdit(template)} className="rounded-full border border-line px-4 py-1.5 text-sm text-ink hover:bg-surface-raised">
                {t('reports.editTemplate')}
              </button>
              <button
                type="button"
                onClick={() => remove.mutate(template.id)}
                aria-label={t('reports.deleteTemplate', { name: template.name })}
                className="rounded-xl p-2 text-muted hover:bg-surface-raised hover:text-ink"
              >
                <Trash2 className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      {run.isError && <p className="mt-2 text-sm text-red-400">{errorMessage(run.error)}</p>}
    </Card>
  )
}

function RecentFiles() {
  const { t, i18n } = useTranslation()
  const { data: files = [] } = useReportFiles()
  const size = (bytes: number) =>
    new Intl.NumberFormat(i18n.language, { style: 'unit', unit: 'kilobyte', maximumFractionDigits: 0 }).format(bytes / 1024)
  const fmt = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
  return (
    <Card
      title={t('reports.filesTitle')}
      description={t('reports.filesText')}
      actions={
        files.length > 0 && (
          <button
            type="button"
            onClick={() => void openReport(files[0].name, true)}
            className="flex items-center gap-1.5 rounded-full border border-line px-4 py-1.5 text-sm text-ink hover:bg-surface-raised"
          >
            <FolderOpen className="size-4" aria-hidden />
            {t('reports.openFolder')}
          </button>
        )
      }
    >
      {files.length === 0 ? (
        <p className="text-muted">{t('reports.noFiles')}</p>
      ) : (
        <ul className="divide-y divide-line">
          {files.map((file) => (
            <li key={file.name} className="flex flex-wrap items-center gap-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-ink">{file.name}</p>
                <p className="text-xs text-muted">
                  {fmt(file.modified)} · {size(file.size)}
                </p>
              </div>
              <button type="button" onClick={() => void openReport(file.name)} className="text-sm font-semibold text-accent-text hover:underline">
                {t('reports.open')}
              </button>
              <a href={reportUrl(file.name)} download={file.name} className="text-sm text-muted hover:text-ink">
                {t('reports.download')}
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
