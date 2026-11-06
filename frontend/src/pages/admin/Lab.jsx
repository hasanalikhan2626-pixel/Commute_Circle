import { useState } from 'react'
import { api, download, rs } from '../../api'
import { useToast } from '../../components/Toast'
import { Err, Loading, useLoad } from '../../components/ui'

const NAMES = { compatibility: 'Compatibility', greedy: 'Greedy', cluster: 'k-means' }
const COLS = [
  ['match_rate', 'Match rate', (v) => `${(v * 100).toFixed(1)}%`, 'max'],
  ['circles', 'Circles', (v) => v],
  ['avg_circle_size', 'Avg size', (v) => v.toFixed(2)],
  ['avg_fit', 'Avg fit', (v) => v.toFixed(1), 'max'],
  ['avg_detour_km', 'Avg detour km', (v) => v.toFixed(2), 'min'],
  ['avg_shared_days', 'Shared days/wk', (v) => v.toFixed(2), 'max'],
  ['weekly_pkr_saved', 'Saved/wk', rs, 'max'],
  ['weekly_co2_kg_saved', 'CO₂ kg/wk', (v) => v, 'max'],
  ['runtime_ms', 'ms', (v) => v, 'min'],
]

export default function Lab() {
  const [cmp, setCmp] = useState(null)
  const [algo, setAlgo] = useState('compatibility')
  const [err, setErr] = useState('')
  const [runs, , reloadRuns] = useLoad(() => api('/api/admin/runs'))
  const toast = useToast()
  const compare = async () => { setErr(''); try { setCmp(await api('/api/admin/compare', { method: 'POST' })) } catch (e) { setErr(e.message) } }
  const run = async () => {
    if (!confirm(`Propose circles for everyone still unmatched using ${NAMES[algo]}? Each student will be asked to accept.`)) return
    try { const r = await api('/api/admin/match', { method: 'POST', body: { algorithm: algo } }); toast(`Proposed ${r.circles_created} circles for ${r.students_matched} of ${r.pool_size} students`); setCmp(null); reloadRuns() } catch (e) { setErr(e.message) }
  }
  const best = (k, dir) => cmp && (dir === 'min' ? Math.min : Math.max)(...cmp.map((r) => r[k]))
  return (
    <>
      <h2>Matching lab</h2>
      <p className="lead">For the research component. Students normally find their own circle; here you can compare the three algorithms on everyone still unmatched, and optionally propose circles in one batch.</p>
      <section className="card stack">
        <div className="row"><button className="btn" onClick={compare}>Compare algorithms (dry run)</button>
          <select value={algo} onChange={(e) => setAlgo(e.target.value)} style={{ width: 'auto' }}>{Object.entries(NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <button className="btn primary" onClick={run}>Propose circles</button>
          <button className="btn" onClick={() => download('/api/admin/research-export', 'commutecircle-research.csv').catch((e) => setErr(e.message))}>Research export (CSV)</button></div>
        <Err>{err}</Err>
        {cmp && <>
          <div className="scroll"><table className="tt"><thead><tr><th>Algorithm</th>{COLS.map(([k, l]) => <th key={k} style={{ textAlign: 'right' }}>{l}</th>)}</tr></thead>
            <tbody>{cmp.map((r) => <tr key={r.algorithm}><td><b>{NAMES[r.algorithm]}</b></td>{COLS.map(([k, , f, dir]) => <td key={k} className="mono" style={{ textAlign: 'right', ...(dir && r[k] === best(k, dir) ? { color: 'var(--accent)', fontWeight: 700 } : {}) }}>{f(r[k])}</td>)}</tr>)}</tbody></table></div>
          <p className="hint">On {cmp[0]?.pool_size} unmatched students. Greedy = nearest-neighbour baseline; k-means = geographic clustering; Compatibility = the method students use in Find my circle. Green marks the best value. Nothing is saved.</p>
        </>}
      </section>
      <section className="card" style={{ marginTop: 18 }}><h3 style={{ marginBottom: 8 }}>Batch runs</h3>
        {!runs ? <Loading /> : runs.length ? <div className="scroll"><table className="tt"><thead><tr><th>When</th><th>Algorithm</th><th>Pool</th><th>Circles</th><th>Matched</th></tr></thead>
          <tbody>{runs.map((r) => <tr key={r.id}><td className="sub">{new Date(r.created_at).toLocaleString('en-GB')}</td><td>{NAMES[r.algorithm]}</td><td className="mono">{r.pool_size}</td><td className="mono">{r.circles_created}</td><td className="mono">{r.students_matched}</td></tr>)}</tbody></table></div>
          : <p className="hint">No batch runs yet.</p>}</section>
    </>
  )
}
