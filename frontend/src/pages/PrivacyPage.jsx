import { Link } from 'react-router-dom'
import { useMeta } from '../meta'

export default function PrivacyPage({ standalone }) {
  const meta = useMeta()
  return (
    <div className="card stack" style={{ maxWidth: 760, margin: standalone ? '24px auto' : 0 }}>
      <h2>Privacy notice</h2>
      <p className="hint">Version {meta?.consent_version || '2026-12'}</p>
      <h3>Who we are</h3>
      <p>CommuteCircle is a student project at BIC Karachi (273/1/A Main Ibrahim Hyderi Road, Korangi Creek) run with Student Affairs. It introduces classmates who travel the same way. BIC doesn't arrange transport: you and your families decide how to travel.</p>
      <h3>What we collect and why</h3>
      <ul>
        <li><b>Account:</b> name, BIC email, mobile number, gender, programme and year. Student Affairs uses these to check you are a BIC student; your circle sees your name, programme and, once everyone accepts, your number.</li>
        <li><b>Trip:</b> your <i>area</i> (never your address), campus days and times, ways you’d travel, and whether you drive. Used only to suggest circles, plan trips and the rota.</li>
        <li><b>Trips and money:</b> daily check-ins (travelled, not going, didn’t turn up) and the fares you choose to enter, to show balances, savings and fare guides.</li>
        <li><b>Feedback and reports:</b> private 👍/👎 feedback and safety reports. Positive feedback adds up to badges; negative feedback and reports are seen only by Student Affairs.</li>
      </ul>
      <h3>Who can see it</h3>
      <ul>
        <li>Students shown a suggested circle see first name, initial, programme and area only.</li>
        <li>Phone numbers are shared only when everyone in the circle accepts, and hidden again if you leave.</li>
        <li>Student Affairs sees totals by default and opens individual records only to approve sign-ups or handle a report.</li>
      </ul>
      <h3>Research (optional)</h3>
      <p>If you opt in, your trip data may be used in the project’s evaluation of matching methods. It is <b>pseudonymised</b>: no names, emails or phone numbers leave the system, and results are reported only in aggregate. You can opt out any time on your Account page.</p>
      <h3>Your rights</h3>
      <ul><li>Download everything we hold about you from your Account page.</li><li>Correct your details at any time.</li>
        <li>Delete your account permanently. Safety reports are kept but no longer linked to you.</li></ul>
      <h3>Retention</h3>
      <p>Data is kept for the project’s duration (academic year 2026–27) and deleted afterwards, except anonymous totals.</p>
      <h3>Code of conduct</h3>
      <p>Be on time, be respectful, only mark trips truthfully, pay your share, and drive only with a valid licence. Breaking these can lead to suspension.</p>
      {standalone && <p><Link to="/">Back</Link></p>}
    </div>
  )
}
