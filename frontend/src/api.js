// Thin fetch wrapper: attaches the JWT, parses errors into readable messages.
const TOKEN_KEY = 'cc_token'

export const token = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } },
  set: (t) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ } },
}

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

function messageFrom(body, status) {
  const d = body?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d.map((e) => {
      const field = e.loc?.filter((x) => x !== 'body').join('.')
      const msg = (e.msg || '').replace(/^Value error, /, '')
      return field ? `${field}: ${msg}` : msg
    }).join('\n')
  }
  return `Request failed (${status})`
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const t = token.get()
  if (t) headers.Authorization = `Bearer ${t}`
  let payload
  if (form) {
    payload = new URLSearchParams(form)
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(path, { method, headers, body: payload })
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && t) { token.clear(); window.dispatchEvent(new Event('cc:logout')) }
    throw new ApiError(messageFrom(data, res.status), res.status)
  }
  return data
}

export const DAY_LABELS = { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat' }
export const pkr = (n) => `PKR ${Math.round(n).toLocaleString('en-PK')}`
export const fmtDate = (iso) =>
  new Date(iso + (iso.length === 10 ? 'T00:00:00' : '')).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
