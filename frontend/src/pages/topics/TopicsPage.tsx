import { Info, Pencil, Plus, RefreshCw, Share2, Tags, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import {
  useCurrentScan,
  useDeleteTopic,
  useSetTopicActive,
  useStartScan,
  useTopics,
  useTopicsMeta,
} from '../../api/hooks'
import type { Topic } from '../../api/types'
import { useExportTopic } from '../../api/system'
import { Card } from '../../components/Card'
import { SavedNotice } from '../../components/reports/ExportPdfButton'
import { Toggle } from '../../components/Toggle'
import { useErrorMessage } from '../../components/useErrorMessage'
import { ImportButton } from '../settings/SystemCards'
import { editionLabel } from './editionLabel'

export function TopicsPage() {
  const { t } = useTranslation()
  const { data: topics = [], isLoading } = useTopics()
  const { data: meta } = useTopicsMeta()
  const startScan = useStartScan()
  const { data: scan } = useCurrentScan()
  const errorMessage = useErrorMessage()
  const max = meta?.max_topics ?? 10
  const atLimit = topics.length >= max
  const scanning = scan?.status === 'running'

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink">{t('topics.title')}</h1>
          <p className="mt-1 text-muted">{t('topics.count', { count: topics.length, max })}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {!atLimit && <ImportButton label={t('topics.importFile')} />}
          <button
            type="button"
            disabled={!topics.some((tp) => tp.active) || scanning || startScan.isPending}
            onClick={() => startScan.mutate(undefined)}
            className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2.5 font-semibold text-ink shadow-card hover:bg-surface-raised disabled:opacity-50"
          >
            <RefreshCw className={`size-4 ${scanning ? 'animate-spin' : ''}`} aria-hidden />
            {t('topics.scanAll')}
          </button>
          {atLimit ? (
            <span className="rounded-full bg-surface px-4 py-2.5 text-muted ring-1 ring-line">
              {t('topics.limitReached', { max })}
            </span>
          ) : (
            <Link
              to="/topics/new"
              className="flex items-center gap-2 rounded-full bg-accent-gradient px-4 py-2.5 font-semibold text-on-accent shadow-card"
            >
              <Plus className="size-4" aria-hidden />
              {t('topics.new')}
            </Link>
          )}
        </div>
      </div>
      {startScan.isError && <p className="text-red-400">{errorMessage(startScan.error)}</p>}

      {!isLoading && topics.length === 0 && (
        <Card className="flex items-center gap-5">
          <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-accent-gradient text-on-accent">
            <Tags className="size-7" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-lg font-semibold text-ink">{t('topics.emptyTitle')}</p>
            <p className="max-w-prose text-muted">{t('topics.emptyBody', { max })}</p>
          </div>
          <Link
            to="/topics/new"
            className="rounded-full bg-accent-gradient px-4 py-2.5 font-semibold text-on-accent"
          >
            {t('topics.new')}
          </Link>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        {topics.map((topic) => (
          <TopicCard key={topic.id} topic={topic} scanning={scanning} />
        ))}
      </div>

      <p className="flex max-w-prose items-start gap-2 text-sm text-muted">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
        {t('topics.notMonitored')}
      </p>
    </div>
  )
}

function TopicCard({ topic, scanning }: { topic: Topic; scanning: boolean }) {
  const { t, i18n } = useTranslation()
  const setActive = useSetTopicActive()
  const remove = useDeleteTopic()
  const startScan = useStartScan()
  const [confirming, setConfirming] = useState(false)
  const share = useExportTopic()
  const keywordCount = Object.values(topic.keywords).reduce((n, list) => n + (list?.length ?? 0), 0)

  return (
    <Card className={topic.active ? '' : 'opacity-70'}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to={`/topics/${topic.id}`} className="text-lg font-semibold text-ink hover:underline">
            {topic.name}
          </Link>
          {topic.description && <p className="mt-1 line-clamp-2 text-muted">{topic.description}</p>}
        </div>
        <label className="flex shrink-0 items-center gap-2 text-sm text-muted">
          {topic.active ? t('topics.active') : t('topics.paused')}
          <Toggle
            checked={topic.active}
            label={t('topics.activeToggle', { name: topic.name })}
            onChange={(active) => setActive.mutate({ id: topic.id, active })}
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {topic.editions.map((code) => (
          <span key={code} className="rounded-full bg-surface-raised px-3 py-1 text-sm text-ink">
            {editionLabel(code, i18n.language)}
          </span>
        ))}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3">
        <Stat label={t('topics.keywordsStat')} value={keywordCount} />
        <Stat label={t('topics.sourcesStat')} value={topic.sources.length} />
        <Stat label={t('topics.itemsTodayStat')} value={topic.items_today ?? 0} />
      </dl>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Link
          to={`/topics/${topic.id}`}
          className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 font-medium text-ink hover:bg-surface-raised"
        >
          <Pencil className="size-4" aria-hidden />
          {t('topics.edit')}
        </Link>
        <button
          type="button"
          disabled={scanning || startScan.isPending}
          onClick={() => startScan.mutate(topic.id)}
          className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 font-medium text-ink hover:bg-surface-raised disabled:opacity-50"
        >
          <RefreshCw className="size-4" aria-hidden />
          {t('topics.scanOne')}
        </button>
        <button
          type="button"
          disabled={share.isPending}
          onClick={() => share.mutate(topic.id)}
          className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 font-medium text-ink hover:bg-surface-raised disabled:opacity-50"
        >
          <Share2 className="size-4" aria-hidden />
          {t('topics.share')}
        </button>
        <div className="ml-auto">
          {confirming ? (
            <span className="flex items-center gap-2 text-sm">
              <span className="text-muted">{t('topics.confirmDelete')}</span>
              <button
                type="button"
                onClick={() => remove.mutate(topic.id)}
                className="rounded-xl bg-red-500/90 px-3 py-2 font-semibold text-white"
              >
                {t('common.delete')}
              </button>
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="rounded-xl border border-line px-3 py-2 text-ink"
              >
                {t('common.cancel')}
              </button>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              aria-label={t('topics.deleteNamed', { name: topic.name })}
              className="rounded-xl p-2 text-muted hover:bg-surface-raised hover:text-ink"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          )}
        </div>
      </div>
      {share.data && (
        <div className="mt-3">
          <SavedNotice file={share.data} />
        </div>
      )}
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-surface-raised px-3 py-2">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-xl font-bold text-ink">{value}</dd>
    </div>
  )
}
