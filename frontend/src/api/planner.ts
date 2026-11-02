import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, jsonBody } from './client'
import type { Draft, Platform, PostResults, PriorityReason } from './types'

// -- Calendar ------------------------------------------------------------------------

export interface PostingTime {
  platform: Platform
  default: string
  custom: string | null
  time: string
  learned: { time: string; posts: number; average: number } | null
}

export interface CalendarEntry {
  id: number
  platform: Platform
  language: string
  label: string
  preview: string
  status: Draft['status']
  topic_id: number | null
  day: string | null
  time: string | null
  url?: string | null
}

export interface CalendarData {
  start: string
  end: string
  entries: CalendarEntry[]
  unscheduled: CalendarEntry[]
  posting_times: PostingTime[]
}

export function useCalendar(start: string, end: string) {
  return useQuery({
    queryKey: ['calendar', start, end],
    queryFn: () => api<CalendarData>(`/calendar?start=${start}&end=${end}`),
    placeholderData: keepPreviousData,
  })
}

export function usePostingTimes() {
  return useQuery({ queryKey: ['posting-times'], queryFn: () => api<PostingTime[]>('/posting-times') })
}

function invalidateDrafts(queryClient: ReturnType<typeof useQueryClient>) {
  for (const key of ['calendar', 'drafts', 'archive', 'today', 'results', 'posting-times']) {
    void queryClient.invalidateQueries({ queryKey: [key] })
  }
}

export function useMoveDraft() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, day, time }: { id: number; day: string; time?: string }) =>
      api<Draft>(`/calendar/${id}`, { method: 'PUT', body: jsonBody({ day, time: time ?? null }) }),
    onSuccess: () => invalidateDrafts(queryClient),
  })
}

// -- Results -------------------------------------------------------------------------

export interface PlatformResults {
  platform: Platform
  posts: number
  likes: number | null
  comments: number | null
  shares: number | null
  views: number | null
  interactions: number
}

export interface ResultsSummary {
  posts: number
  platforms: PlatformResults[]
  reasons: PriorityReason[]
}

export function useResultsSummary() {
  return useQuery({ queryKey: ['results'], queryFn: () => api<ResultsSummary>('/results/summary') })
}

export function useSaveResults() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, results }: { id: number; results: PostResults }) =>
      api<{ results: PostResults | null }>(`/drafts/${id}/results`, { method: 'PUT', body: jsonBody(results) }),
    onSuccess: () => invalidateDrafts(queryClient),
  })
}

// -- Archive -------------------------------------------------------------------------

export interface ArchivePost extends Draft {
  topic_name: string | null
  results: PostResults | null
}

export interface ArchiveTheme {
  id: number
  topic_id: number
  topic_name: string
  day: string
  title: string
  summary: string | null
  score: number
  trend: 'up' | 'down' | 'flat' | 'new'
  item_count: number
  related_terms: string[]
  drafts: number
  published: number
}

export interface Page<T> {
  total: number
  rows: T[]
}

export type ArchiveFilters = Record<string, string | number | undefined>

function query(filters: ArchiveFilters) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  return params.toString()
}

export function useArchivePosts(filters: ArchiveFilters) {
  return useQuery({
    queryKey: ['archive', 'posts', filters],
    queryFn: () => api<Page<ArchivePost>>(`/archive/posts?${query(filters)}`),
    placeholderData: keepPreviousData,
  })
}

export function useArchiveThemes(filters: ArchiveFilters) {
  return useQuery({
    queryKey: ['archive', 'themes', filters],
    queryFn: () => api<Page<ArchiveTheme>>(`/archive/themes?${query(filters)}`),
    placeholderData: keepPreviousData,
  })
}

// -- Notifications -------------------------------------------------------------------

export interface AppNotification {
  id: number
  created_at: string
  kind: 'spike' | 'scan_completed' | 'scan_recovered' | 'source_failing' | 'spend_near' | 'spend_reached'
  params: Record<string, string | number>
  link: string | null
  read: boolean
}

export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<{ unread: number; rows: AppNotification[] }>('/notifications'),
  })
}

export function useMarkNotificationsRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ids?: number[]) =>
      api<void>('/notifications/read', { method: 'POST', body: jsonBody({ ids: ids ?? null }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

export function useClearNotifications() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>('/notifications/read', { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

// -- AI spend ------------------------------------------------------------------------

export interface UsageRow {
  id: number
  created_at: string
  provider: string
  model: string
  feature: string
  input_tokens: number
  output_tokens: number
  cost_usd: number | null
  cost_source: 'provider' | 'estimate' | 'free' | 'unknown'
}

export interface UsageData {
  month_total_usd: number
  cap_usd: number | null
  warn_percent: number
  cap_reached: boolean
  by_provider: { provider: string; calls: number; cost_usd: number; unknown: number }[]
  recent: UsageRow[]
}

export function useUsage() {
  return useQuery({ queryKey: ['usage'], queryFn: () => api<UsageData>('/ai/usage') })
}
