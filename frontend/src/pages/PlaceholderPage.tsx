import { Construction } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Card } from '../components/Card'

export function PlaceholderPage({ titleKey, phase }: { titleKey: string; phase: number }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-ink">{t(titleKey)}</h1>
      <Card className="flex items-center gap-5">
        <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-accent-gradient text-on-accent">
          <Construction className="size-7" aria-hidden />
        </span>
        <div>
          <p className="text-lg font-semibold text-ink">{t('placeholder.title')}</p>
          <p className="text-muted">{t('placeholder.body', { phase })}</p>
        </div>
      </Card>
    </div>
  )
}
