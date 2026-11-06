// Fetch wrapper: attaches the JWT and turns API errors into readable messages.
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
  if (Array.isArray(d)) return d.map((e) => (e.msg || '').replace(/^Value error, /, '')).join('\n')
  return `Something went wrong (${status})`
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const t = token.get()
  if (t) headers.Authorization = `Bearer ${t}`
  let payload
  if (form) payload = new URLSearchParams(form)
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(path, { method, headers, body: payload })
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && t) { token.clear(); window.dispatchEvent(new Event('cc:logout')) }
    throw new ApiError(messageFrom(data, res.status), res.status)
  }
  return data
}

export async function download(path, filename) {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${token.get()}` } })
  if (!res.ok) throw new ApiError('Download failed', res.status)
  const url = URL.createObjectURL(await res.blob())
  Object.assign(document.createElement('a'), { href: url, download: filename }).click()
  URL.revokeObjectURL(url)
}

// Formatting helpers (same as the prototype)
export const rs = (v) => 'Rs ' + Math.round(v || 0).toLocaleString('en-PK')
export const k1 = (v) => (v ?? 0).toFixed(1)
export const sa = (a = '') => a.replace('Gulshan-e-Iqbal', 'Gulshan').replace('Gulistan-e-Johar', 'Johar')
export const ini = (n = '') => n.split(' ').map((w) => w[0]).join('').slice(0, 2)
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
export const fmt = (iso) => { if (!iso) return ''; const d = new Date(iso.slice(0, 10) + 'T12:00:00'); return `${DOW[d.getDay()]} ${d.getDate()} ${MON[d.getMonth()]}` }
export const phone = (p) => (p && p.startsWith('+92') ? '0' + p.slice(3, 6) + ' ' + p.slice(6) : p || '')
