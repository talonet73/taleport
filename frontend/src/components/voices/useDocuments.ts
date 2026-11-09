import { useState } from 'react'

import { readAsBase64 } from '../../api/files'
import { extractFile } from '../../api/hooks'
import { MAX_DOCUMENTS, type ReferenceDocument } from '../../api/voices'

export interface LoadedDocument extends ReferenceDocument {
  characters: number
  truncated: boolean
}

/** Reference documents read on the user's PC (Word, PDF, PowerPoint, text). */
export function useDocuments() {
  const [documents, setDocuments] = useState<LoadedDocument[]>([])
  const [reading, setReading] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const add = async (files: File[]) => {
    setError(null)
    setReading(true)
    try {
      const loaded: LoadedDocument[] = []
      for (const file of files.slice(0, MAX_DOCUMENTS - documents.length)) {
        const result = await extractFile(file.name, await readAsBase64(file))
        loaded.push({ name: file.name, text: result.text, characters: result.characters, truncated: result.truncated })
      }
      setDocuments((current) => [...current, ...loaded].slice(0, MAX_DOCUMENTS))
    } catch (err) {
      setError(err)
    } finally {
      setReading(false)
    }
  }

  return {
    documents,
    reading,
    error,
    add,
    remove: (name: string) => setDocuments((current) => current.filter((d) => d.name !== name)),
    clear: () => setDocuments([]),
    payload: documents.map(({ name, text }) => ({ name, text })),
  }
}
