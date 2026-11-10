import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, k1, rs } from '../api'
import { useAuth } from '../auth'
import { useCircle } from '../App'
import { useMeta } from '../meta'
import Map from '../components/Map'
import { useToast } from '../components/Toast'
import { Av, Err, Loading } from '../components/ui'
import VerifyEmail from '../components/VerifyEmail'

export default function Find() {
  const { circle } = useCircle()
  if (circle && circle.status === 'proposed') return <Proposed c={circle} />
  return <Search />
}

function Search() {
  const { user } = useAuth()
  const { rematch, setRematch, reload } = useCircle()
  const meta = useMeta()
  const toast = useToast()
  const nav = useNavigate()
  const [t, setT] = useState(null)
  const [stage, setStage] = useState('trip')
  const [res, setRes] = useState(null)
  const [ix, setIx] = useState(0)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [perDay, setPerDay] = useState(false)

  useEffect(() => {
    api('/api/trip').then((d) => {
      const ex = {}
      d.days.forEach((x) => { const s = d.schedule[x]; if (s && (s.in !== d.arrive || s.out !== d.leave)) ex[x] = s })
      setT({ ...d, area: d.area || '', exceptions: ex })
      setPerDay(Object.keys(ex).length > 0)
    })
  }, [])
  if (!t || !meta) return <Loading />

  const toggle = (k, v) => setT({ ...t, [k]: t[k].includes(v) ? t[k].filter((x) => x !== v) : [...t[k], v] })
  const setEx = (d, k, v) => setT({ ...t, exceptions: { ...t.exceptions, [d]: { ...(t.exceptions[d] || { in: t.arrive, out: t.leave }), [k]: v } } })
  const go = async () => {
    setErr('')
    if (!t.days.length) { toast('Pick at least one day'); return }
    if (!t.methods.length) { toast('Pick at least one way to travel'); return }
    setBusy(true)
    try {
      const ex = perDay ? Object.fromEntries(Object.entries(t.exceptions).filter(([d]) => t.days.includes(d))) : {}
      await api('/api/trip', { method: 'PUT', body: { area: t.area, days: t.days, arrive: t.arrive, leave: t.leave, women_only: t.women_only, methods: t.methods, has_car: t.has_car, seats: Number(t.seats) || 0, has_bike: !!t.has_bike, exceptions: ex } })
      if (user.status !== 'approved') { toast('Saved. You can search once Student Affairs approves your sign-up.'); return }
      setRes(await api('/api/find/options')); setIx(0); setStage('match'); window.scrollTo({ top: 0 })
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  const accept = async () => {
    setErr(''); setBusy(true)
    try {
      await api('/api/find/accept', { method: 'POST', body: { member_ids: res.options[ix].member_ids } })
      setRematch(false); await reload(); toast('Circle proposed. We’ve asked the others to accept.'); nav('/find')
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (stage === 'match') return <Options res={res} ix={ix} setIx={setIx} accept={accept} back={() => setStage('trip')} err={err} busy={busy} womenOnly={t.women_only} />

  const first = user.full_name.split(' ')[0]
  const pinMe = t.area ? [{ coords: meta.areas[t.area], area: t.area, me: true, pickup: 1 }] : []
  return (
    <>
      <h2>{rematch ? 'Update your timetable to re-match' : `Hi ${first}, let’s find your circle`}</h2>
      <p className="lead">Three quick questions. We match you with classmates who live near you, or on your way, and come to campus at the same times.</p>
      <VerifyEmail />
      {user.status === 'pending' && <div className="notice" style={{ marginBottom: 16 }}><span aria-hidden="true">ℹ</span><span>Student Affairs is checking your sign-up against the student record. Answer the questions now and you can search as soon as you’re approved.</span></div>}
      <div className="cols">
        <section className="card stack">
          <div><p className="q">1. Where do you travel from?</p>
            <select value={t.area} onChange={(e) => setT({ ...t, area: e.target.value })} aria-label="Home area" required>
              <option value="">Choose your area…</option>
              {Object.keys(meta.areas).sort().map((a) => <option key={a}>{a}</option>)}
            </select>
            <p className="hint" style={{ marginTop: 6 }}>Area only. We never ask for your address.</p></div>
          <div><p className="q">2. When are you on campus?</p>
            <div className="opts">{meta.days.map((d) => <button type="button" key={d} className="opt day" aria-pressed={t.days.includes(d)} onClick={() => toggle('days', d)}>{d}</button>)}</div>
            <div className="row" style={{ marginTop: 10, flexWrap: 'nowrap' }}>
              <div style={{ flex: 1 }}><label className="hint" htmlFor="t-in">Usually arrive</label><input type="time" id="t-in" value={t.arrive} onChange={(e) => setT({ ...t, arrive: e.target.value })} /></div>
              <div style={{ flex: 1 }}><label className="hint" htmlFor="t-out">Usually leave</label><input type="time" id="t-out" value={t.leave} onChange={(e) => setT({ ...t, leave: e.target.value })} /></div>
            </div>
            <label className="switch" style={{ marginTop: 10 }}><input type="checkbox" checked={perDay} onChange={(e) => setPerDay(e.target.checked)} /><span className="hint">Different times on some days</span></label>
            {perDay && t.days.map((d) => (
              <div key={d} className="row" style={{ marginTop: 6, flexWrap: 'nowrap' }}>
                <span className="mono" style={{ width: 40 }}>{d}</span>
                <input type="time" aria-label={`${d} arrive`} value={(t.exceptions[d] || {}).in || t.arrive} onChange={(e) => setEx(d, 'in', e.target.value)} />
                <input type="time" aria-label={`${d} leave`} value={(t.exceptions[d] || {}).out || t.leave} onChange={(e) => setEx(d, 'out', e.target.value)} />
              </div>
            ))}</div>
          <div><p className="q">3. Preferences</p>
            {t.gender === 'female'
              ? <label className="switch"><input type="checkbox" checked={t.women_only} onChange={(e) => setT({ ...t, women_only: e.target.checked })} /><span><b>Women-only circle</b><br /><span className="hint">Only women will be suggested, and you'll only be shown to women.</span></span></label>
              : <p className="hint">Some female students choose women-only circles. They won't be suggested to you.</p>}
            <p className="hint" style={{ margin: '12px 0 6px' }}>How would you travel together?</p>
            <div className="opts">{meta.methods.map((m) => <button type="button" key={m} className="opt" aria-pressed={t.methods.includes(m)} onClick={() => toggle('methods', m)}>{m}</button>)}</div>
            {t.methods.includes('Classmate drives') && (
              <div className="row" style={{ marginTop: 10 }}>
                <label className="switch"><input type="checkbox" checked={t.has_car} onChange={(e) => setT({ ...t, has_car: e.target.checked, seats: e.target.checked ? Math.max(1, t.seats) : 0 })} /><span>I can drive my own car</span></label>
                {t.has_car && <label className="hint row" style={{ gap: 6 }}>Seats for classmates <input type="number" min="1" max="6" value={t.seats} onChange={(e) => setT({ ...t, seats: e.target.value })} style={{ width: 80 }} /></label>}
              </div>
            )}
            {t.methods.includes('Motorbike pillion') && (
              <label className="switch" style={{ marginTop: 10 }}><input type="checkbox" checked={!!t.has_bike} onChange={(e) => setT({ ...t, has_bike: e.target.checked })} /><span>I ride a motorbike and can take one pillion passenger</span></label>
            )}
            <p className="hint" style={{ marginTop: 8 }}><b>Shared ride-hailing:</b> Careem, Uber or inDrive, fare split. <b>Classmate drives:</b> a circle member drives their own car and the circle shares fuel. <b>Family driver / Parent drop:</b> one family drops the circle, often taking turns; passengers chip in Rs 20/km for fuel. <b>Rickshaw:</b> up to 3 passengers, fare split. <b>Motorbike pillion:</b> one passenger pays the rider Rs 15/km.</p></div>
          <Err>{err}</Err>
          <div className="row">
            <button className="btn primary big" onClick={go} disabled={busy || !t.area}>{busy ? 'Searching…' : user.status === 'approved' ? 'Find my circle' : 'Save my answers'}</button>
            {rematch && <button className="btn" onClick={() => { setRematch(false); nav('/circle') }}>Cancel</button>}
          </div>
        </section>
        <aside className="stack">
          <div className="card"><Map group={pinMe} /></div>
          <div className="notice"><span aria-hidden="true">ℹ</span><span>BIC doesn't arrange transport. CommuteCircle only introduces classmates; you and your families decide how to travel.</span></div>
        </aside>
      </div>
    </>
  )
}

function Options({ res, ix, setIx, accept, back, err, busy, womenOnly }) {
  const myName = useAuth().user.full_name
  const opts = res.options
  if (!opts.length) {
    return (
      <>
        <h2>No circle yet</h2>
        <p className="lead">Nobody near you or on your way travels at similar times yet. You're on the waiting list, and Student Affairs can see the demand in your area.</p>
        <div className="card stack"><p style={{ margin: 0 }}>Things you can try:</p>
          <ul style={{ margin: 0 }}>{womenOnly && <li>Turn off women-only</li>}<li>Check your arrival time</li><li>Add more campus days</li><li>Add another way to travel</li></ul>
          <div><button className="btn primary" onClick={back}>Change my answers</button></div></div>
      </>
    )
  }
  const g = opts[ix]
  return (
    <>
      <h2>We found {opts.length > 1 ? `${opts.length} possible circles` : 'a circle'} for you</h2>
      <p className="lead">Everyone lives near you or along your route, and arrives within about 15 minutes of you. Phone numbers are shared only when everyone accepts.</p>
      {opts.length > 1 && <div className="opts" style={{ marginBottom: 14 }}>{opts.map((o, i) => <button key={i} className="opt" aria-pressed={i === ix} onClick={() => setIx(i)}>Option {i + 1} · {o.fit}</button>)}</div>}
      <div className="cols">
        <section className="card stack">
          <div className="fit"><b className="mono">{g.fit}</b><div><div className="q" style={{ margin: 0 }}>{g.label}</div><div className="sub">Circle of {g.size} · together on {g.days.join(', ') || '—'} · {g.mode}</div></div></div>
          <div>{g.members.map((m) => (
            <div className="member" key={m.user_id}><Av name={m.me ? myName : m.name} n={m.pickup} />
              <div style={{ minWidth: 0 }}>
                <div className="nm">{m.name} <span className="sub">· {m.programme}</span></div><div className="sub">{m.area}</div>
                {!m.me && <div className="facts">{m.same_area ? <span className="badge ok">Same area</span> : <span className="badge">{k1(m.km)} km away</span>}
                  {m.on_way && !m.same_area && <span className="badge ok">On your way</span>}<span className="badge">{m.days_match} days match</span></div>}
              </div><div />
            </div>
          ))}</div>
          <Explain g={g} />
          <Err>{err}</Err>
          <div className="row"><button className="btn primary big" onClick={accept} disabled={busy}>Accept this circle</button><button className="btn" onClick={back}>Change my answers</button></div>
        </section>
        <aside className="stack">
          <div className="card"><Map group={g.members} others={res.others} /></div>
          <div className="tiles">
            <div className="tile"><b className="mono">{rs(g.solo_fare)}</b><span>a trip alone ({g.mode.toLowerCase()}, est.)</span></div>
            <div className="tile accent"><b className="mono">{rs(g.share_est)}</b><span>your share in this circle (est.)</span></div>
          </div>
        </aside>
      </div>
    </>
  )
}

function Proposed({ c }) {
  const myName = useAuth().user.full_name
  const { reload } = useCircle()
  const toast = useToast()
  const [err, setErr] = useState('')
  const pending = c.members.filter((m) => m.status === 'pending' && !m.me)
  const respond = async (accept) => {
    try { await api('/api/circle/respond', { method: 'POST', body: { accept } }); await reload(); toast(accept ? 'Accepted' : 'Declined. We won’t suggest this group again.') } catch (e) { setErr(e.message) }
  }
  const withdraw = async () => { try { await api('/api/circle/leave', { method: 'POST' }); await reload(); toast('You left the proposed circle') } catch (e) { setErr(e.message) } }
  return (
    <>
      <h2>{c.my_status === 'pending' ? 'A classmate suggested a circle with you' : 'Waiting for everyone to accept'}</h2>
      <p className="lead">Phone numbers are shared only when everyone accepts. Proposals are withdrawn if not everyone answers within 3 days.</p>
      <div className="cols">
        <section className={`hero ${c.my_status === 'pending' ? 'ask' : ''}`}>
          <div className="fit" style={{ background: 'var(--surface)' }}><b className="mono">{c.fit}</b><div><div className="q" style={{ margin: 0 }}>{c.label}</div><div className="sub">Circle of {c.members.length} · together on {c.travel_days.join(', ') || '—'} · {c.mode}</div></div></div>
          <div>{c.members.map((m) => (
            <div className="member" key={m.user_id}><Av name={m.me ? myName : m.name} n={m.pickup} />
              <div style={{ minWidth: 0 }}><div className="nm">{m.name} <span className="sub">· {m.programme}, Y{m.year}</span></div><div className="sub">{m.area}</div></div>
              <span className={`badge ${m.status === 'accepted' ? 'ok' : 'sign'}`}>{m.status === 'accepted' ? 'Accepted' : 'Waiting'}</span>
            </div>
          ))}</div>
          <Err>{err}</Err>
          {c.my_status === 'pending'
            ? <div className="ck"><button className="btn big primary" onClick={() => respond(true)}>✓ Accept</button><button className="btn big" onClick={() => respond(false)}>✗ Decline</button></div>
            : <div className="row" style={{ justifyContent: 'space-between' }}><span className="hint">Waiting for {pending.map((m) => m.name).join(', ')}.</span><button className="link" onClick={withdraw}>Withdraw</button></div>}
        </section>
        <aside className="card"><Map group={c.members} /></aside>
      </div>
    </>
  )
}

// Explainable match card (proposal 14.9): why each classmate fits, the detour, and the cost working.
function Explain({ g }) {
  const parts = [['route', 'Route', 40], ['near', 'Nearby', 20], ['sched', 'Timetable', 30], ['pref', 'Travel', 10]]
  return (
    <details className="why">
      <summary>Why this circle, and how is the cost worked out?</summary>
      <div className="scroll"><table className="bk"><thead><tr><th>Classmate</th>{parts.map(([k, l, max]) => <th key={k} style={{ whiteSpace: 'nowrap' }}>{l} /{max}</th>)}<th>Detour</th></tr></thead>
        <tbody>{g.members.map((m) => (
          <tr key={m.user_id}><td>{m.name}</td>
            {parts.map(([k, , max]) => <td key={k}>{m.fit_parts ? <span className="row" style={{ gap: 6, flexWrap: 'nowrap' }}><span className="mbar" style={{ width: 44 }}><i style={{ width: `${(m.fit_parts[k] / max) * 100}%` }} /></span><span className="mono">{m.fit_parts[k]}</span></span> : <span className="sub">you</span>}</td>)}
            <td className="mono">{m.detour_min ? `+${m.detour_min} min` : '—'}</td></tr>
        ))}</tbody></table></div>
      <ul className="why-list">{g.members.filter((m) => m.fit_parts).map((m) => (
        <li key={m.user_id}><b>{m.name}</b> · fit {m.fit_parts.total}/100<br />
          <span className="sub">{parts.map(([k, l, max]) => `${l} ${m.fit_parts[k]}/${max}`).join(' · ')}{m.detour_min ? ` · detour +${m.detour_min} min` : ''}</span></li>
      ))}</ul>
      <p className="hint" style={{ margin: '8px 0 4px' }}>Fit with you out of 100. Detour = extra minutes compared with going straight to campus (road distances from OpenStreetMap, peak traffic). No one's detour is over 12 minutes.</p>
      {g.costs.map((c) => <p key={c.mode} style={{ margin: '6px 0' }}><b>{c.mode}:</b> {c.text}</p>)}
      <p className="hint" style={{ margin: 0 }}>Pickup is at your area's centre point; we never use your address.</p>
    </details>
  )
}
