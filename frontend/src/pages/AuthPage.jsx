import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, token } from '../api'
import { useAuth } from '../auth'
import { useMeta } from '../meta'
import { Err, Logo } from '../components/ui'

export default function AuthPage() {
  const { login, register } = useAuth()
  const meta = useMeta()
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ email: '', password: '', full_name: '', phone: '', gender: '', programme: '', year: '1', consent: false, research_consent: false })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try {
      if (mode === 'login') await login(f.email, f.password)
      else await register({ ...f, year: Number(f.year) })
    } catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }
  if (mode === 'forgot') return <Forgot back={() => setMode('login')} />
  return (
    <div className="auth">
      <div className="pitch">
        <div className="brand"><Logo size={44} /><div><h1 style={{ fontSize: '1.5rem', margin: 0 }}>CommuteCircle</h1><small>BIC Karachi · Korangi Creek</small></div></div>
        <h1>Travel to campus with classmates on your route.</h1>
        <p className="lead">We match you with BIC students who live near you, or on your way, and come to campus at the same times. Split the Careem, take turns driving, and never travel alone.</p>
        <ul>
          <li>BIC students only, checked by Student Affairs</li>
          <li>Area only. We never ask for your address</li>
          <li>Women-only circles if you prefer</li>
          <li>Phone numbers shared only when everyone accepts</li>
        </ul>
      </div>
      <form className="card stack" onSubmit={submit}>
        <div className="seg" role="group" aria-label="Sign in or create account" style={{ alignSelf: 'flex-start' }}>
          <button type="button" aria-pressed={mode === 'login'} onClick={() => setMode('login')}>Sign in</button>
          <button type="button" aria-pressed={mode === 'register'} onClick={() => setMode('register')}>Create account</button>
        </div>
        {mode === 'register' && <label className="f">Full name<input required value={f.full_name} onChange={set('full_name')} autoComplete="name" placeholder="First and last name" /></label>}
        <label className="f">BIC email<input required type="email" value={f.email} onChange={set('email')} autoComplete="email" placeholder="you@bic.edu.pk" /></label>
        <label className="f">Password<input required type="password" minLength={mode === 'register' ? 8 : 1} value={f.password} onChange={set('password')} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
        {mode === 'register' && (
          <>
            <label className="f">Mobile <span className="hint">Shared only with your circle, once everyone accepts.</span>
              <input required type="tel" value={f.phone} onChange={set('phone')} placeholder="0300 1234567" autoComplete="tel" /></label>
            <div className="grid2">
              <label className="f">Gender<select required value={f.gender} onChange={set('gender')}><option value="">Choose…</option><option value="female">Female</option><option value="male">Male</option></select></label>
              <label className="f">Year<select value={f.year} onChange={set('year')}>{[1, 2, 3, 4].map((y) => <option key={y} value={y}>Year {y}</option>)}</select></label>
            </div>
            <label className="f">Programme<select required value={f.programme} onChange={set('programme')}><option value="">Choose…</option>{meta?.programmes.map((p) => <option key={p}>{p}</option>)}</select></label>
            <label className="switch"><input type="checkbox" required checked={f.consent} onChange={set('consent')} />
              <span>I accept the Terms, <Link to="/privacy" target="_blank">Privacy Notice</Link> and Code of Conduct.</span></label>
            <label className="switch"><input type="checkbox" checked={f.research_consent} onChange={set('research_consent')} />
              <span><span className="hint">Optional:</span> my pseudonymised trip data may be used in the project's research. <span className="hint">You can change this later.</span></span></label>
          </>
        )}
        <Err>{err}</Err>
        <button className="btn primary big" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
        {mode === 'register' && <p className="hint">Student Affairs checks each sign-up against the student record before you can be matched.</p>}
        {mode === 'login' && <button type="button" className="link" onClick={() => setMode('forgot')}>Forgot password?</button>}
      </form>
    </div>
  )
}

function Forgot({ back }) {
  const [email, setEmail] = useState('')
  const [step, setStep] = useState('ask')
  const [code, setCode] = useState('')
  const [pw, setPw] = useState('')
  const [msg, setMsg] = useState({})
  const ask = async (e) => {
    e.preventDefault(); setMsg({})
    try { const r = await api('/api/auth/forgot', { method: 'POST', body: { email } }); setMsg({ ok: r.message }); setStep('reset') } catch (ex) { setMsg({ err: ex.message }) }
  }
  const reset = async (e) => {
    e.preventDefault(); setMsg({})
    try { const r = await api('/api/auth/reset', { method: 'POST', body: { email, code, new_password: pw } }); token.set(r.access_token); window.location.assign('/') } catch (ex) { setMsg({ err: ex.message }) }
  }
  return (
    <div className="auth">
      <div className="pitch"><div className="brand"><Logo size={44} /><div><h1 style={{ fontSize: '1.5rem', margin: 0 }}>CommuteCircle</h1><small>BIC Karachi · Korangi Creek</small></div></div>
        <h1>Reset your password</h1><p className="lead">We’ll email a 6-digit code to your BIC address. It works for 30 minutes.</p></div>
      <form className="card stack" onSubmit={step === 'ask' ? ask : reset}>
        <label className="f">BIC email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@bic.edu.pk" disabled={step !== 'ask'} /></label>
        {step === 'reset' && <>
          <label className="f">6-digit code<input type="text" inputMode="numeric" required maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} /></label>
          <label className="f">New password<input type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" /></label>
        </>}
        {msg.ok && <div className="notice"><span>{msg.ok}</span></div>}
        <Err>{msg.err}</Err>
        <button className="btn primary big">{step === 'ask' ? 'Email me a code' : 'Set new password'}</button>
        <button type="button" className="link" onClick={back}>Back to sign in</button>
      </form>
    </div>
  )
}
