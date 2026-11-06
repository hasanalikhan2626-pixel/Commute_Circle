import { useEffect, useState } from 'react'

export function Card({ title, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="row">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function Alert({ kind = 'error', children }) {
  if (!children) return null
  return <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>{children}</div>
}

export function Badge({ tone = 'neutral', children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return <div className="spinner" role="status"><span className="dot" />{label}</div>
}

export const STATUS_TONE = {
  proposed: 'warn', active: 'ok', dissolved: 'neutral',
  pending: 'warn', accepted: 'ok', declined: 'bad', left: 'neutral',
  open: 'bad', resolved: 'ok', dismissed: 'neutral',
}

/** Loads data with `fn`, re-running when `deps` change. Returns [data, error, reload, setData]. */
export function useLoad(fn, deps = []) {
  const [state, setState] = useState({ data: undefined, error: null })
  const [n, setN] = useState(0)
  useEffect(() => {
    let live = true
    fn().then((data) => live && setState({ data, error: null }))
      .catch((e) => live && setState({ data: null, error: e.message }))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n])
  return [state.data, state.error, () => setN((x) => x + 1), (data) => setState({ data, error: null })]
}
