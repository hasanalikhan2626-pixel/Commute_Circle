import { useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { useToast } from './Toast'

// Enter the 6-digit code emailed at sign-up (proves the student owns the BIC address).
export default function VerifyEmail() {
  const { user, refresh } = useAuth()
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')
  const toast = useToast()
  if (!user || user.role === 'admin' || user.email_verified) return null
  const verify = async () => {
    setErr('')
    try { await api('/api/auth/verify', { method: 'POST', body: { code } }); await refresh(); toast('Email verified') } catch (e) { setErr(e.message) }
  }
  const resend = async () => { try { await api('/api/auth/verify/send', { method: 'POST' }); toast('New code sent to ' + user.email) } catch (e) { toast(e.message) } }
  return (
    <div className="notice" style={{ marginBottom: 16, flexWrap: 'wrap' }}>
      <span aria-hidden="true">✉</span>
      <span style={{ flex: 1, minWidth: 220 }}>We emailed a 6-digit code to <b>{user.email}</b>. Enter it to verify your BIC email.</span>
      <span className="row" style={{ flexWrap: 'nowrap' }}>
        <input type="text" inputMode="numeric" maxLength={6} placeholder="123456" aria-label="Verification code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} style={{ width: 110 }} />
        <button className="btn sm primary" disabled={code.length !== 6} onClick={verify}>Verify</button>
        <button className="btn sm" onClick={resend}>Resend</button>
      </span>
      {err && <div className="err" style={{ flexBasis: '100%' }}>{err}</div>}
    </div>
  )
}
