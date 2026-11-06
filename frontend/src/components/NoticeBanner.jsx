import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

// Shown when the privacy notice changed since the student last agreed to it.
export default function NoticeBanner() {
  const { user, refresh } = useAuth()
  if (!user || user.role === 'admin' || user.consent_current) return null
  return (
    <div className="wrap" style={{ paddingTop: 12 }}>
      <div className="notice"><span aria-hidden="true">ℹ</span>
        <span style={{ flex: 1 }}>We’ve updated the <Link to="/privacy">privacy notice</Link> (ratings, SOS, email codes, optional WhatsApp and surveys).</span>
        <button className="btn sm primary" onClick={async () => { await api('/api/auth/consent', { method: 'POST' }); refresh() }}>I agree</button></div>
    </div>
  )
}
