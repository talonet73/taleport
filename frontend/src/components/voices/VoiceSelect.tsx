import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import { useVoices } from '../../api/voices'

const fieldClass =
  'w-full rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none focus:border-accent'

/** Which voice the posts are written in: a saved profile, or the topic's own tone. */
export function VoiceSelect({
  value,
  onChange,
  extra,
}: {
  value: string
  onChange: (value: string) => void
  extra?: { value: string; label: string }
}) {
  const { t } = useTranslation()
  const { data: voices = [] } = useVoices()
  return (
    <label className="flex flex-col gap-2">
      <span className="flex items-center justify-between gap-2 font-medium text-ink">
        {t('voices.select.label')}
        <Link to="/voices" className="text-sm font-normal text-accent-text hover:underline">
          {t('voices.select.manage')}
        </Link>
      </span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={fieldClass}>
        {extra && <option value={extra.value}>{extra.label}</option>}
        <option value="">{t('voices.select.topic')}</option>
        {voices.map((v) => (
          <option key={v.id} value={String(v.id)}>
            {v.name}
          </option>
        ))}
      </select>
    </label>
  )
}

/** The profile linked to a topic, if any (pre-selected for that topic's themes). */
export function useTopicVoice(topicId: number | undefined | null): string {
  const { data: voices = [] } = useVoices()
  const linked = topicId == null ? undefined : voices.find((v) => v.topic_ids.includes(topicId))
  return linked ? String(linked.id) : ''
}
