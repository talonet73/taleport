import { AlertTriangle, BarChart3, Loader2, RotateCcw, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { frameUrl, type Video } from '../../api/video'
import { useErrorMessage } from '../../components/useErrorMessage'
import { makeFormat } from './format'

interface VideoCardProps {
  video: Video
  onResults: () => void
  onRetry: () => void
  onDelete: () => void
}

export function VideoCard({ video, onResults, onRetry, onDelete }: VideoCardProps) {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const f = makeFormat(i18n.language)
  const working = video.status === 'queued' || video.status === 'processing'
  const hasResults = Object.keys(video.stats).some((k) => k !== 'platform')

  return (
    <article className="flex gap-3 rounded-2xl border border-line bg-surface-raised p-3">
      <div className="grid aspect-[9/16] w-16 shrink-0 place-items-center overflow-hidden rounded-xl bg-surface">
        {video.status === 'ready' && video.frames > 0 ? (
          <img src={frameUrl(video.id, 0)} alt="" className="size-full object-cover" />
        ) : working ? (
          <Loader2 className="size-5 animate-spin text-accent-text" aria-hidden />
        ) : (
          <AlertTriangle className="size-5 text-red-400" aria-hidden />
        )}
      </div>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-start justify-between gap-2">
          <p className="truncate font-semibold text-ink" title={video.file_name}>
            {video.file_name}
          </p>
          <button
            type="button"
            onClick={onDelete}
            aria-label={t('video.card.delete')}
            title={t('video.card.delete')}
            className="rounded-full p-1 text-muted hover:bg-surface hover:text-ink"
          >
            <Trash2 className="size-4" aria-hidden />
          </button>
        </div>
        <p className="text-sm text-muted">
          {t(`video.platforms.${video.platform}`)}
          {video.status === 'ready' && (
            <>
              {' · '}
              {f.sec(video.features.duration)}
              {' · '}
              {t('video.card.cuts', { value: f.n(video.features.cuts_per_minute) })}
            </>
          )}
        </p>
        {working && (
          <p className="text-sm text-accent-text" role="status">
            {video.status === 'queued' ? t('video.card.queued') : t(`video.steps.${video.step ?? 'probe'}`)}
          </p>
        )}
        {video.status === 'failed' && (
          <p className="flex flex-wrap items-center gap-2 text-sm text-red-400">
            {errorMessage({ code: video.error_code ?? 'video.process_failed' })}
            <button type="button" onClick={onRetry} className="flex items-center gap-1 font-semibold text-accent-text hover:underline">
              <RotateCcw className="size-3.5" aria-hidden />
              {t('video.card.retry')}
            </button>
          </p>
        )}
        {video.status === 'ready' && video.features.speech_error && (
          <p className="text-xs text-muted">{errorMessage({ code: video.features.speech_error })}</p>
        )}
        {video.status !== 'failed' && (
          <button
            type="button"
            onClick={onResults}
            className="flex items-center gap-1.5 text-sm font-semibold text-accent-text hover:underline"
          >
            <BarChart3 className="size-4" aria-hidden />
            {hasResults
              ? t('video.card.resultsSummary', {
                  views: f.compact(video.stats.views),
                  watched: f.pct(video.derived.watched_ratio),
                })
              : t('video.card.addResults')}
          </button>
        )}
      </div>
    </article>
  )
}
