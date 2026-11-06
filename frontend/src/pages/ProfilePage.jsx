import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, DAY_LABELS } from '../api'
import { useAuth } from '../auth'
import { Alert, Card, Spinner } from '../components/ui'

const EMPTY = { area: '', pickup_landmark: '', gender: 'undisclosed', same_gender_only: false, has_car: false, seats: 0, schedule: {}, seeking: true }

export default function ProfilePage() {
  const { user, refresh } = useAuth()
  const nav = useNavigate()
  const [meta, setMeta] = useState(null)
  const [p, setP] = useState(null)
  const [msg, setMsg] = useState({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api('/api/meta').then(setMeta)
    api('/api/profile').then((d) => setP({ ...EMPTY, ...d, pickup_landmark: d.pickup_landmark || '' }))
      .catch(() => setP({ ...EMPTY, schedule: { mon: { arrive: '08:30', leave: '14:30' } } }))
  }, [])

  if (!meta || !p) return <Spinner />
  const set = (k, v) => setP({ ...p, [k]: v })
  const toggleDay = (d) => {
    const s = { ...p.schedule }
    if (s[d]) delete s[d]; else s[d] = { arrive: '08:30', leave: '14:30' }
    set('schedule', s)
  }
  const setTime = (d, k, v) => set('schedule', { ...p.schedule, [d]: { ...p.schedule[d], [k]: v } })

  const save = async (e) => {
    e.preventDefault()
    setBusy(true); setMsg({})
    try {
      const body = { ...p, seats: p.has_car ? Number(p.seats) : 0, pickup_landmark: p.pickup_landmark || null }
      const res = await api('/api/profile', { method: 'PUT', body })
      const first = !user.has_profile
      await refresh()
      setMsg({ ok: 'Saved.', warn: res.warning })
      if (first) nav('/circle')
    } catch (ex) { setMsg({ err: ex.message }) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={save} className="stack">
      {!user.has_profile && <Alert kind="info">Tell us how you get to campus. We use this to find students on your route with a matching timetable.</Alert>}
      <Card title="Where you start">
        <div className="grid2">
          <label>Area
            <select required value={p.area} onChange={(e) => set('area', e.target.value)}>
              <option value="">Choose your area…</option>
              {meta.areas.map((a) => <option key={a}>{a}</option>)}
            </select>
            <small className="muted">We match by area only. Your home address is never stored.</small>
          </label>
          <label>Pickup landmark <span className="muted">(optional)</span>
            <input maxLength={120} value={p.pickup_landmark} onChange={(e) => set('pickup_landmark', e.target.value)} placeholder="e.g. Outside Millennium Mall" />
            <small className="muted">Shown only to members of your confirmed circle.</small>
          </label>
        </div>
      </Card>

      <Card title="Your timetable">
        <p className="muted">Choose the days you are on campus. Arrival times within {meta.schedule_window_min} minutes of each other count as a match.</p>
        <div className="days">
          {meta.days.map((d) => {
            const on = !!p.schedule[d]
            return (
              <div key={d} className={`day ${on ? 'on' : ''}`}>
                <label className="check"><input type="checkbox" checked={on} onChange={() => toggleDay(d)} /> {DAY_LABELS[d]}</label>
                {on && (
                  <div className="times">
                    <label>Arrive<input type="time" required value={p.schedule[d].arrive} onChange={(e) => setTime(d, 'arrive', e.target.value)} /></label>
                    <label>Leave<input type="time" required value={p.schedule[d].leave} onChange={(e) => setTime(d, 'leave', e.target.value)} /></label>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </Card>

      <div className="grid2">
        <Card title="Car">
          <label className="check"><input type="checkbox" checked={p.has_car} onChange={(e) => setP({ ...p, has_car: e.target.checked, seats: e.target.checked ? Math.max(1, p.seats) : 0 })} /> I can drive and offer seats</label>
          {p.has_car && (
            <label>Passenger seats offered
              <input type="number" min={1} max={6} value={p.seats} onChange={(e) => set('seats', e.target.value)} />
            </label>
          )}
        </Card>
        <Card title="Safety preferences">
          <label>Gender
            <select value={p.gender} onChange={(e) => setP({ ...p, gender: e.target.value, same_gender_only: e.target.value === 'undisclosed' ? false : p.same_gender_only })}>
              <option value="undisclosed">Prefer not to say</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </label>
          <label className="check"><input type="checkbox" disabled={p.gender === 'undisclosed'} checked={p.same_gender_only} onChange={(e) => set('same_gender_only', e.target.checked)} /> Only match me with students of the same gender</label>
        </Card>
      </div>

      <Card>
        <label className="check"><input type="checkbox" checked={p.seeking} onChange={(e) => set('seeking', e.target.checked)} /> Include me in the next matching round</label>
        <Alert kind="ok">{msg.ok}</Alert>
        <Alert kind="warn">{msg.warn}</Alert>
        <Alert>{msg.err}</Alert>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save commute details'}</button>
      </Card>
    </form>
  )
}
