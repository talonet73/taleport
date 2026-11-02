import { useTranslation } from 'react-i18next'

import { AI_MODES, type AiMode } from '../../api/types'

export function AiModeSelect({ value, onChange }: { value: AiMode; onChange: (mode: AiMode) => void }) {
  const { t } = useTranslation()
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-ink">{t('ai.useAi')}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as AiMode)}
        className="rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent"
      >
        {AI_MODES.map((mode) => (
          <option key={mode} value={mode}>
            {t(`ai.${mode}`)}
          </option>
        ))}
      </select>
    </label>
  )
}
