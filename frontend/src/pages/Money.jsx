import { api, fmt, rs } from '../api'
import { useToast } from '../components/Toast'
import { Err, Loading, useLoad } from '../components/ui'

export default function Money() {
  const [d, err, reload] = useLoad(() => api('/api/money'))
  const toast = useToast()
  if (err) return <Err>{err}</Err>
  if (!d) return <Loading />
  const mine = d.balance
  const settle = async (x) => { await api('/api/money/settle', { method: 'POST', body: { from_id: x.from_id, to_id: x.to_id, amount: x.amount } }); reload(); toast('Marked as settled') }
  const all = async () => { if (!confirm('Reset balances for everyone in the circle?')) return; await api('/api/money/settle-all', { method: 'POST' }); reload(); toast('Balances reset for everyone') }
  return (
    <>
      <h2>Money</h2>
      <p className="lead">Who paid and who owes, from the fares your circle entered. CommuteCircle doesn’t handle money: pay each other in cash or by bank transfer, then mark it settled.</p>
      <div className="cols">
        <section className="stack">
          <div className={`hero ${Math.abs(mine) < 5 ? 'quiet' : mine > 0 ? 'done' : 'ask'}`}><div><p className="eyebrow">Your balance</p>
            <h2>{Math.abs(mine) < 5 ? 'You’re all settled' : mine > 0 ? <>You’re owed <span className="mono">{rs(mine)}</span></> : <>You owe <span className="mono">{rs(-mine)}</span></>}</h2>
            <p className="hint">Since the last settle-up{d.settled_until ? ` on ${fmt(d.settled_until)}` : ''}.</p></div></div>
          <div className="card">{d.lines.length ? d.lines.map((x, i) => (
            <div className="who-row" key={i}><span>{x.to === 'You' ? <><b>{x.from}</b> owes you</> : <>You owe <b>{x.to}</b></>} <span className="mono">{rs(x.amount)}</span></span>
              <button className={`btn sm ${x.from === 'You' ? 'primary' : ''}`} onClick={() => settle(x)}>{x.from === 'You' ? 'I’ve paid' : 'Mark as received'}</button></div>
          )) : <p className="hint" style={{ margin: 0 }}>Nothing to settle with anyone right now.</p>}</div>
          <div className="card"><h3 style={{ marginBottom: 6 }}>Circle balances</h3>
            {d.members.map((s) => <div className="who-row" key={s.user_id}><span>{s.name === 'You' ? <b>You</b> : s.name}</span>
              <span className="mono" style={{ color: s.net > 5 ? 'var(--good)' : s.net < -5 ? 'var(--bad)' : 'var(--muted)', fontWeight: 600 }}>{Math.abs(s.net) < 5 ? 'settled' : (s.net > 0 ? '+' : '−') + rs(Math.abs(s.net))}</span></div>)}</div>
        </section>
        <section className="card"><h3 style={{ marginBottom: 6 }}>Trips since last settle-up</h3>
          {d.recent.length ? <div className="scroll"><table className="tt"><thead><tr><th>Day</th><th>Paid by</th><th style={{ textAlign: 'right' }}>Total</th><th style={{ textAlign: 'right' }}>Your share</th></tr></thead>
            <tbody>{d.recent.map((t, i) => <tr key={i}><td className="mono sub">{fmt(t.day)}</td><td>{t.payer}</td><td className="mono" style={{ textAlign: 'right' }}>{rs(t.total)}</td>
              <td className="mono" style={{ textAlign: 'right' }}>{t.my_share != null ? rs(t.my_share) : <span className="sub">didn’t go</span>}</td></tr>)}</tbody></table></div>
            : <p className="hint">No fares entered since the last settle-up.</p>}
          <div className="row" style={{ marginTop: 12 }}><button className="btn" onClick={all}>Everyone settled up</button></div></section>
      </div>
    </>
  )
}
