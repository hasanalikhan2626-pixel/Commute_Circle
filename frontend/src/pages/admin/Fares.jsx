import { api, k1, rs } from '../../api'
import { Err, Loading, useLoad } from '../../components/ui'

export default function Fares() {
  const [d, err] = useLoad(() => api('/api/admin/fares'))
  if (err) return <Err>{err}</Err>
  if (!d) return <Loading />
  return (
    <>
      <h2>Fares</h2>
      <p className="lead">What students actually pay, from optional fare entries after confirmed trips. Medians, so one unusual entry doesn't skew the picture.</p>
      <div className="kpis">{d.by_mode.map((b) => <div className="kpi" key={b.mode}><b className="mono">{b.per_km != null ? rs(b.per_km) + '/km' : '—'}</b><span>{b.mode} · per person</span></div>)}
        <div className="kpi"><b className="mono">{d.fare_pct}%</b><span>of confirmed trips have a fare</span></div></div>
      <section className="card"><div className="scroll"><table className="tt">
        <thead><tr><th>Area → campus</th><th>Way</th><th style={{ textAlign: 'right' }}>Road km (est.)</th><th style={{ textAlign: 'right' }}>Median share</th><th style={{ textAlign: 'right' }}>Entries</th></tr></thead>
        <tbody>{d.rows.map((r, i) => <tr key={i}><td>{r.area}</td><td>{r.mode}</td><td className="mono" style={{ textAlign: 'right' }}>{k1(r.road_km)}</td><td className="mono" style={{ textAlign: 'right' }}>{rs(r.median)}</td><td className="mono" style={{ textAlign: 'right' }}>{r.n}</td></tr>)}</tbody></table></div>
        <p className="hint" style={{ marginTop: 8 }}>Areas with fewer than 3 entries for a way of travelling are hidden.</p></section>
    </>
  )
}
