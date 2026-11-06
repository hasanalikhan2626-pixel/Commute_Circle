import { api } from '../../api'
import { Alert, Badge, Card, Spinner, STATUS_TONE, useLoad } from '../../components/ui'

const LABEL = { unsafe_driving: 'Unsafe driving', harassment: 'Harassment', no_show: 'No-show', payment: 'Payment', other: 'Other' }

export default function Reports() {
  const [reports, err, reload] = useLoad(() => api('/api/admin/reports'))
  const update = async (r, status) => {
    const admin_note = prompt('Note for the record (optional):', r.admin_note || '') ?? r.admin_note
    await api(`/api/admin/reports/${r.id}`, { method: 'PATCH', body: { status, admin_note } })
    reload()
  }
  if (err) return <Alert>{err}</Alert>
  if (!reports) return <Spinner />
  return (
    <Card title="Safety reports">
      {reports.length === 0 ? <p className="muted">No reports. 🎉</p> : (
        <div className="stack">
          {reports.map((r) => (
            <div key={r.id} className="report">
              <div className="row between">
                <div><Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge> <strong>{LABEL[r.reason]}</strong>: {r.reporter_name} reported <strong>{r.reported_name}</strong>
                  {r.circle_id && <span className="muted"> · circle #{r.circle_id}</span>}</div>
                <span className="muted small">{new Date(r.created_at).toLocaleString('en-GB')}</span>
              </div>
              {r.details && <p>{r.details}</p>}
              {r.admin_note && <p className="muted small">Admin note: {r.admin_note}</p>}
              {r.status === 'open' && (
                <div className="row">
                  <button className="btn btn-primary" onClick={() => update(r, 'resolved')}>Mark resolved</button>
                  <button className="btn" onClick={() => update(r, 'dismissed')}>Dismiss</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <p className="muted small">To suspend a student, go to the Students tab. Suspending removes them from their circle at once.</p>
    </Card>
  )
}
