import { api } from '../../api'
import { Err, Loading, useLoad } from '../../components/ui'

const TONE = { sent: 'ok', mock: 'sign', failed: 'bad', queued: '' }

export default function Messages() {
  const [d, err] = useLoad(() => api('/api/admin/outbox'))
  if (err) return <Err>{err}</Err>
  if (!d) return <Loading />
  return (
    <>
      <h2>Messages</h2>
      <p className="lead">Every WhatsApp message and email CommuteCircle sends. “Mock” means the service isn’t connected yet, so the message was recorded but not sent.</p>
      <div className="kpis">
        <div className="kpi"><b>{d.whatsapp_ready ? 'Connected' : 'Not connected'}</b><span>WhatsApp Cloud API</span></div>
        <div className="kpi"><b>{d.email_ready ? 'Connected' : 'Not connected'}</b><span>Email (Brevo)</span></div>
      </div>
      <section className="card"><div className="scroll"><table className="tt">
        <thead><tr><th>When</th><th>Channel</th><th>To</th><th>Message</th><th>Status</th></tr></thead>
        <tbody>{d.messages.length ? d.messages.map((m) => <tr key={m.id}><td className="sub">{new Date(m.created_at).toLocaleString('en-GB')}</td><td>{m.channel}</td>
          <td className="mono">{m.to}</td><td style={{ maxWidth: 420 }}>{m.body}{m.error && <div className="sub" style={{ color: 'var(--bad)' }}>{m.error}</div>}</td>
          <td><span className={`badge ${TONE[m.status]}`}>{m.status}</span></td></tr>)
          : <tr><td colSpan="5" className="empty">No messages yet.</td></tr>}</tbody></table></div></section>
    </>
  )
}
