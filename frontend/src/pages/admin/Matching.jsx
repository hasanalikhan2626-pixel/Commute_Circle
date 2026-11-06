import { useState } from 'react'
import { api, pkr, token } from '../../api'
import { Alert, Card, Spinner, useLoad } from '../../components/ui'

const ALGOS = {
  compatibility: 'Compatibility-weighted (proposed)',
  greedy: 'Greedy nearest-neighbour (baseline)',
  cluster: 'Geographic k-means clustering',
}
const SHORT = { compatibility: 'Compatibility', greedy: 'Greedy', cluster: 'k-means' }
const COLS = [
  ['match_rate', 'Match rate', (v) => `${(v * 100).toFixed(1)}%`, 'max'],
  ['circles', 'Circles', (v) => v],
  ['avg_circle_size', 'Avg size', (v) => v.toFixed(2)],
  ['avg_score', 'Avg compatibility', (v) => v.toFixed(3), 'max'],
  ['avg_detour_km', 'Avg detour (km)', (v) => v.toFixed(2), 'min'],
  ['avg_shared_days', 'Shared days/wk', (v) => v.toFixed(2), 'max'],
  ['weekly_fuel_pkr_saved', 'Fuel saved/wk', pkr, 'max'],
  ['weekly_co2_kg_saved', 'CO₂ saved/wk (kg)', (v) => v, 'max'],
  ['runtime_ms', 'Runtime (ms)', (v) => v, 'min'],
]

export default function Matching() {
  const [algo, setAlgo] = useState('compatibility')
  const [cmp, setCmp] = useState(null)
  const [msg, setMsg] = useState({})
  const [busy, setBusy] = useState(false)
  const [runs, , reloadRuns] = useLoad(() => api('/api/admin/runs'))

  const compare = async () => {
    setBusy(true); setMsg({})
    try { setCmp(await api('/api/admin/compare', { method: 'POST' })) } catch (e) { setMsg({ err: e.message }) } finally { setBusy(false) }
  }
  const run = async () => {
    if (!confirm(`Create circles with "${ALGOS[algo]}"? Students will be asked to accept.`)) return
    setBusy(true); setMsg({})
    try {
      const r = await api('/api/admin/match', { method: 'POST', body: { algorithm: algo } })
      setMsg({ ok: `Created ${r.circles_created} circles covering ${r.students_matched} of ${r.pool_size} students.` })
      setCmp(null); reloadRuns()
    } catch (e) { setMsg({ err: e.message }) } finally { setBusy(false) }
  }
  const exportCsv = async () => {
    const res = await fetch('/api/admin/research-export', { headers: { Authorization: `Bearer ${token.get()}` } })
    if (!res.ok) { setMsg({ err: 'Export failed' }); return }
    const url = URL.createObjectURL(await res.blob())
    Object.assign(document.createElement('a'), { href: url, download: 'commutecircle-research.csv' }).click()
    URL.revokeObjectURL(url)
  }
  const best = (key, dir) => cmp && (dir === 'min' ? Math.min : Math.max)(...cmp.map((r) => r[key]))

  return (
    <div className="stack">
      <Card title="Run matching">
        <p className="muted">Matching only considers students who are seeking and not already in a circle. Existing circles and student profiles are never changed.</p>
        <div className="row wrap">
          <select value={algo} onChange={(e) => setAlgo(e.target.value)}>
            {Object.entries(ALGOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <button className="btn" onClick={compare} disabled={busy}>Compare algorithms (dry run)</button>
          <button className="btn btn-primary" onClick={run} disabled={busy}>Create circles</button>
          <button className="btn btn-ghost" onClick={exportCsv}>Download research export (CSV)</button>
        </div>
        <Alert kind="ok">{msg.ok}</Alert><Alert>{msg.err}</Alert>
      </Card>

      {cmp && (
        <Card title={`Comparison on the current pool (${cmp[0]?.pool_size ?? 0} students)`}>
          <div className="scroll">
            <table className="table">
              <thead><tr><th>Algorithm</th>{COLS.map(([k, l]) => <th key={k}>{l}</th>)}</tr></thead>
              <tbody>
                {cmp.map((r) => (
                  <tr key={r.algorithm}>
                    <td className="name">{SHORT[r.algorithm]}</td>
                    {COLS.map(([k, , f, dir]) => <td key={k} className={dir && r[k] === best(k, dir) ? 'best' : ''}>{f(r[k])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">Greedy = nearest-neighbour baseline; k-means = geographic clustering; Compatibility = proposed method. Bold marks the best value in each column. Nothing is saved until you create circles.</p>
        </Card>
      )}

      <Card title="Run history">
        {!runs ? <Spinner /> : runs.length === 0 ? <p className="muted">No runs yet.</p> : (
          <div className="scroll">
            <table className="table">
              <thead><tr><th>When</th><th>Algorithm</th><th>Pool</th><th>Circles</th><th>Matched</th><th>Fuel saved/wk</th></tr></thead>
              <tbody>{runs.map((r) => (
                <tr key={r.id}><td>{new Date(r.created_at).toLocaleString('en-GB')}</td><td>{r.algorithm}</td><td>{r.pool_size}</td>
                  <td>{r.circles_created}</td><td>{r.students_matched} ({Math.round(r.metrics.match_rate * 100)}%)</td><td>{pkr(r.metrics.weekly_fuel_pkr_saved)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
