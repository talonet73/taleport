import { ChevronRight, Clapperboard, MessageSquareText, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router'

import { useCreateVideoProject, useVideoProjects } from '../../api/video'
import { Card } from '../../components/Card'
import { useErrorMessage } from '../../components/useErrorMessage'
import { ClientMessageDialog } from './ClientMessageDialog'

export function VideoProjectsPage() {
  const { t, i18n } = useTranslation()
  const errorMessage = useErrorMessage()
  const navigate = useNavigate()
  const { data: projects = [], isLoading } = useVideoProjects()
  const create = useCreateVideoProject()
  const [name, setName] = useState('')
  const [message, setMessage] = useState(false)
  const date = new Intl.DateTimeFormat(i18n.language, { day: 'numeric', month: 'short', year: 'numeric' })

  const submit = () =>
    name.trim() && create.mutate(name.trim(), { onSuccess: (project) => navigate(`/video/${project.id}`) })

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('nav.video')}</h1>
          <p className="mt-1 max-w-prose text-muted">{t('video.subtitle')}</p>
        </div>
        <button
          type="button"
          onClick={() => setMessage(true)}
          className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 font-semibold text-ink shadow-card hover:bg-surface-raised"
        >
          <MessageSquareText className="size-4" aria-hidden />
          {t('video.message.button')}
        </button>
      </div>

      <Card title={t('video.new.title')}>
        <form
          className="flex flex-wrap gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('video.new.placeholder')}
            aria-label={t('video.new.placeholder')}
            maxLength={80}
            className="min-w-64 flex-1 rounded-xl border border-line bg-surface-raised px-3 py-2.5 text-ink outline-none placeholder:text-muted focus:border-accent"
          />
          <button
            type="submit"
            disabled={!name.trim() || create.isPending}
            className="flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-semibold text-on-accent disabled:opacity-50"
          >
            <Plus className="size-4" aria-hidden />
            {t('video.new.create')}
          </button>
        </form>
        {create.isError && <p className="mt-2 text-red-400">{errorMessage(create.error)}</p>}
      </Card>

      {!isLoading && projects.length === 0 && (
        <Card title={t('video.empty.title')}>
          <ol className="grid gap-4 md:grid-cols-3">
            {(['one', 'two', 'three'] as const).map((step, i) => (
              <li key={step} className="rounded-2xl bg-surface-raised p-4">
                <span className="grid size-8 place-items-center rounded-full bg-accent-gradient font-bold text-on-accent">{i + 1}</span>
                <p className="mt-3 font-semibold text-ink">{t(`video.empty.${step}.title`)}</p>
                <p className="mt-1 text-sm text-muted">{t(`video.empty.${step}.text`)}</p>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {projects.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {projects.map((p) => (
            <li key={p.id}>
              <Link
                to={`/video/${p.id}`}
                className="flex items-center gap-4 rounded-card border border-line bg-surface p-5 shadow-card hover:bg-surface-raised"
              >
                <Clapperboard className="size-8 shrink-0 text-accent-text" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-lg font-semibold text-ink">{p.client_name}</p>
                  <p className="text-sm text-muted">
                    {t('video.list.counts', { videos: p.client_videos, competitors: p.competitors })}
                  </p>
                  <p className="text-sm text-accent-text">
                    {p.busy > 0
                      ? t('video.list.busy', { count: p.busy })
                      : p.analyzed_at
                        ? t('video.list.analyzed', { date: date.format(new Date(p.analyzed_at)) })
                        : t('video.list.notAnalyzed')}
                  </p>
                </div>
                <ChevronRight className="size-5 text-muted" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {message && <ClientMessageDialog onClose={() => setMessage(false)} />}
    </div>
  )
}
