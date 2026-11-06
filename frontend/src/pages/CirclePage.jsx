import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, DAY_LABELS, fmtDate, pkr } from '../api'
import { useAuth } from '../auth'
import { Alert, Badge, Card, Spinner, STATUS_TONE, Stat, useLoad } from '../components/ui'

export default function CirclePage() {
  const { user } = useAuth()
  const [circles, err, reload] = useLoad(() => api('/api/circles/mine'))
  const [profile] = useLoad(() => api('/api/profile'))
  if (err) return <Alert>{err}</Alert>
  if (!circles || !profile) return <Spinner />

  const live = circles.find((c) => c.status !== 'dissolved' && ['pending', 'accepted'].includes(c.my_status))
  const history = circles.filter((c) => c !== live)
  return (
    <div className="stack">
      {live ? <LiveCircle c={live} me={user} onChange={reload} /> : <Waiting seeking={profile.seeking} />}
      {history.length > 0 && (
        <Card title="Past circles">
          <ul className="list">
            {history.map((c) => (
              <li key={c.id}><span>Circle #{c.id} · {fmtDate(c.created_at.slice(0, 10))}</span>
                <span className="row"><Badge tone={STATUS_TONE[c.my_status]}>{c.my_status}</Badge> {c.dissolved_reason && <span className="muted">{c.dissolved_reason}</span>}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

function Waiting({ seeking }) {
  return (
    <Card title="No circle yet">
      {seeking ? (
        <p>You are in the matching pool. The transport office runs matching regularly, and you will see a proposed circle here when we find students on your route with a matching timetable.</p>
      ) : (
        <Alert kind="warn">You have paused matching. <Link to="/profile">Turn it back on</Link> to be included in the next round.</Alert>
      )}
      <p className="muted">Tip: the more days you list, and the more flexible your times, the easier you are to match.</p>
    </Card>
  )
}

function LiveCircle({ c, me, onChange }) {
  const [err, setErr] = useState('')
  const [reporting, setReporting] = useState(null)
  const act = async (fn) => { setErr(''); try { await fn(); onChange() } catch (e) { setErr(e.message) } }
  const respond = (accept) => act(() => api(`/api/circles/${c.id}/respond`, { method: 'POST', body: { accept } }))
  const leave = () => { if (confirm('Leave this circle? If it can no longer run without you it will be dissolved.')) act(() => api(`/api/circles/${c.id}/leave`, { method: 'POST' })) }
  const myMember = c.members.find((m) => m.user_id === me.id)
  const mine = c.costs.per_member?.find((x) => x.user_id === me.id)

  return (
    <>
      <Card title={<>Your circle <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge></>}
        actions={c.status === 'active' && <button className="btn btn-ghost" onClick={leave}>Leave circle</button>}>
        {c.status === 'proposed' && (
          <Alert kind="info">
            We found a circle for you. Contact details are shared once everyone accepts.
            {c.my_status === 'pending' ? (
              <div className="row mt">
                <button className="btn btn-primary" onClick={() => respond(true)}>Accept</button>
                <button className="btn" onClick={() => respond(false)}>Decline</button>
              </div>
            ) : <div className="mt">You accepted. Waiting for the others.</div>}
          </Alert>
        )}
        <Alert>{err}</Alert>
        <p className="muted">Travelling together on {c.shared_days.map((d) => DAY_LABELS[d]).join(', ') || '—'}</p>
        <div className="members">
          {c.members.map((m) => (
            <div key={m.user_id} className="member">
              <div className="avatar" aria-hidden>{m.full_name.split(' ').map((x) => x[0]).slice(0, 2).join('')}</div>
              <div className="grow">
                <div><strong>{m.full_name}</strong>{m.user_id === me.id && ' (you)'} {m.is_driver && <Badge tone="info">Driver</Badge>}</div>
                <div className="muted">{m.area}{m.pickup_landmark && ` · ${m.pickup_landmark}`}</div>
                {m.phone && <a href={`tel:${m.phone}`}>{m.phone}</a>}
              </div>
              {c.status === 'proposed' && <Badge tone={STATUS_TONE[m.status]}>{m.status}</Badge>}
              {m.user_id !== me.id && c.status === 'active' && <button className="btn btn-link" onClick={() => setReporting(m)}>Report</button>}
            </div>
          ))}
        </div>
      </Card>

      {c.costs.available && (
        <Card title="Cost split">
          <div className="stats">
            <Stat label="Your share per trip" value={pkr(c.costs.share_per_trip_pkr)} hint={`of ${pkr(c.costs.trip_cost_pkr)} (${c.costs.trip_km} km)`} />
            <Stat label="Your monthly share" value={pkr(c.costs.monthly_share_pkr)} />
            {mine && <Stat label="Driving alone would cost" value={pkr(mine.solo_monthly_pkr)} hint={`You save about ${mine.saving_pct}%`} />}
          </div>
          <p className="muted small">{c.costs.assumptions}</p>
        </Card>
      )}

      {c.status === 'active' && <Rota c={c} me={me} isDriver={myMember?.is_driver} onChange={onChange} setErr={setErr} />}
      {reporting && <ReportDialog circle={c} member={reporting} onClose={() => setReporting(null)} />}
    </>
  )
}

function Rota({ c, me, isDriver, onChange, setErr }) {
  const unavailable = async (day) => {
    try { await api(`/api/circles/${c.id}/unavailable`, { method: 'POST', body: { day } }); onChange() } catch (e) { setErr(e.message) }
  }
  return (
    <Card title="Driving rota · next two weeks">
      {c.rota.length === 0 ? <p className="muted">No shared days in the next two weeks.</p> : (
        <table className="table">
          <thead><tr><th>Day</th><th>Be ready by</th><th>Driver</th>{isDriver && <th />}</tr></thead>
          <tbody>
            {c.rota.map((e) => (
              <tr key={e.day} className={e.driver_id === me.id ? 'hl' : ''}>
                <td>{fmtDate(e.day)}</td>
                <td>Arrive {e.arrive}</td>
                <td>{e.driver_name ?? <Badge tone="bad">No driver: arrange together</Badge>}</td>
                {isDriver && <td>{e.driver_id === me.id && <button className="btn btn-link" onClick={() => unavailable(e.day)}>Can't drive</button>}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="muted small">Turns are shared evenly between drivers. If you can't drive, the rota hands the day to another driver.</p>
    </Card>
  )
}

function ReportDialog({ circle, member, onClose }) {
  const [reason, setReason] = useState('unsafe_driving')
  const [details, setDetails] = useState('')
  const [state, setState] = useState({})
  const submit = async (e) => {
    e.preventDefault()
    try {
      await api('/api/reports', { method: 'POST', body: { reported_id: member.user_id, circle_id: circle.id, reason, details } })
      setState({ done: true })
    } catch (ex) { setState({ err: ex.message }) }
  }
  return (
    <div className="modal" role="dialog" aria-modal="true" onClick={onClose}>
      <form className="card" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>Report {member.full_name}</h2>
        {state.done ? (
          <><Alert kind="ok">Thank you. The transport office will review this in confidence.</Alert><button type="button" className="btn" onClick={onClose}>Close</button></>
        ) : (
          <>
            <p className="muted">Reports are confidential. If you are in danger, call 15 (Police) first.</p>
            <label>Reason
              <select value={reason} onChange={(e) => setReason(e.target.value)}>
                <option value="unsafe_driving">Unsafe driving</option>
                <option value="harassment">Harassment or inappropriate behaviour</option>
                <option value="no_show">Repeated no-shows</option>
                <option value="payment">Payment dispute</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label>What happened?<textarea rows={4} maxLength={2000} value={details} onChange={(e) => setDetails(e.target.value)} /></label>
            <Alert>{state.err}</Alert>
            <div className="row"><button className="btn btn-primary">Send report</button><button type="button" className="btn" onClick={onClose}>Cancel</button></div>
          </>
        )}
      </form>
    </div>
  )
}
