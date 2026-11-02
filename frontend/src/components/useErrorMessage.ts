import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'

type CodedError = { code: string | null; params?: Record<string, unknown> }

/** Turns any thrown error (or a `{code, params}` from the backend) into a translated message. */
export function useErrorMessage() {
  const { t } = useTranslation()
  return (error: unknown): string => {
    let code = 'generic'
    let params: Record<string, unknown> = {}
    if (error instanceof ApiError) {
      code = error.code
      params = error.params
    } else if (error && typeof error === 'object' && 'code' in error) {
      code = (error as CodedError).code ?? 'generic'
      params = (error as CodedError).params ?? {}
    }
    return t(`errors.${code}`, { ...params, defaultValue: t('errors.generic') })
  }
}
