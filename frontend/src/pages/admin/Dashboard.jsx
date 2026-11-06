import { Link } from 'react-router-dom'
import { api, pkr } from '../../api'
import { Alert, Card, Spinner, Stat, useLoad } from '../../components/ui'

export default function Dashboard() {
  const [s, err] = useLoad(() => api('/api/admin/stats'))
  if (err) return <Alert>{err}</Alert>
  if (!s) return <Spinner />
  const m = s.last_run?.metrics
  return (
    <div className="stack">
      <div className="stats">
        <Stat label="Registered students" value={s.students} hint={`${s.profiles} with commute details`} />
        <Stat label="Drivers" value={s.drivers} />
        <Stat label="In active circles" value={s.students_in_active_circles} hint={`${Math.round(s.active_match_rate * 100)}% of students with details`} />
        <Stat label="Waiting for a match" value={s.seeking_unmatched} />
      </div>
      <div className="stats">
        <Stat label="Active circles" value={s.circles.active} />
        <Stat label="Awaiting acceptance" value={s.circles.proposed} />
        <Stat label="Dissolved" value={s.circles.dissolved} />
        <Stat label="Open safety reports" value={s.open_reports} hint={s.open_reports ? <Link to="/admin/reports">Review now</Link> : 'None'} />
      </div>
      <Card title="Last matching run" actions={<Link className="btn btn-primary" to="/admin/matching">Run matching</Link>}>
        {m ? (
          <p>{new Date(s.last_run.created_at).toLocaleString('en-GB')} · <strong>{m.algorithm}</strong> · {s.last_run.circles_created} circles,
            {' '}{s.last_run.students_matched}/{s.last_run.pool_size} matched ({Math.round(m.match_rate * 100)}%) · estimated {pkr(m.weekly_fuel_pkr_saved)} and {m.weekly_co2_kg_saved} kg CO₂ saved a week</p>
        ) : <p className="muted">No matching has been run yet.</p>}
      </Card>
    </div>
  )
}
