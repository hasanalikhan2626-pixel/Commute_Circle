# CommuteCircle

Carpool matching for BIC Karachi students. Students enter their area, timetable and
whether they can drive; the system forms small, compatible **circles** (2–5 people),
shares a fair driving rota and splits fuel costs. The transport office runs matching,
compares algorithms and handles safety reports.

**Live:** https://commutecircle.onrender.com (free hosting; the first visit after a quiet spell can take up to a minute while it wakes)

## Quick start

Requires Python 3.11+ and Node 18+.

```bash
# Backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python -m app.seed               # 60 synthetic students + admin
uvicorn app.main:app --reload    # http://localhost:8000  (API docs at /docs)

# Frontend (second terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

For a single-server demo, run `npm run build` in `frontend/` and open
http://localhost:8000 (FastAPI serves the built app).

**Demo logins** (synthetic data):

| Role | Email | Password |
|---|---|---|
| Transport office | admin@bic.edu.pk | admin12345 |
| Student | student1@bic.edu.pk … student60@bic.edu.pk | student123 |

## Tests and benchmark

```bash
cd backend
python -m pytest -q                   # 54 tests (SQLite)
CC_DATABASE_URL=postgres://user:pass@localhost/db python -m pytest -q   # same suite on PostgreSQL
python -m app.benchmark               # compare algorithms over 5 synthetic datasets
```

## Production

Real student data is handled under consent (see the in-app privacy notice). Deploy with
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (Render + Neon, free). Create admins with
`python -m app.create_admin`; the seed script refuses to run in production.

## Docs

- [docs/TECHNICAL.md](docs/TECHNICAL.md): architecture, data model, algorithms, API, security, testing
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): free hosting guide
- [docs/benchmark-synthetic.csv](docs/benchmark-synthetic.csv): algorithm results
- [docs/screenshots/](docs/screenshots/): UI walkthrough
