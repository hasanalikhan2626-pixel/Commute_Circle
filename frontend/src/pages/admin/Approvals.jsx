import { api, fmt } from '../../api'
import { useToast } from '../../components/Toast'
import { Err, Loading, useLoad } from '../../components/ui'

export default function Approvals() {
  const [rows, err, reload] = useLoad(() => api('/api/admin/approvals'))
  const toast = useToast()
  const decide = async (u, approve) => { await api(`/api/admin/approvals/${u.id}`, { method: 'POST', body: { approve } }); reload(); toast(approve ? 'Member approved' : 'Sign-up rejected') }
  if (err) return <Err>{err}</Err>
  if (!rows) return <Loading />
  return (
    <>
      <h2>Approvals</h2>
      <p className="lead">Check each sign-up against the student record. Members accept the Terms, Privacy Notice and Code of Conduct at sign-up; acceptance is logged.</p>
      <section className="card">{rows.length ? <div className="scroll"><table className="tt">
        <thead><tr><th>Name</th><th>Programme</th><th>Area</th><th>Email</th><th>Terms accepted</th><th /></tr></thead>
        <tbody>{rows.map((s) => <tr key={s.id}><td><b>{s.full_name}</b><br /><span className="sub mono">{s.email}</span></td><td>{s.programme} · Y{s.year}</td><td>{s.area || <span className="sub">not set yet</span>}</td>
          <td>{s.email_verified ? <span className="badge ok">✓ Verified</span> : <span className="badge sign">Not yet</span>}</td>
          <td className="sub">v{s.consent_version} · {fmt(s.consented_at)}</td>
          <td><div className="row" style={{ flexWrap: 'nowrap' }}><button className="btn sm primary" onClick={() => decide(s, true)}>Approve</button><button className="btn sm" onClick={() => decide(s, false)}>Reject</button></div></td></tr>)}</tbody></table></div>
        : <div className="empty">No sign-ups waiting.</div>}</section>
    </>
  )
}
