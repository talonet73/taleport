import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, jsonBody } from './client'
import { getToken } from './session'
import type { AiEnvelope, AiMode, Handoff } from './types'

export const VIDEO_PLATFORMS = ['instagram', 'tiktok', 'youtube', 'facebook', 'other'] as const
export type VideoPlatform = (typeof VIDEO_PLATFORMS)[number]
export type OwnerKind = 'client' | 'competitor'
export type VideoStatus = 'queued' | 'processing' | 'ready' | 'failed'

export interface RetentionPoint {
  second: number
  percent: number
}

export interface VideoStats {
  platform?: VideoPlatform
  views?: number
  reach?: number
  likes?: number
  comments?: number
  shares?: number
  saves?: number
  follows?: number
  avg_watch_seconds?: number
  duration?: number
  published?: string
  retention?: RetentionPoint[]
  notes?: string
}

export interface VideoFeatures {
  duration?: number
  orientation?: string
  has_audio?: boolean
  cut_count?: number
  cuts_per_minute?: number
  first_cut_at?: number | null
  silence_ratio?: number
  first_word_at?: number | null
  words_per_minute?: number | null
  hook_text?: string
  speech_error?: string
}

export interface VideoDerived {
  watched_ratio?: number
  interaction_rate?: number
  biggest_drop?: { from_second: number; to_second: number; lost_percent: number }
}

export interface Video {
  id: number
  project_id: number
  owner_kind: OwnerKind
  owner_name: string
  platform: VideoPlatform
  file_name: string
  size: number
  status: VideoStatus
  step: string | null
  error_code: string | null
  features: VideoFeatures
  stats: VideoStats
  stats_via: 'manual' | 'screenshot' | null
  derived: VideoDerived
  frames: number
}

export interface GroupSummary {
  videos: number
  duration: number | null
  cuts_per_minute: number | null
  first_cut_at: number | null
  first_word_at: number | null
  words_per_minute: number | null
  silence_ratio: number | null
  views: number | null
  watched_ratio: number | null
  interaction_rate: number | null
}

export interface VideoGroup {
  kind: OwnerKind
  name: string
  video_ids: number[]
  summary: GroupSummary
}

export interface AnalysisPoint {
  title: string
  detail: string
  videos: number[]
}

export interface VideoAnalysis {
  summary: string
  strengths: AnalysisPoint[]
  weaknesses: AnalysisPoint[]
  competitors: { name: string; what_works: string; weak_spots: string; to_borrow: string }[]
  recommendations: { action: string; why: string; priority: 'high' | 'medium' | 'low' }[]
  videos: { id: number; verdict: string; hook: string; drop_off: string; fix: string }[]
  ideas: string[]
}

export interface VideoProject {
  id: number
  client_name: string
  notes: string
  analysis: VideoAnalysis | null
  analysis_via: string | null
  analyzed_at: string | null
  videos: Video[]
  groups: VideoGroup[]
}

export interface VideoProjectSummary {
  id: number
  client_name: string
  analyzed_at: string | null
  updated_at: string
  videos: number
  client_videos: number
  competitors: number
  busy: number
}

export interface VideoTools {
  ffmpeg: boolean
  transcription: boolean
  model_downloaded: boolean
  model_mb: number
}

export type StatsHandoff = Handoff & { images: number }

const projectKey = (id: number) => ['video-projects', id] as const

export function useVideoTools() {
  return useQuery({ queryKey: ['video-tools'], queryFn: () => api<VideoTools>('/video/tools') })
}

export function useVideoProjects() {
  return useQuery({
    queryKey: ['video-projects'],
    queryFn: () => api<VideoProjectSummary[]>('/video-projects'),
  })
}

export function useVideoProject(id: number) {
  return useQuery({
    queryKey: projectKey(id),
    queryFn: () => api<VideoProject>(`/video-projects/${id}`),
    enabled: Number.isFinite(id),
  })
}

export function useCreateVideoProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (clientName: string) =>
      api<VideoProject>('/video-projects', { method: 'POST', body: jsonBody({ client_name: clientName }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['video-projects'] }),
  })
}

export function useUpdateVideoProject(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (changes: { client_name?: string; notes?: string }) =>
      api<VideoProject>(`/video-projects/${id}`, { method: 'PATCH', body: jsonBody(changes) }),
    onSuccess: (project) => {
      queryClient.setQueryData(projectKey(id), project)
      void queryClient.invalidateQueries({ queryKey: ['video-projects'], exact: true })
    },
  })
}

export function useDeleteVideoProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/video-projects/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['video-projects'] }),
  })
}

/** Video actions that refresh the client's page afterwards. */
export function useVideoAction(projectId: number) {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: projectKey(projectId) })
  return {
    update: useMutation({
      mutationFn: ({ id, changes }: { id: number; changes: Record<string, unknown> }) =>
        api<Video>(`/videos/${id}`, { method: 'PATCH', body: jsonBody(changes) }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: number) => api<void>(`/videos/${id}`, { method: 'DELETE' }),
      onSuccess: refresh,
    }),
    retry: useMutation({
      mutationFn: (id: number) => api<Video>(`/videos/${id}/retry`, { method: 'POST' }),
      onSuccess: refresh,
    }),
    refresh,
  }
}

export function frameUrl(videoId: number, index = 0): string {
  return `/api/videos/${videoId}/frames/${index}?t=${encodeURIComponent(getToken())}`
}

function errorFrom(xhr: XMLHttpRequest): ApiError {
  try {
    const body = JSON.parse(xhr.responseText)
    return new ApiError(body?.error?.code ?? 'generic', body?.error?.params ?? {}, xhr.status)
  } catch {
    return new ApiError(xhr.status ? 'generic' : 'network', {}, xhr.status)
  }
}

/** Multipart POST with upload progress (video files can be large). */
export function postForm<T>(path: string, form: FormData, onProgress?: (share: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api${path}`)
    xhr.setRequestHeader('X-TALeport-Token', getToken())
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded / event.total)
    }
    xhr.onload = () => (xhr.status < 400 ? resolve(JSON.parse(xhr.responseText) as T) : reject(errorFrom(xhr)))
    xhr.onerror = () => reject(new ApiError('network'))
    xhr.send(form)
  })
}

export function uploadVideos(
  projectId: number,
  files: File[],
  owner: { kind: OwnerKind; name: string; platform: VideoPlatform },
  onProgress?: (share: number) => void,
) {
  const form = new FormData()
  for (const file of files) form.append('files', file, file.name)
  form.append('owner_kind', owner.kind)
  form.append('owner_name', owner.name)
  form.append('platform', owner.platform)
  return postForm<Video[]>(`/video-projects/${projectId}/videos`, form, onProgress)
}

export function readStatsFromScreenshots(videoId: number, images: File[], mode: AiMode) {
  const form = new FormData()
  for (const image of images) form.append('images', image, image.name)
  form.append('mode', mode)
  return postForm<AiEnvelope<never> & { video?: Video; handoff?: StatsHandoff }>(
    `/videos/${videoId}/stats/read`,
    form,
  )
}

export function generateVideoReport(projectId: number) {
  return api<{ name: string; size: number; path: string }>(`/video-projects/${projectId}/report`, {
    method: 'POST',
  })
}

export const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi']
export const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp']

export function hasExtension(file: File, extensions: string[]): boolean {
  const name = file.name.toLowerCase()
  return extensions.some((ext) => name.endsWith(ext))
}
