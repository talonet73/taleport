import { Lightbulb } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router'

import { useSettings, useUpdateSettings } from '../../api/hooks'
import { readAsBase64 } from '../../api/files'
import { usePostingTimes, useUsage } from '../../api/planner'
import { useReportLogo, useSetReportLogo } from '../../api/reports'
import type { Platform } from '../../api/types'
import { Card } from '../../components/Card'
import { Toggle } from '../../components/Toggle'
import { useErrorMessage } from '../../components/useErrorMessage'

const fieldClass = 'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'

/** Monthly API spend: total, per provider, recent calls, and the cap that blocks paid calls. */
export function SpendCard() {
  const { t, i18n } = useTranslation()
  const { data: settings } = useSettings()
  const { data: usage } = useUsage()
  const update = useUpdateSettings()
  const errorMessage = useErrorMessage()
  const [cap, setCap] = useState('')
  useEffect(() => setCap(settings?.spend_cap_usd != null ? String(settings.spend_cap_usd) : ''), [settings?.spend_cap_usd])
  if (!settings || !usage) return null

  const usd = (n: number, digits = 2) =>
    new Intl.NumberFormat(i18n.language, { style: 'currency', currency: 'USD', maximumFractionDigits: digits }).format(n)
  const share = usage.cap_usd ? Math.min(100, (100 * usage.month_total_usd) / usage.cap_usd) : 0
  const saveCap = () => {
    const value = cap.trim() === '' ? null : Number(cap.replace(',', '.'))
    if (value !== settings.spend_cap_usd && (value === null || !Number.isNaN(value))) update.mutate({ spend_cap_usd: value })
  }

  return (
    <Card title={t('spend.title')} description={t('spend.description')}>
      <div className="space-y-5">
        <div>
          <p className="text-3xl font-bold text-ink">{usd(usage.month_total_usd)}</p>
          <p className="text-sm text-muted">
            {usage.cap_usd ? t('spend.ofCap', { cap: usd(usage.cap_usd) }) : t('spend.noCap')}
          </p>
          {usage.cap_usd ? (
            <div
              role="meter"
              aria-label={t('spend.meter')}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(share)}
              className="mt-2 h-2 max-w-md overflow-hidden rounded-full bg-surface-raised"
            >
              <div className="h-full rounded-full bg-accent-gradient" style={{ width: `${share}%` }} />
            </div>
          ) : null}
          {usage.cap_reached && <p className="mt-2 font-semibold text-amber-500">{t('spend.capReached')}</p>}
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm font-medium text-ink">
            {t('spend.cap')}
            <input
              inputMode="decimal"
              value={cap}
              onChange={(e) => setCap(e.target.value)}
              onBlur={saveCap}
              placeholder={t('spend.capPlaceholder')}
              className={`${fieldClass} mt-1.5 block w-36`}
            />
          </label>
          <label className="text-sm font-medium text-ink">
            {t('spend.warnAt')}
            <select
              value={settings.spend_warn_percent}
              onChange={(e) => update.mutate({ spend_warn_percent: Number(e.target.value) })}
              className={`${fieldClass} mt-1.5 block`}
            >
              {[50, 70, 80, 90, 95].map((p) => (
                <option key={p} value={p}>
                  {p}%
                </option>
              ))}
            </select>
          </label>
          <p className="max-w-prose basis-full text-sm text-muted">{t('spend.capHint')}</p>
        </div>
        {update.isError && <p className="text-sm text-red-400">{errorMessage(update.error)}</p>}

        {usage.by_provider.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="mb-1 text-left font-semibold text-ink">{t('spend.thisMonth')}</caption>
              <thead>
                <tr className="text-left text-muted">
                  <th className="py-1 pr-3 font-medium">{t('spend.provider')}</th>
                  <th className="py-1 pr-3 text-right font-medium">{t('spend.calls')}</th>
                  <th className="py-1 text-right font-medium">{t('spend.cost')}</th>
                </tr>
              </thead>
              <tbody>
                {usage.by_provider.map((row) => (
                  <tr key={row.provider} className="border-t border-line text-ink">
                    <td className="py-1.5 pr-3">{t(`ai.${row.provider}`, { defaultValue: row.provider })}</td>
                    <td className="py-1.5 pr-3 text-right">{row.calls}</td>
                    <td className="py-1.5 text-right">
                      {usd(row.cost_usd, 4)}
                      {row.unknown > 0 && <span className="text-muted"> · {t('spend.unknown', { count: row.unknown })}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <details>
          <summary className="cursor-pointer font-medium text-ink">{t('spend.recent')}</summary>
          {usage.recent.length === 0 ? (
            <p className="mt-2 text-sm text-muted">{t('spend.noCalls')}</p>
          ) : (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted">
                    <th className="py-1 pr-3 font-medium">{t('spend.when')}</th>
                    <th className="py-1 pr-3 font-medium">{t('spend.provider')}</th>
                    <th className="py-1 pr-3 font-medium">{t('spend.feature')}</th>
                    <th className="py-1 pr-3 text-right font-medium">{t('spend.tokens')}</th>
                    <th className="py-1 text-right font-medium">{t('spend.cost')}</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.recent.map((row) => (
                    <tr key={row.id} className="border-t border-line text-ink">
                      <td className="py-1.5 pr-3 whitespace-nowrap">
                        {new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(
                          new Date(row.created_at),
                        )}
                      </td>
                      <td className="py-1.5 pr-3">{t(`ai.${row.provider}`, { defaultValue: row.provider })}</td>
                      <td className="py-1.5 pr-3">{t(`spend.features.${row.feature}`, { defaultValue: row.feature })}</td>
                      <td className="py-1.5 pr-3 text-right">
                        {new Intl.NumberFormat(i18n.language).format(row.input_tokens + row.output_tokens)}
                      </td>
                      <td className="py-1.5 text-right">
                        {row.cost_usd === null ? t('spend.priceUnknown') : usd(row.cost_usd, 4)}
                        {row.cost_source === 'estimate' && <span className="text-muted"> {t('spend.estimated')}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </details>
      </div>
    </Card>
  )
}

export function NotificationsCard() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  if (!settings) return null
  return (
    <Card title={t('notifications.settingsTitle')} description={t('notifications.settingsDescription')}>
      <div className="flex items-start gap-3">
        <Toggle
          checked={settings.notify_windows}
          onChange={(v) => update.mutate({ notify_windows: v })}
          label={t('notifications.windows')}
        />
        <div>
          <p className="text-ink">{t('notifications.windows')}</p>
          <p className="max-w-prose text-sm text-muted">{t('notifications.windowsHint')}</p>
        </div>
      </div>
    </Card>
  )
}

export function PostingTimesCard() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const { data: times } = usePostingTimes()
  const update = useUpdateSettings()
  const { hash } = useLocation()
  const ref = useRef<HTMLDivElement>(null)

  // The calendar links here (/settings#posting-times): scroll once the times are shown.
  useEffect(() => {
    if (times && hash === '#posting-times') ref.current?.scrollIntoView({ block: 'start' })
  }, [times, hash])

  if (!settings || !times) return null

  const setTime = (platform: Platform, value: string | null) => {
    const next = { ...settings.posting_times }
    if (value) next[platform] = value
    else delete next[platform]
    update.mutate({ posting_times: next })
  }

  return (
    <div ref={ref}>
      <Card title={t('calendar.postingTimes')} description={t('calendar.postingTimesHint')}>
        <ul className="space-y-3">
          {times.map((pt) => (
            <li key={pt.platform} className="flex flex-wrap items-center gap-3">
              <span className="w-40 font-medium text-ink">{t(`platforms.${pt.platform}`)}</span>
              <input
                type="time"
                aria-label={t(`platforms.${pt.platform}`)}
                defaultValue={pt.time}
                key={pt.time}
                onBlur={(e) => e.target.value && e.target.value !== pt.time && setTime(pt.platform, e.target.value)}
                className={fieldClass}
              />
              {pt.custom ? (
                <button type="button" onClick={() => setTime(pt.platform, null)} className="text-sm text-muted hover:text-ink">
                  {t('calendar.resetTime', { time: pt.default })}
                </button>
              ) : (
                <span className="text-sm text-muted">{t('calendar.defaultTime')}</span>
              )}
              {pt.learned && pt.learned.time !== pt.time && (
                <span className="flex basis-full items-center gap-2 pl-43 text-sm text-ink">
                  <Lightbulb className="size-4 text-accent-text" aria-hidden />
                  {t('calendar.learned', { time: pt.learned.time, posts: pt.learned.posts, average: pt.learned.average })}
                  <button
                    type="button"
                    onClick={() => setTime(pt.platform, pt.learned!.time)}
                    className="rounded-full border border-line px-3 py-0.5 text-sm hover:bg-surface-raised"
                  >
                    {t('calendar.useLearned')}
                  </button>
                </span>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

/** Cover of the PDF reports: default theme, name and logo. */
export function ReportCoverCard() {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: settings } = useSettings()
  const { data: logo } = useReportLogo()
  const update = useUpdateSettings()
  const setLogo = useSetReportLogo()
  const [name, setName] = useState('')
  useEffect(() => setName(settings?.report_cover_name ?? ''), [settings?.report_cover_name])
  if (!settings) return null

  return (
    <Card title={t('reports.coverTitle')} description={t('reports.coverText')}>
      <div className="space-y-5">
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-ink">{t('reports.defaultTheme')}</legend>
          <div role="radiogroup" className="flex gap-1">
            {(['light', 'dark'] as const).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={settings.report_theme === value}
                onClick={() => update.mutate({ report_theme: value })}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold ${
                  settings.report_theme === value
                    ? 'bg-accent-gradient text-on-accent'
                    : 'border border-line text-ink hover:bg-surface-raised'
                }`}
              >
                {t(`reports.themes.${value}`)}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="block text-sm font-medium text-ink">
          {t('reports.coverName')}
          <input
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => name !== settings.report_cover_name && update.mutate({ report_cover_name: name.trim() })}
            placeholder={t('reports.coverNamePlaceholder')}
            className={`${fieldClass} mt-1.5 block w-full max-w-md`}
          />
        </label>
        <div>
          <p className="text-sm font-medium text-ink">{t('reports.logo')}</p>
          <p className="mb-2 text-sm text-muted">
            {logo?.custom ? t('reports.logoCustom') : t('reports.logoDefault')} {t('reports.logoHint')}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <label className="relative cursor-pointer rounded-full border border-line px-4 py-1.5 text-sm font-semibold text-ink focus-within:border-accent hover:bg-surface-raised">
              {t('reports.chooseLogo')}
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.svg"
                className="sr-only"
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  e.target.value = ''
                  if (file) setLogo.mutate({ file_name: file.name, file_base64: await readAsBase64(file) })
                }}
              />
            </label>
            {logo?.custom && (
              <button type="button" onClick={() => setLogo.mutate(null)} className="text-sm text-muted hover:text-ink">
                {t('reports.removeLogo')}
              </button>
            )}
          </div>
          {setLogo.isError && <p className="mt-2 text-sm text-red-400">{errorMessage(setLogo.error)}</p>}
        </div>
      </div>
    </Card>
  )
}
