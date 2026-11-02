import { KeyRound, Monitor, Moon, Sun } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  useDeleteSecret,
  useSaveSecret,
  useSecrets,
  useSettings,
  useUpdateSettings,
  useYouTubeQuota,
} from '../../api/hooks'
import {
  LANGUAGES,
  type Language,
  SECRET_NAMES,
  type SecretName,
  THEMES,
  type ThemeSetting,
} from '../../api/types'
import { Card } from '../../components/Card'
import { Toggle } from '../../components/Toggle'
import { useErrorMessage } from '../../components/useErrorMessage'
import { AiSettingsCard } from './AiSettingsCard'
import { NotificationsCard, PostingTimesCard, ReportCoverCard, SpendCard } from './SettingsCards'
import { BackupCard, DataCard, ErrorLogCard, UpdatesCard } from './SystemCards'

const THEME_ICONS = { dark: Moon, light: Sun, system: Monitor } as const
const THEME_LABELS = {
  dark: 'settings.appearance.themeDark',
  light: 'settings.appearance.themeLight',
  system: 'settings.appearance.themeSystem',
} as const

const fieldClass =
  'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'

export function SettingsPage() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const errorMessage = useErrorMessage()

  if (!settings) return null

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink">{t('settings.title')}</h1>
        <p className="mt-1 text-muted">{t('settings.subtitle')}</p>
      </div>
      {update.isError && <p className="text-red-400">{errorMessage(update.error)}</p>}

      <Card title={t('settings.appearance.title')}>
        <div className="grid gap-6 md:grid-cols-2">
          <label className="flex flex-col gap-2">
            <span className="font-medium text-ink">{t('settings.appearance.language')}</span>
            <select
              value={settings.language}
              onChange={(e) => update.mutate({ language: e.target.value as Language })}
              className={fieldClass}
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {t(`languages.${lang}`)}
                </option>
              ))}
            </select>
          </label>

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 font-medium text-ink">{t('settings.appearance.theme')}</legend>
            <div className="flex gap-2" role="radiogroup">
              {THEMES.map((theme: ThemeSetting) => {
                const Icon = THEME_ICONS[theme]
                const active = settings.theme === theme
                return (
                  <button
                    key={theme}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => update.mutate({ theme })}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-3 py-2 font-medium transition-colors ${
                      active
                        ? 'border-transparent bg-accent-gradient text-on-accent'
                        : 'border-line bg-surface-raised text-ink hover:border-accent'
                    }`}
                  >
                    <Icon className="size-4" aria-hidden />
                    {t(THEME_LABELS[theme])}
                  </button>
                )
              })}
            </div>
          </fieldset>
        </div>
      </Card>

      <AiSettingsCard />
      <ApiKeysCard />
      <SpendCard />
      <ScanSettingsCard />
      <NotificationsCard />
      <PostingTimesCard />
      <ReportCoverCard />
      <BackupCard />
      <DataCard />
      <UpdatesCard />
      <ErrorLogCard />
    </div>
  )
}

function ScanSettingsCard() {
  const { t } = useTranslation()
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const [time, setTime] = useState(settings?.scan_time ?? '07:00')
  if (!settings) return null

  return (
    <Card title={t('settings.scan.title')} description={t('settings.scan.description')}>
      <div className="space-y-5">
        <label className="flex flex-wrap items-center gap-3">
          <span className="w-64 font-medium text-ink">{t('settings.scan.time')}</span>
          <input
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            onBlur={() => time && time !== settings.scan_time && update.mutate({ scan_time: time })}
            className={fieldClass}
          />
        </label>
        <div className="flex items-center gap-3">
          <Toggle
            checked={settings.start_with_windows}
            onChange={(v) => update.mutate({ start_with_windows: v })}
            label={t('settings.scan.startWithWindows')}
          />
          <span className="text-ink">{t('settings.scan.startWithWindows')}</span>
        </div>
        <div className="flex items-start gap-3">
          <Toggle
            checked={settings.close_to_tray}
            onChange={(v) => update.mutate({ close_to_tray: v })}
            label={t('settings.scan.closeToTray')}
          />
          <div>
            <p className="text-ink">{t('settings.scan.closeToTray')}</p>
            <p className="max-w-prose text-sm text-muted">{t('settings.scan.closeToTrayHint')}</p>
          </div>
        </div>
      </div>
    </Card>
  )
}

function YouTubeQuota() {
  const { t, i18n } = useTranslation()
  const { data: quota } = useYouTubeQuota()
  if (!quota) return null
  const number = new Intl.NumberFormat(i18n.language)
  return (
    <p className="w-full pl-7 text-sm text-muted">
      {t('settings.keys.youtubeQuota', {
        remaining: number.format(quota.remaining),
        limit: number.format(quota.limit),
      })}
    </p>
  )
}

function ApiKeysCard() {
  const { t } = useTranslation()
  const { data: status } = useSecrets()

  return (
    <Card title={t('settings.keys.title')} description={t('settings.keys.description')}>
      <ul className="divide-y divide-line">
        {SECRET_NAMES.map((name) => (
          <SecretRow key={name} name={name} isSet={status?.[name] ?? false} />
        ))}
      </ul>
    </Card>
  )
}

export function SecretRow({ name, isSet }: { name: SecretName; isSet: boolean }) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const save = useSaveSecret()
  const remove = useDeleteSecret()
  const errorMessage = useErrorMessage()
  const error = save.error ?? remove.error

  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <KeyRound className="size-4 text-accent-text" aria-hidden />
      <span className="w-52 font-medium text-ink">{t(`settings.keys.names.${name}`)}</span>
      <span
        className={`rounded-full px-2.5 py-0.5 text-sm font-medium ${
          isSet ? 'bg-teal/15 text-accent-text' : 'bg-surface-raised text-muted'
        }`}
      >
        {isSet ? t('settings.keys.set') : t('settings.keys.missing')}
      </span>
      <form
        className="ml-auto flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate({ name, value }, { onSuccess: () => setValue('') })
        }}
      >
        <input
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t('settings.keys.placeholder')}
          aria-label={t(`settings.keys.names.${name}`)}
          className={`${fieldClass} w-64`}
        />
        <button
          type="submit"
          disabled={!value.trim() || save.isPending}
          className="rounded-xl bg-accent-gradient px-4 py-2 font-semibold text-on-accent disabled:opacity-50"
        >
          {t('settings.keys.save')}
        </button>
        {isSet && (
          <button
            type="button"
            onClick={() => remove.mutate(name)}
            className="rounded-xl border border-line px-4 py-2 font-medium text-ink hover:bg-surface-raised"
          >
            {t('settings.keys.remove')}
          </button>
        )}
      </form>
      {name === 'youtube' && isSet && <YouTubeQuota />}
      {error && <p className="w-full text-sm text-red-400">{errorMessage(error)}</p>}
    </li>
  )
}
