import { api } from '../../api'
import { useToast } from '../../components/Toast'
import { Err, Loading, useLoad } from '../../components/ui'

const when = (iso) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

export default function Reports() {
  const [d, err, reload] = useLoad(() => api('/api/admin/reports'))
  const toast = useToast()
  const set = async (r, status) => {
    if (status === 'suspended' && !confirm(`Suspend ${r.about}? They will be signed out and removed from their circle.`)) return
    await api(`/api/admin/reports/${r.id}`, { method: 'PATCH', body: { status } }); reload(); toast(status === 'suspended' ? 'Member suspended' : 'Report resolved')
  }
  if (err) return <Err>{err}</Err>
  if (!d) return <Loading />
  const label = { open: 'Open', resolved: 'Resolved', suspended: 'Member suspended' }
  return (
    <>
      <h2>Reports</h2>
      <p className="lead">Reports need a decision. Private negative feedback is shown below for context; it is never visible to other students.</p>
      <div className="stack">
        {d.reports.length ? d.reports.map((r) => (
          <section className="card" key={r.id}>
            <div className="row" style={{ justifyContent: 'space-between' }}><h3>{r.reason}</h3><span className={`badge ${r.status === 'open' ? 'bad' : 'ok'}`}>{label[r.status]}</span></div>
            <p style={{ margin: '8px 0' }}>{r.details}</p>
            <p className="hint" style={{ marginBottom: 12 }}>From {r.from} · About {r.about} · {when(r.created_at)}</p>
            {r.status === 'open' && <div className="row"><button className="btn sm primary" onClick={() => set(r, 'resolved')}>Mark resolved</button>
              {r.reported_id && <button className="btn sm danger" onClick={() => set(r, 'suspended')}>Suspend member</button>}</div>}
          </section>
        )) : <div className="card empty">No reports.</div>}
        <section className="card"><h3 style={{ marginBottom: 8 }}>Private negative feedback ({d.negative_feedback.length})</h3>
          <div className="scroll"><table className="tt"><thead><tr><th>About</th><th>Reason</th><th>From</th></tr></thead>
            <tbody>{d.negative_feedback.map((f, i) => <tr key={i}><td>{f.about}</td><td>{f.tag}</td><td className="sub">{f.from}</td></tr>)}</tbody></table></div></section>
      </div>
    </>
  )
}
