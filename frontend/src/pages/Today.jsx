import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth'
import { api, fmt, k1, rs, sa } from '../api'
import Map from '../components/Map'
import { useToast } from '../components/Toast'
import { Av, Err, Loading, useLoad } from '../components/ui'

export default function Today() {
  const myName = useAuth().user.full_name
  const [d, err, reload] = useLoad(() => api('/api/today'))
  const [seatOpen, setSeatOpen] = useState(false)
  const toast = useToast()
  if (err) return <Err>{err}</Err>
  if (!d) return <Loading />
  const t = d.trip
  const act = async (path, body, msg) => {
    try { await api(path, { method: 'POST', body }); reload(); if (msg) toast(msg) } catch (e) { toast(e.message) }
  }

  let card
  if (!t) {
    card = <div className="hero quiet"><div><p className="eyebrow">{fmt(d.date)}</p><h2>No circle trip planned for you today</h2><p className="hint">Your circle travels on {d.travel_days.join(', ')}.</p></div></div>
  } else if (t.confirmed) {
    card = (
      <>
        <div className="hero done"><div><p className="eyebrow">{fmt(d.date)} · confirmed</p>
          <h2>{t.confirmed_by_me ? 'You confirmed today’s trip' : `${t.confirmed_by} confirmed today’s trip`} for {t.went} {t.went > 1 ? 'people' : 'person'}</h2>
          {t.my_status === 'went'
            ? (t.share != null && <p className="big">Your share: <b className="mono">{rs(t.share)}</b> · saved about <b className="mono">{rs(t.saved)}</b> vs going alone</p>)
            : <p className="hint">You're marked as not travelling today.</p>}</div>
          {!t.confirmed_by_me && <button className="link" onClick={() => act('/api/today/correct', undefined, 'Thanks, your record is updated')}>{t.my_status === 'went' ? 'Not me? I didn’t go' : 'Actually, I did go'}</button>}
        </div>
        {t.ask_fare && <FareCard t={t} onSave={(body, msg) => act('/api/today/fare', body, msg)} />}
      </>
    )
  } else if (t.my_status === 'notgoing') {
    card = <div className="hero quiet"><div><p className="eyebrow">{fmt(d.date)}</p><h2>You’re not travelling with your circle today</h2><p className="hint">The others can still confirm their trip.</p></div></div>
  } else {
    card = (
      <div className="hero ask"><div><p className="eyebrow">{fmt(d.date)}</p><h2>Reached campus with your circle today?</h2><p className="hint">One tap. It counts for your whole circle.</p></div>
        <div className="ck"><button className="btn big primary" onClick={() => act('/api/today/yes', undefined, 'Trip confirmed for your circle')}>✓ Yes</button>
          <button className="btn big" onClick={() => act('/api/today/no', undefined, 'Marked as not travelling today')}>✗ Didn’t go</button></div>
      </div>
    )
  }

  const rt = d.rota_today
  return (
    <div className="cols">
      <section className="stack">
        {card}
        {d.seat_requests.map((s) => (
          <div key={s.id} className="card row" style={{ justifyContent: 'space-between' }}>
            <div><p className="eyebrow">One-day seat request</p><p className="q" style={{ margin: '2px 0 0' }}>{s.name} from {sa(s.area)} would like a seat today</p></div>
            <div className="row"><button className="btn sm primary" onClick={() => act(`/api/seats/${s.id}/answer`, { accept: true }, 'Seat accepted')}>Accept</button>
              <button className="btn sm" onClick={() => act(`/api/seats/${s.id}/answer`, { accept: false }, 'Seat declined')}>Decline</button></div>
          </div>
        ))}
        {rt && <div className="card row" style={{ justifyContent: 'space-between' }}><div><p className="eyebrow">Today’s drive</p><p className="q" style={{ margin: '2px 0 0' }}>{driveLabel(d.mode, rt)}</p></div><Link className="link" to="/circle">See the rota</Link></div>}
        {d.guest
          ? <div className="hero done"><div><p className="eyebrow">One-day seat · {fmt(d.date)}</p><h2>You’re travelling with {d.guest.members.join(', ')} today</h2><p className="hint">Only for today. Your own circle is unchanged.</p></div>
            <button className="link" onClick={() => act(`/api/seats/${d.guest.seat_id}/cancel`, undefined, 'Today’s seat cancelled')}>Cancel today’s seat</button></div>
          : t && <SeatFinder open={seatOpen} setOpen={setSeatOpen} pending={d.my_seat_request} onChange={reload} />}
        <div className="card"><div className="row" style={{ justifyContent: 'space-between' }}><div><p className="eyebrow">Tomorrow · {fmt(d.tomorrow.date)}</p>
          <p className="q" style={{ margin: '2px 0 0' }}>{d.tomorrow.planned ? (d.tomorrow.off ? 'You’re not going' : <>You’re going · arrive <span className="mono">{d.tomorrow.arrive}</span></>) : 'No circle trip planned'}</p>
          <p className="hint">Your weekly plan is used automatically. Tap only if it changes.</p></div>
          {d.tomorrow.planned && <button className={`btn ${d.tomorrow.off ? 'primary' : ''}`} onClick={() => act('/api/tomorrow', { going: d.tomorrow.off }, d.tomorrow.off ? 'You’re back on for tomorrow' : 'Your circle will see you’re not going tomorrow')}>{d.tomorrow.off ? 'I’m going after all' : 'Not going tomorrow'}</button>}</div></div>
        <div className="tiles">
          <div className="tile"><b className="mono">{d.tiles.streak}</b><span>day circle streak</span></div>
          <div className="tile"><b className="mono">{d.tiles.went}</b><span>trips with your circle</span></div>
          <div className="tile accent"><b className="mono">{rs(d.tiles.saved)}</b><span>saved vs going alone</span></div>
          <div className="tile"><b className="mono">{d.tiles.reliability == null ? '—' : d.tiles.reliability + '%'}</b><span>you show up when you say</span></div>
        </div>
      </section>
      <aside className="stack">
        <div className="card"><h3 style={{ marginBottom: 8 }}>Today’s circle</h3>
          {d.members.map((m) => {
            const cls = m.status === 'went' ? 'go' : m.status === 'planned' ? 'wait' : 'no'
            return (
              <div className="who-row" key={m.user_id}>
                <span className="row" style={{ gap: 10, flexWrap: 'nowrap' }}><Av name={m.me ? myName : m.name} sm /><span>{m.me ? <b>You</b> : m.name}<br /><span className="sub">pickup {m.pickup} · {sa(m.area)}</span></span></span>
                <span className={`st ${cls}`}>{m.label}</span>
              </div>
            )
          })}
          <p className="hint" style={{ marginTop: 8 }}>Travelling by {d.mode} · route about {k1(d.road_km)} km</p></div>
        <div className="card"><Map group={d.members} /></div>
      </aside>
    </div>
  )
}

export const driveLabel = (mode, r) => {
  const n = r.me ? null : r.name
  if (mode === 'Classmate drives') return r.me ? 'You drive' : `${n} drives`
  if (mode === 'Family driver') return r.me ? 'Your family driver' : `${n}’s family driver`
  return r.me ? 'Your parent drops' : `${n}’s parent drops`
}

function FareCard({ t, onSave }) {
  const [custom, setCustom] = useState(false)
  const [amt, setAmt] = useState('')
  const [payer, setPayer] = useState(t.payers.find((p) => p.name === 'Me')?.user_id)
  const save = (share) => onSave({ share, payer_id: Number(payer) }, 'Fare saved and added to Money')
  return (
    <div className="card fare">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}><p className="q" style={{ margin: 0 }}>Your share today? <span className="hint">(optional)</span></p>
        <label className="hint row" style={{ gap: 6, flexWrap: 'nowrap' }}>Paid by <select value={payer} onChange={(e) => setPayer(e.target.value)} style={{ width: 'auto', padding: '5px 8px' }}>{t.payers.map((p) => <option key={p.user_id} value={p.user_id}>{p.name}</option>)}</select></label></div>
      <p className="hint" style={{ margin: '4px 0 10px' }}>Adds to your circle’s Money tab so everyone pays their fair share.</p>
      <div className="opts">{t.suggestions.map((v) => <button key={v} className="opt" onClick={() => save(v)}>{rs(v)}</button>)}
        <button className="opt" onClick={() => setCustom(true)}>Other</button><button className="opt ghost" onClick={() => onSave({ skip: true })}>Skip</button></div>
      {custom && <div className="row" style={{ marginTop: 10, flexWrap: 'nowrap' }}><input type="number" min="1" step="10" placeholder="Amount in Rs" aria-label="Your share in rupees" value={amt} onChange={(e) => setAmt(e.target.value)} />
        <button className="btn primary" onClick={() => (Number(amt) > 0 ? save(Number(amt)) : null)}>Save</button></div>}
    </div>
  )
}

function SeatFinder({ open, setOpen, pending, onChange }) {
  const [opts, setOpts] = useState(null)
  const toast = useToast()
  const toggle = async () => { if (!open) setOpts(await api('/api/seats').catch(() => [])); setOpen(!open) }
  const request = async (cid) => { try { await api('/api/seats', { method: 'POST', body: { circle_id: cid } }); toast('Seat requested. That circle will be asked.'); setOpen(false); onChange() } catch (e) { toast(e.message) } }
  if (pending) return <div className="card row" style={{ justifyContent: 'space-between' }}><div><p className="q" style={{ margin: 0 }}>Seat requested</p><p className="hint">Waiting for the other circle to accept.</p></div><button className="link" onClick={async () => { await api(`/api/seats/${pending.id}/cancel`, { method: 'POST' }); onChange() }}>Cancel</button></div>
  return (
    <div className="card"><div className="row" style={{ justifyContent: 'space-between' }}><div><p className="q" style={{ margin: 0 }}>Circle not going today?</p><p className="hint">Find a one-day seat with another verified circle on your route.</p></div>
      <button className="btn" onClick={toggle}>{open ? 'Hide' : 'Find a seat'}</button></div>
      {open && (opts?.length
        ? opts.map((x) => <div className="who-row" key={x.circle_id}><span>{x.members.join(', ')}<br /><span className="sub">{sa(x.area)} · {x.on_way ? 'on your way' : k1(x.near_km) + ' km away'} · arrives {x.arrive} · {x.free} seat{x.free > 1 ? 's' : ''} free</span></span><button className="btn sm primary" onClick={() => request(x.circle_id)}>Request</button></div>)
        : <p className="hint" style={{ marginTop: 8 }}>No circle with a free seat near you today.</p>)}
    </div>
  )
}
