import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, jsonBody } from './client'
import { getToken } from './session'

export type ReportKind = 'daily' | 'weekly' | 'trends' | 'ask' | 'custom'
export type ReportTheme = 'light' | 'dark'

export const REPORT_SECTIONS = [
  'summary',
  'themes',
  'keywords',
  'changes',
  'trend',
  'compare',
  'posts',
  'results',
] as const
export type ReportSection = (typeof REPORT_SECTIONS)[number]

export interface SavedReport {
  name: string
  size: number
  path: string
  title: string
}

export interface ReportFile {
  name: string
  size: number
  modified: string
}

export interface CustomReportParams {
  title: string
  period: { preset: string; start?: string | null; end?: string | null }
  filters: { topics?: number[] | null; languages?: string[] | null }
  sections: ReportSection[]
  theme?: ReportTheme | null
}

export interface ReportTemplate {
  id: number
  name: string
  params: CustomReportParams
  created_at: string
  last_run_at: string | null
}

export function useReportFiles() {
  return useQuery({ queryKey: ['reports', 'files'], queryFn: () => api<ReportFile[]>('/reports/files') })
}

/** Builds a report and saves it in the exports folder; returns the file. */
export function useGenerateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, body }: { kind: ReportKind; body: unknown }) =>
      api<SavedReport>(`/reports/${kind}`, { method: 'POST', body: jsonBody(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reports', 'files'] }),
  })
}

export function openReport(name: string, folder = false) {
  return api<void>('/reports/open', { method: 'POST', body: jsonBody({ name, folder }) })
}

/** Direct link to the file (works in a normal browser too: the token goes in the query). */
export function reportUrl(name: string): string {
  return `/api/reports/files/${encodeURIComponent(name)}?t=${encodeURIComponent(getToken())}`
}

// -- templates -----------------------------------------------------------------------

export function useReportTemplates() {
  return useQuery({ queryKey: ['reports', 'templates'], queryFn: () => api<ReportTemplate[]>('/reports/templates') })
}

export function useSaveTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, name, params }: { id?: number; name: string; params: CustomReportParams }) =>
      api<ReportTemplate>(id ? `/reports/templates/${id}` : '/reports/templates', {
        method: id ? 'PUT' : 'POST',
        body: jsonBody({ name, params }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reports', 'templates'] }),
  })
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/reports/templates/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reports', 'templates'] }),
  })
}

export function useRunTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<SavedReport>(`/reports/templates/${id}/run`, { method: 'POST' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

// -- cover logo ----------------------------------------------------------------------

export function useReportLogo() {
  return useQuery({
    queryKey: ['reports', 'logo'],
    queryFn: () => api<{ custom: boolean; name: string | null }>('/reports/logo'),
  })
}

export function useSetReportLogo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { file_name: string; file_base64: string } | null) => {
      if (body) await api<{ custom: boolean }>('/reports/logo', { method: 'PUT', body: jsonBody(body) })
      else await api<void>('/reports/logo', { method: 'DELETE' })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reports', 'logo'] }),
  })
}
