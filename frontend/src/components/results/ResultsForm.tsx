import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useSaveResults } from '../../api/planner'
import { type PostResults, RESULT_METRICS } from '../../api/types'
import { useErrorMessage } from '../useErrorMessage'

const EMPTY: PostResults = { likes: null, comments: null, shares: null, views: null }

/** Likes, comments, shares and views of a published post, entered by hand. */
export function ResultsForm({
  draftId,
  initial,
  onDone,
}: {
  draftId: number
  initial: PostResults | null | undefined
  onDone?: () => void
}) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const save = useSaveResults()
  const [values, setValues] = useState<PostResults>(initial ?? EMPTY)

  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ id: draftId, results: values }, { onSuccess: () => onDone?.() })
      }}
    >
      {RESULT_METRICS.map((metric) => (
        <label key={metric} className="text-sm text-muted">
          {t(`results.metrics.${metric}`)}
          <input
            type="number"
            min={0}
            aria-label={t(`results.metrics.${metric}`)}
            inputMode="numeric"
            value={values[metric] ?? ''}
            onChange={(e) =>
              setValues({ ...values, [metric]: e.target.value === '' ? null : Math.max(0, Number(e.target.value)) })
            }
            className="mt-1 block w-28 rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-ink"
          />
        </label>
      ))}
      <button
        type="submit"
        disabled={save.isPending}
        className="rounded-xl bg-accent-gradient px-4 py-1.5 font-semibold text-on-accent disabled:opacity-60"
      >
        {t('common.save')}
      </button>
      <p className="basis-full text-xs text-muted">{t('results.hint')}</p>
      {save.isError && <p className="basis-full text-sm text-red-400">{errorMessage(save.error)}</p>}
    </form>
  )
}

/** "12 like · 3 commenti · …" for the metrics that were entered. */
export function ResultsLine({ results }: { results: PostResults | null | undefined }) {
  const { t, i18n } = useTranslation()
  if (!results) return null
  const parts = RESULT_METRICS.filter((m) => results[m] !== null).map(
    (m) => `${new Intl.NumberFormat(i18n.language).format(results[m]!)} ${t(`results.metrics.${m}`).toLowerCase()}`,
  )
  return <p className="text-sm text-ink">{parts.join(' · ')}</p>
}
