import { useState } from 'react'
import { api, DAY_LABELS } from '../../api'
import { Alert, Badge, Card, Spinner, STATUS_TONE, useLoad } from '../../components/ui'

export default function Circles() {
  const [status, setStatus] = useState('')
  const [circles, err, reload] = useLoad(() => api(`/api/admin/circles${status ? `?status=${status}` : ''}`), [status])
  const [msg, setMsg] = useState('')
  const dissolve = async (c) => {
    const reason = prompt('Reason for dissolving this circle (shown to members):')
    if (!reason) return
    try { await api(`/api/admin/circles/${c.id}/dissolve`, { method: 'POST', body: { reason } }); reload() } catch (e) { setMsg(e.message) }
  }
  return (
    <Card title="Circles" actions={
      <select value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All</option><option value="active">Active</option><option value="proposed">Proposed</option><option value="dissolved">Dissolved</option>
      </select>}>
      <Alert>{err || msg}</Alert>
      {!circles ? <Spinner /> : circles.length === 0 ? <p className="muted">No circles.</p> : (
        <div className="scroll">
          <table className="table">
            <thead><tr><th>#</th><th>Status</th><th>Members</th><th>Days</th><th>Score</th><th>Algorithm</th><th /></tr></thead>
            <tbody>{circles.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td><Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge></td>
                <td>{c.members.map((m) => (
                  <div key={m.user_id} className="small">{m.full_name}{m.is_driver && ' 🚗'} <span className="muted">{m.area}</span> <Badge tone={STATUS_TONE[m.status]}>{m.status}</Badge></div>
                ))}</td>
                <td>{c.shared_days.map((d) => DAY_LABELS[d]).join(' ')}</td>
                <td>{c.score.toFixed(2)}</td>
                <td>{c.algorithm}</td>
                <td>{c.status !== 'dissolved' ? <button className="btn btn-link" onClick={() => dissolve(c)}>Dissolve</button> : <span className="muted small">{c.dissolved_reason}</span>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
