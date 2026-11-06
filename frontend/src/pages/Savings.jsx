import { api, rs, sa } from '../api'
import { Err, Loading, useLoad } from '../components/ui'
import Surveys from '../components/Surveys'

export default function Savings() {
  const [d, err] = useLoad(() => api('/api/savings'))
  if (err) return <Err>{err}</Err>
  if (!d) return <Loading />
  const x = d.tiles
  const mx = Math.max(1, ...d.weeks.map((w) => w.solo))
  return (
    <>
      <h2>My savings</h2>
      <p className="lead">Based on the trips your circle confirmed and the fares members entered. Estimates only.</p>
      <div className="tiles" style={{ marginBottom: 16 }}>
        <div className="tile accent"><b className="mono">{rs(x.saved)}</b><span>saved vs going alone</span></div>
        <div className="tile"><b className="mono">{rs(x.paid)}</b><span>your fare shares</span></div>
        <div className="tile"><b className="mono">{x.went}</b><span>shared trips</span></div>
        <div className="tile"><b className="mono">{x.reliability == null ? '—' : x.reliability + '%'}</b><span>show-up rate</span></div>
      </div>
      <div className="cols">
        <section className="card"><h3 style={{ marginBottom: 12 }}>Last 4 weeks: alone vs your share</h3>
          {d.in_circle || x.went ? <>
            {d.weeks.map((w) => (
              <div className="wk" key={w.label}><span className="sub">{w.label}</span><div className="bars">
                <div className="sbar solo" style={{ width: `${(w.solo / mx) * 100}%` }}><span>{w.solo ? rs(w.solo) : ''}</span></div>
                <div className="sbar paid" style={{ width: `${(w.paid / mx) * 100}%` }}><span>{w.paid ? rs(w.paid) : ''}</span></div></div></div>
            ))}
            <div className="legend"><span><i style={{ background: 'var(--road)' }} />If you went alone</span><span><i style={{ background: 'var(--accent)' }} />What you paid</span></div>
          </> : <p className="hint">Join a circle to start saving.</p>}
        </section>
        <section className="card"><h3 style={{ marginBottom: 4 }}>Fare guide: {d.area ? sa(d.area) : 'your area'} → campus</h3><p className="hint" style={{ marginBottom: 10 }}>Per person, from fares other members entered.</p>
          <table className="tt"><thead><tr><th>Way</th><th style={{ textAlign: 'right' }}>Usual share</th><th style={{ textAlign: 'right' }}>Range</th><th style={{ textAlign: 'right' }}>Trips</th></tr></thead>
            <tbody>{d.guide.map((g) => <tr key={g.mode}><td>{g.mode}</td><td className="mono" style={{ textAlign: 'right' }}>{g.n ? rs(g.median) : '—'}</td>
              <td className="mono sub" style={{ textAlign: 'right' }}>{g.n ? `${rs(g.lo)}–${rs(g.hi).replace('Rs ', '')}` : 'not enough data'}</td><td className="mono" style={{ textAlign: 'right' }}>{g.n}</td></tr>)}</tbody></table>
        </section>
      </div>
      <div style={{ marginTop: 18 }}><Surveys /></div>
    </>
  )
}
