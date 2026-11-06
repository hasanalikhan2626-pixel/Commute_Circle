import { useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Alert, Card } from '../components/ui'

export default function AccountPage() {
  const { user, refresh } = useAuth()
  const [f, setF] = useState({ full_name: user.full_name, phone: user.phone || '' })
  const [msg, setMsg] = useState({})
  const save = async (e) => {
    e.preventDefault()
    try { await api('/api/auth/me', { method: 'PATCH', body: { full_name: f.full_name, phone: f.phone || null } }); await refresh(); setMsg({ ok: 'Saved.' }) }
    catch (ex) { setMsg({ err: ex.message }) }
  }
  return (
    <Card title="Account">
      <form onSubmit={save} className="stack narrow">
        <label>Email<input value={user.email} disabled /></label>
        <label>Full name<input required minLength={2} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
        <label>Mobile<input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="0300 1234567" /></label>
        <Alert kind="ok">{msg.ok}</Alert><Alert>{msg.err}</Alert>
        <button className="btn btn-primary">Save</button>
      </form>
    </Card>
  )
}
