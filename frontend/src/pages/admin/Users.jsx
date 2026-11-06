import { useState } from 'react'
import { api } from '../../api'
import { Alert, Badge, Card, Spinner, useLoad } from '../../components/ui'

export default function Users() {
  const [users, err, reload] = useLoad(() => api('/api/admin/users'))
  const [q, setQ] = useState('')
  const [msg, setMsg] = useState('')
  const toggle = async (u) => {
    if (u.is_active && !confirm(`Suspend ${u.full_name}? They will be signed out and removed from their circle.`)) return
    try { await api(`/api/admin/users/${u.id}`, { method: 'PATCH', body: { is_active: !u.is_active } }); reload() } catch (e) { setMsg(e.message) }
  }
  if (err) return <Alert>{err}</Alert>
  if (!users) return <Spinner />
  const shown = users.filter((u) => `${u.full_name} ${u.email}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <Card title={`Students (${users.length})`} actions={<input placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} />}>
      <Alert>{msg}</Alert>
      <div className="scroll">
        <table className="table">
          <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Commute details</th><th>Status</th><th /></tr></thead>
          <tbody>{shown.map((u) => (
            <tr key={u.id}>
              <td>{u.full_name} {u.role === 'admin' && <Badge tone="info">admin</Badge>}</td>
              <td>{u.email}</td><td>{u.phone || '—'}</td>
              <td>{u.has_profile ? 'Yes' : <span className="muted">Not yet</span>}</td>
              <td><Badge tone={u.is_active ? 'ok' : 'bad'}>{u.is_active ? 'active' : 'suspended'}</Badge></td>
              <td>{u.role !== 'admin' && <button className="btn btn-link" onClick={() => toggle(u)}>{u.is_active ? 'Suspend' : 'Reinstate'}</button>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  )
}
