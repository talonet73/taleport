import { ArrowLeft, FileDown, Info, Loader2, MessageSquareText, Plus, Sparkles, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'

import { aiPost, useSettings } from '../../api/hooks'
import { openReport } from '../../api/reports'
import type { AiMode } from '../../api/types'
import {
  generateVideoReport,
  type OwnerKind,
  uploadVideos,
  useDeleteVideoProject,
  useUpdateVideoProject,
  useVideoAction,
  useVideoProject,
  useVideoTools,
  VIDEO_EXTENSIONS,
  VIDEO_PLATFORMS,
  type Video,
  type VideoPlatform,
} from '../../api/video'
import { AiModeSelect } from '../../components/ai/AiModeSelect'
import { HandoffPanel } from '../../components/ai/HandoffPanel'
import { useAiFlow } from '../../components/ai/useAiFlow'
import { Card } from '../../components/Card'
import { SavedNotice } from '../../components/reports/ExportPdfButton'
import { useErrorMessage } from '../../components/useErrorMessage'
import { AnalysisView, ComparisonTable } from './AnalysisView'
import { ClientMessageDialog } from './ClientMessageDialog'
import { DropZone } from './DropZone'
import { StatsDialog } from './StatsDialog'
import { VideoCard } from './VideoCard'

const selectClass =
  'rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none focus:border-accent'

interface GroupProps {
  projectId: number
  kind: OwnerKind
  name: string
  videos: Video[]
  defaultPlatform: VideoPlatform
  onResults: (video: Video) => void
}

/** One owner (the client or a competitor): drop zone + its videos. */
function VideoGroup({ projectId, kind, name, videos, defaultPlatform, onResults }: GroupProps) {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const actions = useVideoAction(projectId)
  const [platform, setPlatform] = useState<VideoPlatform>(videos[0]?.platform ?? defaultPlatform)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<unknown>(null)

  const upload = async (files: File[]) => {
    setError(null)
    setProgress(0)
    try {
      await uploadVideos(projectId, files, { kind, name, platform }, setProgress)
      await actions.refresh()
    } catch (err) {
      setError(err)
    } finally {
      setProgress(null)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {kind === 'competitor' && <h3 className="text-lg font-semibold text-ink">{name}</h3>}
        <label className="flex items-center gap-2 text-sm text-muted">
          {t('video.platform')}
          <select value={platform} onChange={(e) => setPlatform(e.target.value as VideoPlatform)} className={selectClass}>
            {VIDEO_PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {t(`video.platforms.${p}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <DropZone
        compact={videos.length > 0}
        accept={VIDEO_EXTENSIONS}
        busy={progress !== null}
        progress={progress}
        label={progress !== null ? t('video.uploading') : kind === 'client' ? t('video.drop.client') : t('video.drop.competitor', { name })}
        hint={t('video.drop.hint')}
        onFiles={(files) => void upload(files)}
      />
      {error !== null && <p className="text-red-400">{errorMessage(error)}</p>}
      {videos.length > 0 && (
        <div className="grid gap-3 lg:grid-cols-2">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              onResults={() => onResults(video)}
              onRetry={() => actions.retry.mutate(video.id)}
              onDelete={() => window.confirm(t('video.card.confirmDelete', { name: video.file_name })) && actions.remove.mutate(video.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function VideoProjectPage() {
  const { t } = useTranslation()
  const errorMessage = useErrorMessage()
  const navigate = useNavigate()
  const projectId = Number(useParams().id)
  const { data: project, isLoading, error } = useVideoProject(projectId)
  const { data: tools } = useVideoTools()
  const { data: settings } = useSettings()
  const update = useUpdateVideoProject(projectId)
  const remove = useDeleteVideoProject()
  const actions = useVideoAction(projectId)

  const [extraCompetitors, setExtraCompetitors] = useState<string[]>([])
  const [competitorName, setCompetitorName] = useState('')
  const [statsFor, setStatsFor] = useState<Video | null>(null)
  const [message, setMessage] = useState(false)
  const [mode, setMode] = useState<AiMode | null>(null)
  const [report, setReport] = useState<{ name: string } | null>(null)
  const [reportBusy, setReportBusy] = useState(false)
  const [reportError, setReportError] = useState<unknown>(null)

  const flow = useAiFlow<never>({
    start: (m) => aiPost(`/video-projects/${projectId}/analyze`, { mode: m }),
    parse: (text) => aiPost(`/video-projects/${projectId}/analyze/parse`, { text }),
    onDone: () => {
      setReport(null)
      void actions.refresh()
    },
  })

  if (isLoading) return <p className="text-muted">{t('common.loading')}</p>
  if (!project) return <p className="text-red-400">{errorMessage(error)}</p>

  const clientVideos = project.videos.filter((v) => v.owner_kind === 'client')
  const competitorNames = [
    ...new Set([
      ...project.videos.filter((v) => v.owner_kind === 'competitor').map((v) => v.owner_name),
      ...extraCompetitors,
    ]),
  ]
  const defaultPlatform = clientVideos[0]?.platform ?? 'instagram'
  const busy = project.videos.some((v) => v.status === 'queued' || v.status === 'processing')
  const readyClient = clientVideos.some((v) => v.status === 'ready')
  const withResults = project.videos.filter((v) => Object.keys(v.stats).some((k) => k !== 'platform')).length
  const aiMode = mode ?? settings?.default_ai ?? 'chat'

  const addCompetitor = () => {
    const name = competitorName.trim()
    if (name && !competitorNames.includes(name)) setExtraCompetitors([...extraCompetitors, name])
    setCompetitorName('')
  }

  const makeReport = async () => {
    setReportBusy(true)
    setReportError(null)
    try {
      const saved = await generateVideoReport(projectId)
      setReport(saved)
      void openReport(saved.name)
    } catch (err) {
      setReportError(err)
    } finally {
      setReportBusy(false)
    }
  }

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/video" className="flex items-center gap-1 text-sm text-muted hover:text-ink">
            <ArrowLeft className="size-4" aria-hidden />
            {t('video.backToClients')}
          </Link>
          <h1 className="mt-1 text-3xl font-bold text-ink">{project.client_name}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setMessage(true)}
            className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 font-semibold text-ink shadow-card hover:bg-surface-raised"
          >
            <MessageSquareText className="size-4" aria-hidden />
            {t('video.message.button')}
          </button>
          <button
            type="button"
            onClick={() =>
              window.confirm(t('video.confirmDeleteClient', { name: project.client_name })) &&
              remove.mutate(projectId, { onSuccess: () => navigate('/video') })
            }
            className="flex items-center gap-2 rounded-full border border-line px-4 py-2 text-muted hover:bg-surface-raised hover:text-ink"
          >
            <Trash2 className="size-4" aria-hidden />
            {t('video.deleteClient')}
          </button>
        </div>
      </div>

      {tools && !tools.ffmpeg && <p className="rounded-xl bg-surface-raised p-3 text-red-400">{t('video.tools.noFfmpeg')}</p>}
      {tools?.transcription && !tools.model_downloaded && (
        <p className="flex gap-2 rounded-xl bg-surface-raised p-3 text-sm text-ink">
          <Info className="mt-0.5 size-4 shrink-0 text-accent-text" aria-hidden />
          {t('video.tools.modelDownload', { mb: tools.model_mb })}
        </p>
      )}

      <Card title={t('video.step1.title')} description={t('video.step1.text')}>
        <VideoGroup
          projectId={projectId}
          kind="client"
          name=""
          videos={clientVideos}
          defaultPlatform="instagram"
          onResults={setStatsFor}
        />
        <label className="mt-5 flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">{t('video.notes.label')}</span>
          <textarea
            defaultValue={project.notes}
            rows={2}
            placeholder={t('video.notes.placeholder')}
            onBlur={(e) => e.target.value !== project.notes && update.mutate({ notes: e.target.value })}
            className="rounded-xl border border-line bg-surface-raised px-3 py-2 text-ink outline-none placeholder:text-muted focus:border-accent"
          />
        </label>
      </Card>

      <Card title={t('video.step2.title')} description={t('video.step2.text')}>
        <div className="space-y-8">
          {competitorNames.map((name) => (
            <VideoGroup
              key={name}
              projectId={projectId}
              kind="competitor"
              name={name}
              videos={project.videos.filter((v) => v.owner_kind === 'competitor' && v.owner_name === name)}
              defaultPlatform={defaultPlatform}
              onResults={setStatsFor}
            />
          ))}
          <form
            className="flex flex-wrap gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              addCompetitor()
            }}
          >
            <input
              value={competitorName}
              onChange={(e) => setCompetitorName(e.target.value)}
              placeholder={t('video.step2.placeholder')}
              aria-label={t('video.step2.placeholder')}
              maxLength={80}
              className="min-w-64 flex-1 rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none placeholder:text-muted focus:border-accent"
            />
            <button
              type="submit"
              disabled={!competitorName.trim()}
              className="flex items-center gap-2 rounded-full border border-line px-4 py-2 font-semibold text-ink hover:bg-surface-raised disabled:opacity-50"
            >
              <Plus className="size-4" aria-hidden />
              {t('video.step2.add')}
            </button>
          </form>
        </div>
      </Card>

      <Card title={t('video.step3.title')} description={t('video.step3.text', { done: withResults, total: project.videos.length })}>
        {flow.phase === 'handoff' && flow.handoff ? (
          <HandoffPanel handoff={flow.handoff} fallback={flow.fallback} error={flow.error} onSubmit={flow.submitPasted} />
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-56">
              <AiModeSelect value={aiMode} onChange={setMode} />
            </div>
            <button
              type="button"
              disabled={!readyClient || busy || flow.busy}
              onClick={() => flow.run(aiMode)}
              className="flex items-center gap-2 rounded-full bg-accent-gradient px-6 py-2.5 font-semibold text-on-accent disabled:opacity-50"
            >
              {flow.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
              {flow.busy ? t('video.analyzing') : project.analysis ? t('video.reanalyze') : t('video.analyze')}
            </button>
            {(project.analysis || readyClient) && (
              <button
                type="button"
                disabled={reportBusy || busy}
                onClick={() => void makeReport()}
                className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2.5 font-semibold text-ink shadow-card hover:bg-surface-raised disabled:opacity-60"
              >
                {reportBusy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FileDown className="size-4" aria-hidden />}
                {t('video.pdf')}
              </button>
            )}
          </div>
        )}
        <div className="mt-3 space-y-1 text-sm">
          {!readyClient && !busy && <p className="text-muted">{t('video.needClientVideo')}</p>}
          {busy && <p className="text-accent-text">{t('video.waitProcessing')}</p>}
          {flow.error !== null && flow.phase !== 'handoff' && <p className="text-red-400">{errorMessage(flow.error)}</p>}
          {reportError !== null && <p className="text-red-400">{errorMessage(reportError)}</p>}
          {report && <SavedNotice file={report} />}
        </div>
      </Card>

      <ComparisonTable project={project} />
      <AnalysisView project={project} />

      {statsFor && (
        <StatsDialog
          video={project.videos.find((v) => v.id === statsFor.id) ?? statsFor}
          onClose={() => setStatsFor(null)}
        />
      )}
      {message && <ClientMessageDialog onClose={() => setMessage(false)} />}
    </div>
  )
}
