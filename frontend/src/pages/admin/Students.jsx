import { useState } from 'react'
import { api } from '../../api'
import { useToast } from '../../components/Toast'
import { Err, Loading, useLoad } from '../../components/ui'

const TONE = { approved: 'ok', pending: 'sign', rejected: '', suspended: 'bad' }

export default function Students() {
  const [users, err, reload] = useLoad(() => api('/api/admin/users'))
  const [q, setQ] = useState('')
  const toast = useToast()
  const set = async (u, status) => {
    if (status === 'suspended' && !confirm(`Suspend ${u.full_name}? They will be signed out and removed from their circle.`)) return
    try { await api(`/api/admin/users/${u.id}`, { method: 'PATCH', body: { status } }); reload(); toast(status === 'suspended' ? 'Member suspended' : 'Member reinstated') } catch (e) { toast(e.message) }
  }
  if (err) return <Err>{err}</Err>
  if (!users) return <Loading />
  const shown = users.filter((u) => `${u.full_name} ${u.email} ${u.area || ''}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <>
      <h2>Students</h2>
      <p className="lead">Everyone with an account. Open individual records only when you need to, for example to handle a report.</p>
      <section className="card stack">
        <input type="text" placeholder="Search name, email or area" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search students" />
        <div className="scroll"><table className="tt"><thead><tr><th>Name</th><th>Programme</th><th>Area</th><th>Status</th><th /></tr></thead>
          <tbody>{shown.map((u) => <tr key={u.id}><td><b>{u.full_name}</b><br /><span className="sub mono">{u.email}</span></td>
            <td className="sub">{u.role === 'admin' ? 'Student Affairs' : `${u.programme || ''} · Y${u.year || ''}`}</td><td className="sub">{u.area || '—'}</td>
            <td><span className={`badge ${TONE[u.status]}`}>{u.status}</span></td>
            <td>{u.role !== 'admin' && (u.status === 'approved' ? <button className="btn sm danger" onClick={() => set(u, 'suspended')}>Suspend</button>
              : u.status === 'suspended' ? <button className="btn sm" onClick={() => set(u, 'approved')}>Reinstate</button> : null)}</td></tr>)}</tbody></table></div>
      </section>
    </>
  )
}
