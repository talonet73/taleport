import { Activity, Wallet } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'

import { useStatus } from '../api/hooks'
import { Logo } from '../components/Logo'
import { NAV_ITEMS } from './navigation'

export function Sidebar() {
  const { t } = useTranslation()

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-line bg-sidebar">
      <div className="px-5 pt-5 pb-4">
        <Logo className="h-14 w-auto" />
      </div>

      <nav aria-label={t('nav.label')} className="flex-1 overflow-y-auto px-3">
        <ul className="space-y-1">
          {NAV_ITEMS.map(({ path, labelKey, icon: Icon }) => (
            <li key={path}>
              <NavLink
                to={path}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-xl px-3 py-2.5 font-medium transition-colors ${
                    isActive
                      ? 'bg-surface-raised text-ink shadow-card'
                      : 'text-muted hover:bg-surface hover:text-ink'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`grid size-8 place-items-center rounded-lg ${
                        isActive ? 'bg-accent-gradient text-on-accent' : 'bg-surface/60'
                      }`}
                    >
                      <Icon className="size-4" aria-hidden />
                    </span>
                    {t(labelKey)}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <StatusBox />
    </aside>
  )
}

function StatusBox() {
  const { t, i18n } = useTranslation()
  const { data: status } = useStatus()

  const formatDate = (iso: string | null, fallback: string) =>
    iso
      ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(
          new Date(iso),
        )
      : fallback
  const spend = new Intl.NumberFormat(i18n.language, {
    style: 'currency',
    currency: status?.api_spend_currency ?? 'USD',
  }).format(status?.api_spend_month ?? 0)

  return (
    <div className="m-3 space-y-3 rounded-card border border-line bg-surface p-4 text-sm shadow-card">
      <div>
        <p className="mb-1 flex items-center gap-2 font-semibold text-ink">
          <Activity className="size-4 text-accent-text" aria-hidden />
          {t('sidebar.scanStatus')}
        </p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-muted">
          <dt>{t('sidebar.lastScan')}</dt>
          <dd className="text-right text-ink">
            {status?.scan_running
              ? t('sidebar.inProgress')
              : formatDate(status?.last_scan_at ?? null, t('sidebar.never'))}
          </dd>
          <dt>{t('sidebar.nextScan')}</dt>
          <dd className="text-right text-ink">
            {formatDate(status?.next_scan_at ?? null, t('sidebar.notScheduled'))}
          </dd>
        </dl>
      </div>
      <div className="border-t border-line pt-3">
        <p className="flex items-center gap-2 text-muted">
          <Wallet className="size-4 text-accent-text" aria-hidden />
          {t('sidebar.apiSpend')}
        </p>
        <p className="mt-1 text-xl font-bold text-ink">{spend}</p>
        {status?.api_spend_cap != null && (
          <p className="text-xs text-muted">
            {t('sidebar.ofCap', {
              cap: new Intl.NumberFormat(i18n.language, { style: 'currency', currency: 'USD' }).format(status.api_spend_cap),
            })}
          </p>
        )}
      </div>
      {status && (
        <p className="text-xs text-muted">{t('sidebar.version', { version: status.version })}</p>
      )}
    </div>
  )
}
