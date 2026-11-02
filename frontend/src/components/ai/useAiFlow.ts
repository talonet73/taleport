import { useState } from 'react'

import type { AiEnvelope, AiMode, Handoff } from '../../api/types'

type Phase = 'idle' | 'running' | 'handoff' | 'done'

interface Options<T> {
  start: (mode: AiMode) => Promise<AiEnvelope<T>>
  parse: (text: string) => Promise<AiEnvelope<T>>
  onDone: (envelope: AiEnvelope<T>) => void
}

/**
 * Shared state machine for AI features: run with a provider, or hand off to the user's chat
 * and validate the pasted answer. Errors are kept for display (translated by the caller).
 */
export function useAiFlow<T>({ start, parse, onDone }: Options<T>) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [handoff, setHandoff] = useState<Handoff | null>(null)
  const [fallback, setFallback] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  const finish = (envelope: AiEnvelope<T>) => {
    if (envelope.handoff) {
      setHandoff(envelope.handoff)
      setFallback(envelope.fallback ?? null)
      setPhase('handoff')
      return
    }
    setPhase('done')
    onDone(envelope)
  }

  const run = async (mode: AiMode) => {
    setError(null)
    setPhase('running')
    try {
      finish(await start(mode))
    } catch (err) {
      setError(err)
      setPhase('idle')
    }
  }

  const submitPasted = async (text: string) => {
    setError(null)
    try {
      const envelope = await parse(text)
      setPhase('done')
      onDone(envelope)
    } catch (err) {
      setError(err)
    }
  }

  const reset = () => {
    setPhase('idle')
    setHandoff(null)
    setFallback(null)
    setError(null)
  }

  return { phase, handoff, fallback, error, run, submitPasted, reset, busy: phase === 'running' }
}
