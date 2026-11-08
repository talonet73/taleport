import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { api, jsonBody } from './client'
import { getToken } from './session'
import type {
  AiEnvelope,
  AppSettings,
  Draft,
  ProviderId,
  ProvidersResponse,
  AppStatus,
  CollectedItem,
  QuotaStatus,
  ScanCell,
  ScanSnapshot,
  SecretName,
  SecretsStatus,
  ThemeDetail,
  TodayOverview,
  Topic,
  TopicData,
  TopicsMeta,
} from './types'

export const queryKeys = {
  settings: ['settings'] as const,
  status: ['status'] as const,
  secrets: ['secrets'] as const,
  topics: ['topics'] as const,
  topic: (id: number) => ['topics', id] as const,
  topicItems: (id: number) => ['topics', id, 'items'] as const,
  topicsMeta: ['topics-meta'] as const,
  scan: ['scan', 'current'] as const,
  quota: ['quota', 'youtube'] as const,
  today: ['today'] as const,
  theme: (id: number) => ['themes', id] as const,
}

// -- AI ------------------------------------------------------------------------------

export function useAiProviders() {
  return useQuery({ queryKey: ['ai', 'providers'], queryFn: () => api<ProvidersResponse>('/ai/providers') })
}

export function useProviderModels(id: ProviderId, enabled: boolean) {
  return useQuery({
    queryKey: ['ai', 'models', id],
    queryFn: () => api<string[]>(`/ai/providers/${id}/models`),
    enabled,
    retry: false,
  })
}

export function useTestProvider() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: ProviderId) =>
      api<{ ok: boolean; model: string; latency_ms: number }>(`/ai/providers/${id}/test`, { method: 'POST' }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.status }),
  })
}

export function copyToClipboard(text: string) {
  return api<{ copied: boolean }>('/app/clipboard', { method: 'POST', body: jsonBody({ text }) })
}

/** POST helper for AI features: returns the envelope (result or handoff). */
export function aiPost<T>(path: string, body: unknown) {
  return api<AiEnvelope<T>>(path, { method: 'POST', body: jsonBody(body) })
}

// -- Drafts --------------------------------------------------------------------------

export function useDrafts(limit = 30) {
  return useQuery({ queryKey: ['drafts', limit], queryFn: () => api<Draft[]>(`/drafts?limit=${limit}`) })
}

export function useBatch(batchId: string | null) {
  return useQuery({
    queryKey: ['drafts', 'batch', batchId],
    queryFn: () => api<Draft[]>(`/drafts?batch_id=${batchId}&limit=100`),
    enabled: !!batchId,
  })
}

/** Every draft action returns the updated draft; caches refresh. */
export function useDraftAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ path, method, body }: { path: string; method: string; body?: unknown }) =>
      api<Draft | undefined>(path, { method, body: body === undefined ? undefined : jsonBody(body) }),
    onSuccess: () => {
      for (const key of [['drafts'], queryKeys.today, ['calendar'], ['archive'], ['results']]) {
        void queryClient.invalidateQueries({ queryKey: key })
      }
    },
  })
}

export function extractFile(fileName: string, fileBase64: string) {
  return api<{ text: string; truncated: boolean; characters: number }>('/content/extract', {
    method: 'POST',
    body: jsonBody({ file_name: fileName, file_base64: fileBase64 }),
  })
}

// -- Analysis ------------------------------------------------------------------------

export function useToday() {
  return useQuery({ queryKey: queryKeys.today, queryFn: () => api<TodayOverview>('/today') })
}

export function useTheme(id: number) {
  return useQuery({ queryKey: queryKeys.theme(id), queryFn: () => api<ThemeDetail>(`/themes/${id}`) })
}

// -- Settings & status ---------------------------------------------------------------

export function useSettings() {
  return useQuery({ queryKey: queryKeys.settings, queryFn: () => api<AppSettings>('/settings') })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (changes: Partial<AppSettings>) =>
      api<AppSettings>('/settings', { method: 'PATCH', body: jsonBody(changes) }),
    onSuccess: (settings) => {
      queryClient.setQueryData(queryKeys.settings, settings)
      for (const key of [queryKeys.status, ['usage'], ['posting-times'], ['calendar']]) {
        void queryClient.invalidateQueries({ queryKey: key })
      }
    },
  })
}

export function useStatus() {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: () => api<AppStatus>('/status'),
    refetchInterval: 60_000,
  })
}

export function useSecrets() {
  return useQuery({ queryKey: queryKeys.secrets, queryFn: () => api<SecretsStatus>('/secrets') })
}

export function useSaveSecret() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, value }: { name: SecretName; value: string }) =>
      api<void>(`/secrets/${name}`, { method: 'PUT', body: jsonBody({ value }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.secrets }),
  })
}

export function useDeleteSecret() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: SecretName) => api<void>(`/secrets/${name}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.secrets }),
  })
}

export function useYouTubeQuota() {
  return useQuery({ queryKey: queryKeys.quota, queryFn: () => api<QuotaStatus>('/quota/youtube') })
}

/** Opens a link in the user's default browser (the app window never navigates away). */
export function openExternal(url: string): void {
  void api<void>('/app/open-url', { method: 'POST', body: jsonBody({ url }) })
}

// -- Topics --------------------------------------------------------------------------

export function useTopics() {
  return useQuery({ queryKey: queryKeys.topics, queryFn: () => api<Topic[]>('/topics') })
}

export function useTopic(id: number | undefined) {
  return useQuery({
    queryKey: queryKeys.topic(id ?? 0),
    queryFn: () => api<Topic>(`/topics/${id}`),
    enabled: id !== undefined,
  })
}

export function useTopicsMeta() {
  return useQuery({
    queryKey: queryKeys.topicsMeta,
    queryFn: () => api<TopicsMeta>('/topics/meta'),
    staleTime: Infinity,
  })
}

export function useTopicItems(id: number) {
  return useQuery({
    queryKey: queryKeys.topicItems(id),
    queryFn: () => api<CollectedItem[]>(`/topics/${id}/items?limit=100`),
  })
}

export function useSaveTopic() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: TopicData }) =>
      id
        ? api<Topic>(`/topics/${id}`, { method: 'PUT', body: jsonBody(data) })
        : api<Topic>('/topics', { method: 'POST', body: jsonBody(data) }),
    onSuccess: (topic) => {
      queryClient.setQueryData(queryKeys.topic(topic.id), topic)
      void queryClient.invalidateQueries({ queryKey: queryKeys.topics, exact: true })
    },
  })
}

export function useSetTopicActive() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api<Topic>(`/topics/${id}/active`, { method: 'PATCH', body: jsonBody({ active }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.topics }),
  })
}

export function useDeleteTopic() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/topics/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.topics }),
  })
}

// -- Scans ---------------------------------------------------------------------------

export function useCurrentScan() {
  return useQuery({
    queryKey: queryKeys.scan,
    queryFn: () => api<ScanSnapshot | null>('/scans/current'),
  })
}

export function useStartScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (topicId?: number) =>
      api<{ scan_id: number }>('/scans', { method: 'POST', body: jsonBody({ topic_id: topicId ?? null }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.scan }),
  })
}

export function useCancelScan() {
  return useMutation({
    mutationFn: () => api<void>('/scans/current/cancel', { method: 'POST' }),
  })
}

// -- Live events ---------------------------------------------------------------------

/** Subscribes to the backend event stream and keeps cached data fresh. */
export function useServerEvents() {
  const queryClient = useQueryClient()
  useEffect(() => {
    const source = new EventSource(`/api/events?t=${encodeURIComponent(getToken())}`)
    const on = (name: string, handler: (data: unknown) => void) =>
      source.addEventListener(name, (event) => handler(JSON.parse((event as MessageEvent).data)))

    on('settings.changed', (data) => queryClient.setQueryData(queryKeys.settings, data))
    on('scan.started', (data) => {
      queryClient.setQueryData(queryKeys.scan, data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.status })
    })
    on('scan.progress', (data) => {
      const cell = data as ScanCell & { scan_id: number }
      queryClient.setQueryData<ScanSnapshot | null>(queryKeys.scan, (scan) =>
        scan && scan.scan_id === cell.scan_id
          ? {
              ...scan,
              cells: scan.cells.map((c) =>
                c.source === cell.source && c.topic_id === cell.topic_id ? { ...c, ...cell } : c,
              ),
            }
          : scan,
      )
    })
    on('scan.finished', (data) => {
      queryClient.setQueryData(queryKeys.scan, data)
      void queryClient.invalidateQueries({ queryKey: queryKeys.status })
      void queryClient.invalidateQueries({ queryKey: queryKeys.topics })
      void queryClient.invalidateQueries({ queryKey: queryKeys.quota })
    })
    on('notification', () => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] })
      void queryClient.invalidateQueries({ queryKey: ['usage'] })
      void queryClient.invalidateQueries({ queryKey: queryKeys.status })
    })
    on('drafts.changed', () => {
      for (const key of [['drafts'], ['calendar'], ['archive'], ['results'], queryKeys.today]) {
        void queryClient.invalidateQueries({ queryKey: key })
      }
    })
    on('videos.changed', () => {
      void queryClient.invalidateQueries({ queryKey: ['video-projects'] })
    })
    on('analysis.finished', () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.today })
      void queryClient.invalidateQueries({ queryKey: ['themes'] })
    })
    return () => source.close()
  }, [queryClient])
}
