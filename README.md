# CommuteCircle

Travel to campus with classmates on your route · BIC Karachi.

Students who live near each other, or on each other's way, and come to campus at the same
times are matched into **circles** of 2–4. They agree how to travel (shared ride-hailing,
rickshaw, motorbike pillion, a classmate drives, a family driver or a parent drop), check in
each day (in the app or on WhatsApp), split fares fairly, rate rides and take fair turns
driving, with an SOS button always to hand. Student Affairs approves sign-ups, watches circle
health, handles reports and SOS alerts, and tracks the proposal's evaluation targets. The
design follows the original prototype (`CommuteCircle_Prototype.html`); the matching engine
implements the proposal's DBSCAN + Kuhn–Munkres and Genetic Algorithm methods with real road
times (OSRM). Installable on phones (PWA).

**Live:** https://commutecircle.onrender.com (free hosting; the first visit after a quiet spell can take up to a minute while it wakes)

## Quick start

Requires Python 3.11+ and Node 18+.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python -m app.seed               # the prototype's 71 students, 16 circles, 4 weeks of trips
uvicorn app.main:app --reload    # API on http://localhost:8000 (docs at /docs)

cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

For a single-server demo, run `npm run build` in `frontend/` and open http://localhost:8000.

**Demo logins** (fictional data):

| Who | Email | Password |
|---|---|---|
| Student Affairs | admin@bic.edu.pk | admin12345 |
| Student in a circle | ayesha.khan@bic.edu.pk | student123 |
| Student without a circle | ali.hassan@bic.edu.pk | student123 |

Every student is `first.last@bic.edu.pk` with the password `student123`.

## Tests and research benchmark

```bash
cd backend
python -m pytest -q                       # 87 tests (SQLite)
CC_DATABASE_URL=postgres://user:pass@localhost/db python -m pytest -q   # same suite on PostgreSQL
python -m app.benchmark                   # compare the three matching algorithms
python -m app.benchmark --prototype       # ... on the prototype's students
python -m app.privacy_sim                 # RQ2: exact vs landmark vs area-centre pickups
```

## Production

Deploy with [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (Render + Neon, free). Schema
changes run automatically on start-up (Alembic). The first admin comes from
`CC_ADMIN_EMAIL` / `CC_ADMIN_PASSWORD`; the seed script refuses to run in production.

## Docs

- [docs/TECHNICAL.md](docs/TECHNICAL.md): architecture, data model, matching, trips and money, API, security, testing
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): free hosting guide and optional services
- [docs/WHATSAPP.md](docs/WHATSAPP.md): WhatsApp Cloud API setup and message templates
- [docs/privacy-sim.csv](docs/privacy-sim.csv): RQ2 privacy simulation results
- [docs/benchmark-synthetic.csv](docs/benchmark-synthetic.csv): algorithm results
- [docs/screenshots/](docs/screenshots/): every screen
