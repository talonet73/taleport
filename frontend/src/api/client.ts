import { getToken } from './session'

/** Error returned by the backend as `{ error: { code, params } }`; `code` is an i18n key under `errors.`. */
export class ApiError extends Error {
  constructor(
    public code: string,
    public params: Record<string, unknown> = {},
    public status = 0,
  ) {
    super(code)
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        'X-TALeport-Token': getToken(),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError('network')
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const error = body?.error
    throw new ApiError(error?.code ?? 'generic', error?.params ?? {}, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const jsonBody = (value: unknown): RequestInit['body'] => JSON.stringify(value)
