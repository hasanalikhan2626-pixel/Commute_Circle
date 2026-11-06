import { useState } from 'react'
import { api } from '../api'

// Red SOS button (proposal Appendix D): call for help and alert Student Affairs at once.
export default function Sos() {
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState('')
  const [state, setState] = useState(null) // null | 'sending' | {call: [...]}
  const alertNow = async () => {
    setState('sending')
    try { setState(await api('/api/sos', { method: 'POST', body: { message: msg } })) } catch (e) { setState({ error: e.message }) }
  }
  const calls = state?.call || [{ label: 'Police', number: '15' }, { label: 'Rescue', number: '1122' }]
  return (
    <>
      <button className="btn sos" onClick={() => { setOpen(true); setState(null) }} aria-haspopup="dialog">SOS</button>
      {open && (
        <div className="modal" role="dialog" aria-modal="true" aria-label="Emergency" onClick={() => setOpen(false)}>
          <div className="card stack" onClick={(e) => e.stopPropagation()}>
            <h3>Need help right now?</h3>
            <div className="ck">{calls.map((c) => <a key={c.number} className="btn big sos" href={`tel:${c.number}`}>Call {c.label} · {c.number}</a>)}</div>
            {state?.alert_id
              ? <div className="notice"><span aria-hidden="true">✓</span><span>Student Affairs has been alerted with your circle and route{state.call.length > 2 ? ', and campus security' : ''}. Stay where it’s safe.</span></div>
              : <>
                <label className="hint" htmlFor="sos-msg">What’s happening? (optional)</label>
                <input type="text" id="sos-msg" value={msg} onChange={(e) => setMsg(e.target.value)} maxLength={500} />
                {state?.error && <div className="err">{state.error}</div>}
                <button className="btn primary big" onClick={alertNow} disabled={state === 'sending'}>{state === 'sending' ? 'Sending…' : 'Alert Student Affairs now'}</button>
              </>}
            <p className="hint" style={{ margin: 0 }}>We also message your emergency contact if you’ve added one on your Account page.</p>
            <button className="btn" onClick={() => setOpen(false)}>Close</button>
          </div>
        </div>
      )}
    </>
  )
}
