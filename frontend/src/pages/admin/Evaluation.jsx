import { api } from '../../api'
import { Err, Loading, useLoad } from '../../components/ui'

// The proposal's targets (section 15) against live data, for the final evaluation.
export default function Evaluation() {
  const [rows, err] = useLoad(() => api('/api/admin/evaluation'))
  if (err) return <Err>{err}</Err>
  if (!rows) return <Loading />
  const met = (r) => {
    if (r.value == null) return null
    const m = r.target.match(/(>=|<=)\s*([\d.]+)/)
    if (!m) return r.target === '0' ? r.value === 0 : r.target === '100%' ? r.value >= 100 : null
    return m[1] === '>=' ? r.value >= Number(m[2]) : r.value <= Number(m[2])
  }
  return (
    <>
      <h2>Evaluation</h2>
      <p className="lead">The proposal’s targets against live pilot data. Survey-based figures fill in as students answer the questions on their My savings page.</p>
      <section className="card"><div className="scroll"><table className="tt">
        <thead><tr><th>Measure</th><th>Target</th><th style={{ textAlign: 'right' }}>Now</th><th /><th>How it’s measured</th></tr></thead>
        <tbody>{rows.map((r) => {
          const ok = met(r)
          return <tr key={r.metric}><td><b>{r.metric}</b></td><td className="mono">{r.target}</td>
            <td className="mono" style={{ textAlign: 'right' }}>{r.value == null ? '—' : `${r.value}${r.unit && !r.unit.startsWith('/') ? r.unit : ''}${r.unit?.startsWith('/') ? r.unit : ''}`}</td>
            <td>{ok == null ? <span className="badge">No data yet</span> : ok ? <span className="badge ok">Met</span> : <span className="badge bad">Not yet</span>}</td>
            <td className="sub">{r.note}</td></tr>
        })}</tbody></table></div></section>
    </>
  )
}
