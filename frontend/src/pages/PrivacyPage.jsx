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
        <li><b>Feedback, ratings and reports:</b> private 👍/👎 feedback, 1–5 star ratings after trips, and safety reports. Ratings and show-ups make up a trust score (0–5) shown to your circle; individual ratings, negative feedback and reports are seen only by Student Affairs.</li>
        <li><b>Safety:</b> an optional emergency contact (name and mobile). If you press SOS, we record the time, your circle and route areas and any message, alert Student Affairs, and (if WhatsApp is set up) message your emergency contact and campus security.</li>
        <li><b>Email:</b> we email one-time codes to verify your BIC address and to reset your password.</li>
        <li><b>WhatsApp (optional):</b> if you turn on WhatsApp reminders, your mobile number and short trip messages are sent through Meta’s WhatsApp Business service, and your replies (1, 2, an amount) update your trips. Reply STOP or switch it off on your Account page any time.</li>
        <li><b>Surveys (optional):</b> usability (SUS), safety and monthly spending questions used to evaluate the project.</li>
        <li><b>Message log:</b> a record of the emails and WhatsApp messages we send you, kept for Student Affairs to check delivery.</li>
      </ul>
      <h3>Services we use</h3>
      <ul><li>Render (hosting) and Neon (database), Brevo (email) and Meta WhatsApp Business (optional messages). Road distances come from OpenStreetMap data and are calculated between area centre points only; no personal data is sent for routing.</li></ul>
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
      <h3>What changed in version 2026-12b</h3>
      <p>Added star ratings and trust scores, SOS alerts and emergency contacts, email codes, optional WhatsApp messages, evaluation surveys and the message log.</p>
      <h3>Code of conduct</h3>
      <p>Be on time, be respectful, only mark trips truthfully, pay your share, and drive only with a valid licence. Breaking these can lead to suspension.</p>
      {standalone && <p><Link to="/">Back</Link></p>}
    </div>
  )
}
