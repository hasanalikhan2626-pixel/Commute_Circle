import { useEffect, useState } from 'react'

/** Loads data with fn; re-runs when deps change. Returns [data, error, reload]. */
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
  return [state.data, state.error, () => setN((x) => x + 1)]
}

export const Loading = () => <div className="loading">Loading…</div>
export const Err = ({ children }) => (children ? <div className="err" role="alert">{children}</div> : null)

export function Logo({ size = 36 }) {
  return (
    <div className="logo" aria-hidden="true" style={{ width: size, height: size }}>
      <svg width={size * 0.61} height={size * 0.61} viewBox="0 0 22 22">
        <circle cx="11" cy="11" r="7.5" fill="none" stroke="#fff" strokeWidth="2" strokeDasharray="3 2.6" />
        <circle cx="11" cy="3.5" r="2.3" fill="#fff" /><circle cx="4.5" cy="15" r="2.3" fill="#fff" /><circle cx="17.5" cy="15" r="2.3" fill="#fff" />
      </svg>
    </div>
  )
}

export function Av({ name, n, sm }) {
  const i = (name || '').split(' ').map((w) => w[0]).join('').slice(0, 2)
  return <div className={`av${sm ? ' sm' : ''}`}>{i}{n ? <span className="o">{n}</span> : null}</div>
}
