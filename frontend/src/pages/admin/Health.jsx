import { api, sa } from '../../api'
import { Err, Loading, useLoad } from '../../components/ui'

export default function Health() {
  const [rows, err] = useLoad(() => api('/api/admin/health'))
  if (err) return <Err>{err}</Err>
  if (!rows) return <Loading />
  return (
    <>
      <h2>Circle health</h2>
      <p className="lead">Circles with low completion, no-shows or private negative feedback, so Student Affairs can help early.</p>
      <section className="card"><div className="scroll"><table className="tt">
        <thead><tr><th>Circle</th><th>Area(s)</th><th style={{ textAlign: 'right' }}>Completed</th><th style={{ textAlign: 'right' }}>No-shows</th><th style={{ textAlign: 'right' }}>Negative feedback</th><th style={{ textAlign: 'right' }}>Streak</th><th /></tr></thead>
        <tbody>{rows.length ? rows.map((r) => <tr key={r.circle_id}><td>{r.members.join(', ')}</td><td className="sub">{r.areas.map(sa).join(', ')}</td>
          <td className="mono" style={{ textAlign: 'right' }}>{r.completed}%</td><td className="mono" style={{ textAlign: 'right' }}>{r.noshows}</td><td className="mono" style={{ textAlign: 'right' }}>{r.negative}</td><td className="mono" style={{ textAlign: 'right' }}>{r.streak}</td>
          <td>{r.check_in ? <span className="badge bad">Check in</span> : <span className="badge ok">Healthy</span>}</td></tr>)
          : <tr><td colSpan="7" className="empty">No active circles yet.</td></tr>}</tbody></table></div></section>
    </>
  )
}
