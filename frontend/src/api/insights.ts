import { useQuery } from '@tanstack/react-query'

import { api } from './client'
import type { ThemeTrend } from './types'

// Mirrors backend/taleport/ask/functions.py

export interface KeywordRow {
  term: string
  count: number
  share: number
}
export interface TopKeywords {
  kind: 'keyword' | 'hashtag'
  total_items: number
  rows: KeywordRow[]
}
export interface ChangeRow {
  term: string
  current: number
  previous: number
  change_pct: number | null
}
export interface Changes {
  previous: { start: string; end: string }
  has_history: boolean
  emerging: ChangeRow[]
  declining: ChangeRow[]
}
export interface TermTrend {
  days: string[]
  series: { term: string; values: number[] }[]
}
export interface Groups {
  groups: { key: string; items: number; top: { term: string; count: number }[] }[]
}
export interface ThemeRow {
  id: number
  title: string
  day: string
  score: number
  trend: ThemeTrend
  item_count: number
  topic_id: number
  topic_name: string
}
export interface ComparePeriods {
  kind: string
  period_a: { start: string; end: string }
  period_b: { start: string; end: string }
  rows: { term: string; a: number; b: number }[]
}
export interface PostPerformance {
  rows: {
    platform: string
    generated: number
    published: number
    with_results: number
    avg_likes: number | null
    avg_comments: number | null
    avg_shares: number | null
    avg_views: number | null
  }[]
  metrics_available: boolean
}
export interface ScopeInfo {
  start: string
  end: string
  topics: number[] | null
  languages: string[] | null
  sources: string[] | null
}

export interface TrendsDashboard {
  scope: ScopeInfo
  keywords: TopKeywords
  hashtags: TopKeywords
  changes: Changes
  trend: TermTrend
  cloud: KeywordRow[]
  by_language: Groups
  by_source: Groups
}

export interface WeekOverview {
  scope: ScopeInfo
  stats: { items: number; themes: number; generated: number; published: number }
  daily: { days: string[]; totals: number[]; by_source: { source: string; values: number[] }[] }
  themes: { rows: ThemeRow[] }
  keywords: TopKeywords
  posts: PostPerformance
}

export type AskStep =
  | { function: 'top_keywords'; scope: ScopeInfo; result: TopKeywords }
  | { function: 'emerging_keywords'; scope: ScopeInfo; result: Changes }
  | { function: 'topic_trend'; scope: ScopeInfo; result: TermTrend }
  | { function: 'compare_periods'; scope: { period_a: ScopeInfo; period_b: ScopeInfo }; result: ComparePeriods }
  | { function: 'compare_languages'; scope: ScopeInfo; result: Groups }
  | { function: 'compare_sources'; scope: ScopeInfo; result: Groups }
  | { function: 'top_themes'; scope: ScopeInfo; result: { rows: ThemeRow[] } }
  | { function: 'post_performance'; scope: ScopeInfo; result: PostPerformance }

export interface AskResult {
  title: string
  question?: string
  preset?: string
  /** The validated plan: sent back to build the PDF (the backend re-runs it). */
  plan?: unknown
  steps: AskStep[]
}

export interface TrendsQuery {
  period: 'last_7_days' | 'last_30_days' | 'custom'
  start?: string
  end?: string
  topics: number[]
  language: string
}

export function useTrends(q: TrendsQuery) {
  const params = new URLSearchParams({ period: q.period })
  if (q.period === 'custom' && q.start && q.end) {
    params.set('start', q.start)
    params.set('end', q.end)
  }
  if (q.topics.length) params.set('topics', q.topics.join(','))
  if (q.language) params.set('language', q.language)
  const ready = q.period !== 'custom' || (!!q.start && !!q.end && q.start <= q.end)
  return useQuery({
    queryKey: ['trends', params.toString()],
    queryFn: () => api<TrendsDashboard>(`/trends?${params}`),
    enabled: ready,
  })
}

export function useWeek() {
  return useQuery({ queryKey: ['week'], queryFn: () => api<WeekOverview>('/week') })
}

export function useAskPresets() {
  return useQuery({ queryKey: ['ask', 'presets'], queryFn: () => api<string[]>('/ask/presets'), staleTime: Infinity })
}
