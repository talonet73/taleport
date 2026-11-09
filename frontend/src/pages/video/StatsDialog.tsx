import { Info, Loader2, ScanText } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { aiPost, useSettings } from '../../api/hooks'
import type { AiMode } from '../../api/types'
import {
  IMAGE_EXTENSIONS,
  readStatsFromScreenshots,
  type StatsHandoff,
  useVideoAction,
  type Video,
  type VideoStats,
} from '../../api/video'
import { AiModeSelect } from '../../components/ai/AiModeSelect'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { Modal } from '../../components/Modal'
import { useErrorMessage } from '../../components/useErrorMessage'
import { DropZone } from '../../components/DropZone'

const NUMBER_FIELDS = ['views', 'reach', 'likes', 'comments', 'shares', 'saves', 'follows', 'avg_watch_seconds'] as const
type NumberField = (typeof NUMBER_FIELDS)[number]

const fieldClass =
  'w-full rounded-xl border border-line bg-surface px-3 py-2 text-ink outline-none placeholder:text-muted focus:border-accent'

function retentionText(stats: VideoStats): string {
  return (stats.retention ?? []).map((p) => `${p.second}=${p.percent}`).join(', ')
}

function parseRetention(text: string) {
  return text
    .split(/[,;\n]+/)
    .map((pair) => pair.split(/[=:]/).map((x) => Number(x.trim().replace('%', '').replace('s', ''))))
    .filter(([s, p]) => Number.isFinite(s) && Number.isFinite(p))
    .map(([second, percent]) => ({ second, percent }))
}

function toForm(stats: VideoStats): Record<NumberField, string> {
  return Object.fromEntries(NUMBER_FIELDS.map((k) => [k, stats[k] == null ? '' : String(stats[k])])) as Record<
    NumberField,
    string
  >
}

/** Results of one video: read by the AI from screenshots, or typed by hand. */
export function StatsDialog({ video, onClose }: { video: Video; onClose: () => void }) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const { data: settings } = useSettings()
  const actions = useVideoAction(video.project_id)
  const [mode, setMode] = useState<AiMode | null>(null)
  const [images, setImages] = useState<File[]>([])
  const [values, setValues] = useState(() => toForm(video.stats))
  const [retention, setRetention] = useState(() => retentionText(video.stats))
  const [readDone, setReadDone] = useState(false)

  const applyRead = (updated?: Video) => {
    if (!updated) return
    setValues(toForm(updated.stats))
    setRetention(retentionText(updated.stats))
    setReadDone(true)
    void actions.refresh()
  }

  const flow = useAiFlow<never>({
    start: (m) => readStatsFromScreenshots(video.id, images, m),
    parse: (text) => aiPost(`/videos/${video.id}/stats/parse`, { text }),
    onDone: (envelope) => applyRead((envelope as { video?: Video }).video),
  })
  const handoff = flow.handoff as StatsHandoff | null

  const save = () => {
    const stats: Record<string, unknown> = { ...video.stats }
    for (const key of NUMBER_FIELDS) {
      const raw = values[key].trim().replace(',', '.')
      if (raw) stats[key] = key === 'avg_watch_seconds' ? Number(raw) : raw
      else delete stats[key]
    }
    stats.retention = parseRetention(retention)
    actions.update.mutate({ id: video.id, changes: { stats } }, { onSuccess: onClose })
  }

  return (
    <Modal title={t('video.stats.title', { name: video.file_name })} onClose={onClose} wide>
      <div className="space-y-6">
        <section className="space-y-3">
          <h3 className="flex items-center gap-2 font-semibold text-ink">
            <ScanText className="size-5 text-accent-text" aria-hidden />
            {t('video.stats.fromScreenshots')}
          </h3>
          <p className="text-sm text-muted">{t('video.stats.screenshotsHint')}</p>
          {flow.phase === 'handoff' && handoff ? (
            <>
              <p className="flex gap-2 rounded-xl bg-surface-raised p-3 text-sm text-ink">
                <Info className="mt-0.5 size-4 shrink-0 text-accent-text" aria-hidden />
                {t('video.stats.attachInChat', { count: handoff.images })}
              </p>
              <HandoffPanel handoff={handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
            </>
          ) : (
            <>
              <DropZone
                compact
                accept={IMAGE_EXTENSIONS}
                label={images.length ? t('video.stats.imagesChosen', { count: images.length }) : t('video.stats.dropImages')}
                hint={images.map((i) => i.name).join(', ') || t('video.stats.imagesFormats')}
                onFiles={(files) => setImages(files.slice(0, 6))}
              />
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-56">
                  <AiModeSelect value={mode ?? settings?.default_ai ?? 'chat'} onChange={setMode} />
                </div>
                <button
                  type="button"
                  disabled={!images.length || flow.busy}
                  onClick={() => flow.run(mode ?? settings?.default_ai ?? 'chat')}
                  className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-semibold text-on-accent disabled:opacity-50"
                >
                  {flow.busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
                  {flow.busy ? t('video.stats.reading') : t('video.stats.read')}
                </button>
              </div>
              {flow.error !== null && <p className="text-red-400">{errorMessage(flow.error)}</p>}
            </>
          )}
          {readDone && (
            <p role="status" className="text-sm text-accent-text">
              {t('video.stats.readDone')}
            </p>
          )}
        </section>

        <section className="space-y-3">
          <h3 className="font-semibold text-ink">{t('video.stats.manual')}</h3>
          <div className="grid gap-3 sm:grid-cols-4">
            {NUMBER_FIELDS.map((key) => (
              <label key={key} className="flex flex-col gap-1 text-sm">
                <span className="text-muted">{t(`video.fields.${key}`)}</span>
                <input
                  inputMode="decimal"
                  value={values[key]}
                  onChange={(e) => setValues({ ...values, [key]: e.target.value })}
                  className={fieldClass}
                />
              </label>
            ))}
          </div>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">{t('video.fields.retention')}</span>
            <input
              value={retention}
              onChange={(e) => setRetention(e.target.value)}
              placeholder="0=100, 3=62, 10=41, 20=30"
              className={fieldClass}
            />
            <span className="text-xs text-muted">{t('video.fields.retentionHint')}</span>
          </label>
          {actions.update.isError && <p className="text-red-400">{errorMessage(actions.update.error)}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-full border border-line px-4 py-2 text-ink hover:bg-surface-raised">
              {t('common.cancel')}
            </button>
            <button
              type="button"
              onClick={save}
              disabled={actions.update.isPending}
              className="rounded-full bg-accent-gradient px-5 py-2 font-semibold text-on-accent disabled:opacity-50"
            >
              {t('common.save')}
            </button>
          </div>
        </section>
      </div>
    </Modal>
  )
}
