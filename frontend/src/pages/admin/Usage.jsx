import { api, fmt } from '../../api'
import Map from '../../components/Map'
import { Err, Loading, useLoad } from '../../components/ui'

export default function Usage() {
  const [d, err] = useLoad(() => api('/api/admin/usage'))
  if (err) return <Err>{err}</Err>
  if (!d) return <Loading />
  const mx = Math.max(1, ...d.per_day.map((x) => x.n))
  return (
    <>
      <h2>Usage</h2>
      <p className="lead">How many students CommuteCircle is helping, and where the gaps are. Totals only: individual records are opened only when handling a report.</p>
      <div className="kpis">
        <div className="kpi"><b className="mono">{d.approved}</b><span>Approved members</span></div>
        <div className="kpi"><b className="mono">{d.in_circle}</b><span>In a circle (gap covered)</span></div>
        <div className="kpi"><b className="mono">{d.active}</b><span>Active (trip in last 2 weeks)</span></div>
        <div className="kpi"><b className="mono">{d.completion}%</b><span>Planned trips completed</span></div>
        <div className="kpi"><b className="mono">{d.circles_travelling}/{d.circles}</b><span>Circles still travelling (last week)</span></div>
        <div className="kpi"><b className="mono" style={{ color: 'var(--bad)' }}>{d.without}</b><span>Still without a circle</span></div>
        <div className="kpi"><b className="mono">{d.avg_trust ?? '—'}</b><span>Average trust score /5 ({d.trust_45 ?? 0}% at 4.5+)</span></div>
        <div className="kpi"><b className="mono">{d.women_only_pct ?? '—'}%</b><span>Female students choosing women-only</span></div>
        <div className="kpi"><b className="mono" style={d.open_sos ? { color: 'var(--bad)' } : {}}>{d.open_sos}</b><span>Open SOS alerts</span></div>
      </div>
      <div className="cols">
        <section className="card"><h3 style={{ marginBottom: 10 }}>Confirmed circle trips per day</h3>
          <div className="daybars">{d.per_day.map((x) => (
            <div className="db" key={x.day} title={`${fmt(x.day)}: ${x.n}`}><span className="v mono">{x.n || ''}</span><i style={{ height: `${(x.n / mx) * 100}%` }} /><span className="l">{Number(x.day.slice(8))}</span></div>
          ))}</div>
          <p className="hint" style={{ marginTop: 8 }}>Last 4 weeks of weekdays, ending today.</p></section>
        <section className="card"><Map bubbles={d.areas.map((r) => ({ area: r.area, coords: r.coords, n: r.members, u: r.without }))} />
          <div className="legend"><span><i style={{ background: 'var(--accent)', opacity: 0.5 }} />Members</span><span><i style={{ background: 'var(--bad)' }} />Without a circle</span></div></section>
      </div>
      <section className="card" style={{ marginTop: 18 }}><div className="scroll"><table className="tt">
        <thead><tr><th>Area</th><th style={{ textAlign: 'right' }}>Members</th><th style={{ textAlign: 'right' }}>In a circle</th><th style={{ textAlign: 'right' }}>Active</th><th style={{ textAlign: 'right' }}>Without circle</th></tr></thead>
        <tbody>{d.areas.map((r) => <tr key={r.area}><td>{r.area}</td><td className="mono" style={{ textAlign: 'right' }}>{r.members}</td><td className="mono" style={{ textAlign: 'right' }}>{r.in_circle}</td>
          <td className="mono" style={{ textAlign: 'right' }}>{r.active}</td><td className="mono" style={{ textAlign: 'right', ...(r.without ? { color: 'var(--bad)', fontWeight: 700 } : {}) }}>{r.without}</td></tr>)}</tbody></table></div></section>
    </>
  )
}
