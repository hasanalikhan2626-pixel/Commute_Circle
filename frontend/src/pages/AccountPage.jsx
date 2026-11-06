import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Alert, Card } from '../components/ui'

export default function AccountPage() {
  const { user, refresh, logout } = useAuth()
  const [f, setF] = useState({ full_name: user.full_name, phone: user.phone || '' })
  const [msg, setMsg] = useState({})
  const [del, setDel] = useState({ open: false, password: '', err: '' })

  const save = async (e) => {
    e.preventDefault()
    try { await api('/api/auth/me', { method: 'PATCH', body: { full_name: f.full_name, phone: f.phone || null } }); await refresh(); setMsg({ ok: 'Saved.' }) }
    catch (ex) { setMsg({ err: ex.message }) }
  }
  const toggleResearch = async (e) => {
    try { await api('/api/auth/me', { method: 'PATCH', body: { research_consent: e.target.checked } }); await refresh() }
    catch (ex) { setMsg({ err: ex.message }) }
  }
  const download = async () => {
    const data = await api('/api/auth/me/export')
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: 'my-commutecircle-data.json' })
    a.click(); URL.revokeObjectURL(url)
  }
  const deleteAccount = async (e) => {
    e.preventDefault()
    try { await api('/api/auth/me', { method: 'DELETE', body: { password: del.password } }); logout() }
    catch (ex) { setDel({ ...del, err: ex.message }) }
  }

  return (
    <div className="stack">
      <Card title="Account">
        <form onSubmit={save} className="stack narrow">
          <label>Email<input value={user.email} disabled /></label>
          <label>Full name<input required minLength={2} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
          <label>Mobile<input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="0300 1234567" /></label>
          <Alert kind="ok">{msg.ok}</Alert><Alert>{msg.err}</Alert>
          <button className="btn btn-primary">Save</button>
        </form>
      </Card>
      <Card title="Your data">
        <label className="check"><input type="checkbox" checked={user.research_consent} onChange={toggleResearch} />
          <span>Allow my pseudonymised commute data to be used in the project's research</span></label>
        <p className="muted small">Read the <Link to="/privacy">privacy notice</Link> for what this means.</p>
        <div className="row wrap">
          <button className="btn" onClick={download}>Download my data</button>
          <button className="btn btn-danger" onClick={() => setDel({ ...del, open: true })}>Delete my account</button>
        </div>
        {del.open && (
          <form className="danger-zone stack narrow" onSubmit={deleteAccount}>
            <p>This permanently deletes your account and removes you from your circle. It cannot be undone.</p>
            <label>Confirm your password<input type="password" required value={del.password} onChange={(e) => setDel({ ...del, password: e.target.value })} autoComplete="current-password" /></label>
            <Alert>{del.err}</Alert>
            <div className="row"><button className="btn btn-danger">Delete permanently</button><button type="button" className="btn" onClick={() => setDel({ open: false, password: '', err: '' })}>Cancel</button></div>
          </form>
        )}
      </Card>
    </div>
  )
}
