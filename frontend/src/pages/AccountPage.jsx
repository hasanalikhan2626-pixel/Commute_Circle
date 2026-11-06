import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { useToast } from '../components/Toast'
import { Err } from '../components/ui'
import VerifyEmail from '../components/VerifyEmail'

export default function AccountPage() {
  const { user, refresh, logout } = useAuth()
  const toast = useToast()
  const [f, setF] = useState({ full_name: user.full_name, phone: user.phone || '', emergency_name: user.emergency_name || '', emergency_phone: user.emergency_phone || '' })
  const [err, setErr] = useState('')
  const [del, setDel] = useState(null)
  const save = async (e) => {
    e.preventDefault(); setErr('')
    try { await api('/api/auth/me', { method: 'PATCH', body: { full_name: f.full_name, phone: f.phone || null, emergency_name: f.emergency_name || null, emergency_phone: f.emergency_phone || null } }); await refresh(); toast('Saved') } catch (ex) { setErr(ex.message) }
  }
  const research = async (on) => { await api('/api/auth/me', { method: 'PATCH', body: { research_consent: on } }); await refresh(); toast(on ? 'Thanks for helping the research' : 'You’ve opted out of research use') }
  const exportData = async () => {
    const data = await api('/api/auth/me/export')
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    Object.assign(document.createElement('a'), { href: url, download: 'my-commutecircle-data.json' }).click()
    URL.revokeObjectURL(url)
  }
  const remove = async (e) => {
    e.preventDefault()
    try { await api('/api/auth/me', { method: 'DELETE', body: { password: del } }); logout() } catch (ex) { setErr(ex.message) }
  }
  return (
    <>
      <h2>Account</h2>
      <p className="lead">{user.email} · {user.role === 'admin' ? 'Student Affairs' : `${user.programme || ''}, Year ${user.year || ''}`} · <span className="badge">{user.status}</span></p>
      <VerifyEmail />
      <div className="cols">
        <form className="card stack" onSubmit={save}>
          <label className="f">Full name<input type="text" required minLength={2} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
          <label className="f">Mobile<input type="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="0300 1234567" /></label>
          {user.role !== 'admin' && <>
            <p className="q" style={{ margin: '8px 0 0' }}>Emergency contact <span className="hint">(messaged if you press SOS)</span></p>
            <div className="grid2">
              <label className="f">Name<input type="text" value={f.emergency_name} onChange={(e) => setF({ ...f, emergency_name: e.target.value })} placeholder="e.g. Ammi" /></label>
              <label className="f">Mobile<input type="tel" value={f.emergency_phone} onChange={(e) => setF({ ...f, emergency_phone: e.target.value })} placeholder="0300 1234567" /></label>
            </div>
          </>}
          <Err>{err}</Err>
          <div><button className="btn primary">Save</button></div>
        </form>
        {user.role !== 'admin' && (
          <section className="card stack"><h3>Your data</h3>
            <label className="switch"><input type="checkbox" checked={user.whatsapp_opt_in} onChange={async (e) => { await api('/api/auth/me', { method: 'PATCH', body: { whatsapp_opt_in: e.target.checked } }); await refresh(); toast(e.target.checked ? 'WhatsApp reminders on' : 'WhatsApp reminders off') }} />
              <span>Send me WhatsApp reminders and daily check-ins <span className="hint">(reply 1 or 2 instead of opening the app)</span></span></label>
            <label className="switch"><input type="checkbox" checked={user.research_consent} onChange={(e) => research(e.target.checked)} />
              <span>Allow my pseudonymised trip data to be used in the project’s research</span></label>
            <p className="hint">Read the <Link to="/privacy">privacy notice</Link> for what this means.</p>
            <div className="row"><button className="btn" onClick={exportData}>Download my data</button>
              <button className="btn danger" onClick={() => setDel('')}>Delete my account</button></div>
            {del !== null && (
              <form className="danger-zone stack" onSubmit={remove}>
                <p style={{ margin: 0 }}>This permanently deletes your account and removes you from your circle. It can’t be undone.</p>
                <label className="f">Confirm your password<input type="password" required value={del} onChange={(e) => setDel(e.target.value)} autoComplete="current-password" /></label>
                <div className="row"><button className="btn danger solid">Delete permanently</button><button type="button" className="btn" onClick={() => setDel(null)}>Cancel</button></div>
              </form>
            )}
          </section>
        )}
      </div>
    </>
  )
}
