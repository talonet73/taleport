import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, jsonBody } from './client'
import type { SavedReport } from './reports'

export type SavedFile = Omit<SavedReport, 'title'> & { title?: string }

// -- error log -----------------------------------------------------------------------

export type LogLevel = 'info' | 'warning' | 'error'

export interface LogRow {
  id: number
  created_at: string
  level: LogLevel
  source: string
  code: string
  params: Record<string, string | number>
}

export function useLogs(level: LogLevel | '') {
  return useQuery({
    queryKey: ['logs', level],
    queryFn: () =>
      api<{ counts: Record<LogLevel, number>; rows: LogRow[] }>(`/logs?limit=100${level ? `&level=${level}` : ''}`),
  })
}

export function useLogActions() {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['logs'] })
  return {
    exportLog: useMutation({ mutationFn: () => api<SavedFile>('/logs/export', { method: 'POST' }) }),
    clear: useMutation({ mutationFn: () => api<void>('/logs', { method: 'DELETE' }), onSuccess: refresh }),
  }
}

// -- backup --------------------------------------------------------------------------

export interface ImportPreview {
  format: 'taleport-backup' | 'taleport-topic'
  app_version: string | null
  created_at: string | null
  topics: string[]
  has_settings: boolean
  templates: number
}

export interface ImportResult {
  topics: string[]
  skipped: { name: string; reason: 'limit' | 'invalid' }[]
  settings: boolean
  templates: number
}

export function useExportBackup() {
  return useMutation({ mutationFn: () => api<SavedFile & { topics: number }>('/backup/export', { method: 'POST' }) })
}

export function useExportTopic() {
  return useMutation({ mutationFn: (id: number) => api<SavedFile>(`/topics/${id}/export`, { method: 'POST' }) })
}

export function previewImport(text: string) {
  return api<ImportPreview>('/backup/preview', { method: 'POST', body: jsonBody({ text }) })
}

export function useImportBackup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ text, settings }: { text: string; settings: boolean }) =>
      api<ImportResult>('/backup/import', { method: 'POST', body: jsonBody({ text, settings }) }),
    onSuccess: () => {
      for (const key of [['topics'], ['settings'], ['reports'], ['status']]) {
        void queryClient.invalidateQueries({ queryKey: key })
      }
    },
  })
}

// -- updates -------------------------------------------------------------------------

export interface UpdateStatus {
  current: string
  configured: boolean
  auto?: boolean
  checked_at?: string
  available?: boolean
  latest?: { version: string; url: string; installer_url: string | null; notes: string }
}

export function useUpdates() {
  return useQuery({ queryKey: ['updates'], queryFn: () => api<UpdateStatus>('/updates') })
}

export function useCheckUpdates() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api<UpdateStatus>('/updates/check', { method: 'POST' }),
    onSuccess: (data) => queryClient.setQueryData(['updates'], (old: UpdateStatus | undefined) => ({ ...old, ...data })),
  })
}

export function openRelease() {
  return api<void>('/updates/open', { method: 'POST' })
}

// -- clean-up ------------------------------------------------------------------------

export function useCleanup() {
  return useMutation({
    mutationFn: () =>
      api<{ items: number; logs: number; notifications: number }>('/maintenance/cleanup', { method: 'POST' }),
  })
}
