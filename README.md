# CommuteCircle

Carpool matching for BIC Karachi students. Students enter their area, timetable and
whether they can drive; the system forms small, compatible **circles** (2–5 people),
shares a fair driving rota and splits fuel costs. The transport office runs matching,
compares algorithms and handles safety reports.

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

## Tests

```bash
cd backend && python -m pytest -q     # 47 tests: matching engine + API journeys
```

## Docs

- [docs/TECHNICAL.md](docs/TECHNICAL.md): architecture, data model, algorithms, API, security, testing
- [docs/screenshots/](docs/screenshots/): UI walkthrough
