const BASE = ''

let _onUnauthorized = null

export function setOnUnauthorized(callback) {
  _onUnauthorized = callback
}

export async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (res.status === 401 && !path.startsWith('/api/auth/') && !path.startsWith('/api/setup/')) {
    if (_onUnauthorized) _onUnauthorized()
    throw new Error('Session expired')
  }
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}
