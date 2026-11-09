import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, jsonBody } from './client'

export interface VoiceProfile {
  id: number
  name: string
  guide: string
  examples: string[]
  topic_ids: number[]
  sources: string[]
  created_at: string
  updated_at: string
}

export type VoiceProfileInput = Pick<VoiceProfile, 'name' | 'guide' | 'examples' | 'topic_ids' | 'sources'>

/** A voice read from documents by the AI, not saved yet. */
export interface VoiceSuggestion {
  name: string
  guide: string
  examples: string[]
  sources: string[]
}

export interface ReferenceDocument {
  name: string
  text: string
}

export function useVoices() {
  return useQuery({ queryKey: ['voices'], queryFn: () => api<VoiceProfile[]>('/voices') })
}

export function useSaveVoice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number | null; data: VoiceProfileInput }) =>
      id === null
        ? api<VoiceProfile>('/voices', { method: 'POST', body: jsonBody(data) })
        : api<VoiceProfile>(`/voices/${id}`, { method: 'PUT', body: jsonBody(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['voices'] }),
  })
}

export function useDeleteVoice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/voices/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['voices'] }),
  })
}

export const DOCUMENT_EXTENSIONS = ['.docx', '.pdf', '.pptx', '.txt', '.md']
export const MAX_DOCUMENTS = 5
