// The backend opens the UI at `/#t=<token>`. The token is kept in sessionStorage
// (it changes at every launch) and removed from the address.
const TOKEN_KEY = 'taleport.token'

export function initSession(): void {
  const match = window.location.hash.match(/[#&]t=([^&]+)/)
  if (match) {
    sessionStorage.setItem(TOKEN_KEY, decodeURIComponent(match[1]))
    history.replaceState(null, '', window.location.pathname + window.location.search)
  }
}

export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) ?? ''
}
