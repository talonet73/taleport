import { useTranslation } from 'react-i18next'

import { LANGUAGES, type Language, PLATFORMS, type Platform } from '../../api/types'

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-full px-4 py-2 font-medium ${
        active ? 'bg-accent-gradient text-on-accent' : 'border border-line bg-surface-raised text-ink hover:border-accent'
      }`}
    >
      {children}
    </button>
  )
}

const toggle = <T,>(list: T[], value: T) =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

export function PlatformPicker({ value, onChange }: { value: Platform[]; onChange: (v: Platform[]) => void }) {
  const { t } = useTranslation()
  return (
    <fieldset>
      <legend className="mb-2 font-medium text-ink">{t('generator.platforms')}</legend>
      <div className="flex flex-wrap gap-2">
        {PLATFORMS.map((p) => (
          <Chip key={p} active={value.includes(p)} onClick={() => onChange(toggle(value, p))}>
            {t(`platforms.${p}`)}
          </Chip>
        ))}
      </div>
    </fieldset>
  )
}

export function LanguagePicker({
  value,
  onChange,
  single,
}: {
  value: Language[]
  onChange: (v: Language[]) => void
  single?: boolean
}) {
  const { t } = useTranslation()
  return (
    <fieldset>
      <legend className="mb-2 font-medium text-ink">{single ? t('generator.language') : t('generator.languages')}</legend>
      <div className="flex flex-wrap gap-2">
        {LANGUAGES.map((lang) => (
          <Chip
            key={lang}
            active={value.includes(lang)}
            onClick={() => onChange(single ? [lang] : toggle(value, lang))}
          >
            {t(`languages.${lang}`)}
          </Chip>
        ))}
      </div>
    </fieldset>
  )
}
