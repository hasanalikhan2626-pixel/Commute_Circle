import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth'
import { Alert } from '../components/ui'

export default function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ email: '', password: '', full_name: '', phone: '', consent: false, research_consent: false })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      if (mode === 'login') await login(f.email, f.password)
      else await register({ email: f.email, password: f.password, full_name: f.full_name, phone: f.phone || null, consent: f.consent, research_consent: f.research_consent })
    } catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <div className="brand big"><span className="logo">◎</span> CommuteCircle</div>
        <p>Share the ride to BIC with students who live near you and keep the same timetable. Split fuel, cut traffic, travel with people you know.</p>
        <ul className="ticks">
          <li>BIC students only (@bic.edu.pk)</li>
          <li>Your exact address is never shared</li>
          <li>Same-gender circles if you prefer</li>
        </ul>
      </div>
      <form className="card auth-card" onSubmit={submit}>
        <div className="tabs">
          <button type="button" className={mode === 'login' ? 'on' : ''} onClick={() => setMode('login')}>Sign in</button>
          <button type="button" className={mode === 'register' ? 'on' : ''} onClick={() => setMode('register')}>Create account</button>
        </div>
        {mode === 'register' && (
          <label>Full name<input required minLength={2} value={f.full_name} onChange={set('full_name')} autoComplete="name" /></label>
        )}
        <label>Student email<input required type="email" value={f.email} onChange={set('email')} autoComplete="email" placeholder="you@bic.edu.pk" /></label>
        <label>Password<input required type="password" minLength={mode === 'register' ? 8 : 1} value={f.password} onChange={set('password')} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
        {mode === 'register' && (
          <label>Mobile <span className="muted">(shared only with your circle)</span>
            <input value={f.phone} onChange={set('phone')} placeholder="0300 1234567" autoComplete="tel" />
          </label>
        )}
        {mode === 'register' && (
          <div className="consent">
            <label className="check"><input type="checkbox" required checked={f.consent} onChange={(e) => setF({ ...f, consent: e.target.checked })} />
              <span>I have read and agree to the <Link to="/privacy" target="_blank">privacy notice</Link>.</span></label>
            <label className="check"><input type="checkbox" checked={f.research_consent} onChange={(e) => setF({ ...f, research_consent: e.target.checked })} />
              <span>Optional: my pseudonymised commute data may be used in the project's research. <span className="muted">You can change this later.</span></span></label>
          </div>
        )}
        <Alert>{err}</Alert>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
      </form>
    </div>
  )
}
