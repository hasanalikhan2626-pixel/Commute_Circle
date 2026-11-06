import { Link } from 'react-router-dom'
import { Card } from '../components/ui'

// Keep in step with CC consent_version (backend/app/config.py) when this text changes.
export const PRIVACY_VERSION = '2026-11'

export default function PrivacyPage({ standalone }) {
  return (
    <div className={standalone ? 'content' : ''}>
      <Card title="Privacy notice">
        <p className="muted small">Version {PRIVACY_VERSION}</p>
        <h3>Who we are</h3>
        <p>CommuteCircle is a student project at BIC Karachi (273/1/A Main Ibrahim Hyderi Road, Korangi Creek) run with the campus transport office. It helps students form carpool groups.</p>
        <h3>What we collect and why</h3>
        <ul>
          <li><strong>Account:</strong> name, BIC email, optional mobile number. Used to sign you in and, once your circle is confirmed, to let members contact each other.</li>
          <li><strong>Commute:</strong> your <em>area</em> (not your address), optional pickup landmark, timetable, car and seats, gender and same-gender preference. Used only to form circles, the driving rota and cost split.</li>
          <li><strong>Safety reports</strong> you make or that are made about you, reviewed only by the transport office.</li>
        </ul>
        <h3>Who can see it</h3>
        <ul>
          <li>Students in a <em>proposed</em> circle see each other's name and area only.</li>
          <li>Your phone number and pickup landmark are shown only after every member has accepted.</li>
          <li>The transport office can see account and circle details to run the service and handle reports.</li>
        </ul>
        <h3>Research (optional)</h3>
        <p>If you opt in, your commute data may be used in the project's evaluation of matching algorithms. Research data is <strong>pseudonymised</strong>: no names, emails, phone numbers or landmarks leave the system, and results are reported only in aggregate. You can opt out any time on your Account page without affecting your use of the app.</p>
        <h3>Your rights</h3>
        <ul>
          <li>Download everything we hold about you from your Account page.</li>
          <li>Correct your details at any time.</li>
          <li>Delete your account permanently. Safety reports are kept but no longer linked to you.</li>
        </ul>
        <h3>Retention</h3>
        <p>Data is kept for the duration of the project (academic year 2026–27) and deleted afterwards, except anonymous aggregate results.</p>
        {standalone && <p><Link to="/">Back</Link></p>}
      </Card>
    </div>
  )
}
