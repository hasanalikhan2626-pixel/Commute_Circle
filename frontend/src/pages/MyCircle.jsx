import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { api, fmt, phone, rs } from '../api'
import { useCircle } from '../App'
import { useMeta } from '../meta'
import { useToast } from '../components/Toast'
import { Av, Err } from '../components/ui'
import { driveLabel } from './Today'

export default function MyCircle() {
  const { circle: c, reload, setRematch } = useCircle()
  const myName = useAuth().user.full_name
  const meta = useMeta()
  const toast = useToast()
  const nav = useNavigate()
  const [fb, setFb] = useState(null)
  const [rep, setRep] = useState({ who: c.members.find((m) => !m.me)?.user_id, why: meta?.report_reasons[0], det: '' })
  const [err, setErr] = useState('')
  const me = c.members.find((m) => m.me)
  const call = async (fn, msg) => { setErr(''); try { await fn(); await reload(); if (msg) toast(msg) } catch (e) { setErr(e.message); toast(e.message) } }
  const sendFb = async () => {
    if (!fb?.tag) { toast('Pick one option'); return }
    await call(() => api('/api/circle/feedback', { method: 'POST', body: { to_id: fb.m.user_id, up: fb.up, tag: fb.tag } }),
      fb.up ? 'Thanks! Positive feedback adds up to badges.' : 'Sent privately to Student Affairs.')
    setFb(null)
  }
  const report = (leave) => call(() => api('/api/circle/report', { method: 'POST', body: { reported_id: Number(rep.who), reason: rep.why, details: rep.det, leave } }),
    'Report sent to Student Affairs. You have left the circle.')
  const leave = () => { if (confirm('Leave this circle? Your number will be hidden again.')) call(() => api('/api/circle/leave', { method: 'POST' }), 'You left the circle. Your number is hidden again.') }

  return (
    <>
      <h2>Your circle</h2>
      <p className="lead">{c.members.length} members · together since {fmt(c.since)} · travelling by {c.mode}</p>
      <Err>{err}</Err>
      <div className="cols">
        <section className="stack">
          {c.members.map((s) => (
            <div className="card member2" key={s.user_id}><Av name={s.me ? myName : s.name} n={s.pickup} />
              <div style={{ minWidth: 0 }}>
                <div className="nm">{s.name} <span className="sub">· {s.programme}, Y{s.year}</span></div>
                <div className="sub">{s.area}{s.phone && <> · <a className="mono" href={`tel:${s.phone}`}>{phone(s.phone)}</a></>}</div>
                <div className="facts"><span className="badge">✓ BIC email verified</span>
                  <span className={`badge ${s.reliability >= 90 ? 'ok' : s.reliability >= 75 || s.reliability == null ? '' : 'bad'}`}>Shows up {s.reliability == null ? '—' : s.reliability + '%'}</span>
                  <span className="badge">{s.trips} trips</span>{s.badges.map((b) => <span key={b} className="badge sign">★ {b}</span>)}</div>
                {!s.me && <div className="row" style={{ marginTop: 8, gap: 6 }}><span className="hint">Private feedback:</span>
                  <button className="opt sm" aria-label={`Thumbs up for ${s.name}`} onClick={() => setFb({ m: s, up: true })}>👍</button>
                  <button className="opt sm" aria-label={`Thumbs down for ${s.name}`} onClick={() => setFb({ m: s, up: false })}>👎</button></div>}
              </div>
            </div>
          ))}
        </section>
        <aside className="stack">
          <div className="card"><h3 style={{ marginBottom: 8 }}>Weekly plan</h3>
            <div className="scroll"><table className="tt"><thead><tr><th />{meta?.days.map((d) => <th key={d}>{d}</th>)}</tr></thead>
              <tbody>{c.members.map((s) => <tr key={s.user_id}><td>{s.me ? <b>You</b> : s.name}</td>{meta?.days.map((d) => <td key={d} className="mono">{c.plan[d]?.[s.user_id] || <span className="sub">—</span>}</td>)}</tr>)}</tbody></table></div>
            <p className="hint" style={{ marginTop: 8 }}>Times are campus arrival times. Change yours with “Update timetable” below.</p></div>
          <div className="card stack"><div><h3>How your circle travels</h3><p className="hint">Change it any time; everyone in the circle sees it.</p></div>
            <select aria-label="How your circle travels" value={c.mode} onChange={(e) => call(() => api('/api/circle/mode', { method: 'PATCH', body: { mode: e.target.value } }), 'Your circle now travels by ' + e.target.value)}>
              {meta?.methods.map((m) => <option key={m} disabled={!c.modes.includes(m)}>{m}{c.modes.includes(m) ? '' : ' (not everyone)'}</option>)}
            </select>
            {c.is_driver_mode && <div><p className="q" style={{ margin: '0 0 6px' }}>Driving rota · next 2 weeks</p>
              {c.rota.map((r) => (
                <div className="who-row" key={r.day}><span><span className="mono sub">{fmt(r.day)}</span> · {r.name ? driveLabel(c.mode, { me: r.user_id === me.user_id, name: r.name }) : 'Nobody yet'}</span>
                  {r.user_id === me.user_id
                    ? <button className="btn sm" onClick={() => call(() => api('/api/circle/rota/cant', { method: 'POST', body: { day: r.day } }), 'Swapped. Someone else has been asked to cover')}>Can’t do it</button>
                    : <button className="btn sm" onClick={() => call(() => api('/api/circle/rota/take', { method: 'POST', body: { day: r.day } }), 'You’ve taken that day')}>I’ll take it</button>}</div>
              ))}
              <p className="hint" style={{ marginTop: 6 }}>Turns rotate fairly between members who can drive or drop.{c.mode === 'Classmate drives' ? ' Drivers need a valid licence; the circle shares fuel only.' : ''}</p></div>}
          </div>
          <div className="card stack"><div className="row" style={{ justifyContent: 'space-between' }}><h3>WhatsApp group</h3><span className="badge sign">Coming soon</span></div>
            <p style={{ margin: 0 }}><b>{c.whatsapp_name}</b></p><p className="hint" style={{ margin: 0 }}>Chat there. Use the app for confirmations, money, the rota and changes.</p>
            <div className="wa"><div className="bub in">CommuteCircle: Reached campus today? Reply <b>1</b> = Yes, <b>2</b> = Didn’t go</div><div className="bub out">1</div>
              <div className="bub in">✓ Confirmed for your circle. Your share: {rs(c.share_hint)}?  Reply with an amount or <b>skip</b></div></div>
            <p className="hint" style={{ margin: 0 }}>Preview of daily confirmation by WhatsApp (stretch goal).</p></div>
          <div className="card stack"><h3>New term or new timetable?</h3><p className="hint" style={{ margin: 0 }}>Timetables change each term. Update yours and we’ll re-match you, keeping your current circle members as options.</p>
            <div><button className="btn" onClick={() => { setRematch(true); nav('/find'); window.scrollTo({ top: 0 }) }}>Update timetable and re-match</button></div></div>
          {fb && (
            <div className="card stack"><h3>Private feedback</h3>
              <p className="hint">{fb.up ? `What did ${fb.m.name} do well?` : `What went wrong with ${fb.m.name}? Only Student Affairs sees this.`}</p>
              <div className="opts">{(fb.up ? meta.tags : meta.neg_tags).map((t) => <button key={t} className="opt" aria-pressed={fb.tag === t} onClick={() => setFb({ ...fb, tag: t })}>{t}</button>)}</div>
              <div className="row"><button className="btn primary" onClick={sendFb}>Send</button><button className="btn" onClick={() => setFb(null)}>Cancel</button></div></div>
          )}
          <details className="card"><summary style={{ cursor: 'pointer', fontWeight: 700 }}>Report a problem or leave the circle</summary>
            <div className="stack" style={{ marginTop: 12 }}>
              <div><label className="hint" htmlFor="r-who">Who is it about?</label><select id="r-who" value={rep.who} onChange={(e) => setRep({ ...rep, who: e.target.value })}>{c.members.filter((m) => !m.me).map((m) => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}</select></div>
              <div><label className="hint" htmlFor="r-why">What happened?</label><select id="r-why" value={rep.why} onChange={(e) => setRep({ ...rep, why: e.target.value })}>{meta?.report_reasons.map((r) => <option key={r}>{r}</option>)}</select></div>
              <div><label className="hint" htmlFor="r-det">Details (optional)</label><input type="text" id="r-det" value={rep.det} onChange={(e) => setRep({ ...rep, det: e.target.value })} /></div>
              <div className="row"><button className="btn danger" onClick={() => report(true)}>Report and leave</button><button className="btn" onClick={leave}>Just leave the circle</button></div>
              <p className="hint">Feel unsafe right now? Contact BIC campus security straight away, or call 15 (Police).</p></div></details>
        </aside>
      </div>
    </>
  )
}
