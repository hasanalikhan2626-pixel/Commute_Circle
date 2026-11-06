# CommuteCircle: Technical Documentation (MVP, Week 9)

_Version 1.1. Campus: BIC Karachi, 273/1/A Main Ibrahim Hyderi Road, Korangi Creek, Karachi 75190._

## 1. Overview

CommuteCircle is a web application that groups BIC Karachi students into carpool
"circles". It has two user types:

* **Students** register with their BIC email, describe their commute (area, timetable,
  car/seats, gender preference), accept or decline proposed circles, see contacts,
  the driving rota and cost split once a circle is confirmed, and can report members.
* **Transport office (admin)** compares matching algorithms on the live pool, runs
  matching, monitors circles, dissolves circles, reviews reports and suspends accounts.

## 2. Architecture

```
React SPA (Vite)  ──HTTPS/JSON──▶  FastAPI  ──SQLAlchemy──▶  SQLite (dev) / PostgreSQL (prod)
  frontend/src                     backend/app
                                     ├─ routers/    HTTP layer, auth, validation
                                     ├─ services/   circle lifecycle, rota, costs
                                     └─ matching/   pure algorithms + evaluation
```

* **Layering.** Routers handle HTTP and permissions only. Services hold business
  rules. `matching/` is pure Python with no database access, so the algorithms can be
  unit-tested and benchmarked in isolation (the research component).
* **Deployment.** In production, FastAPI serves the built frontend from `frontend/dist`,
  so the whole app is one process behind one origin (no CORS needed).
* **Configuration** comes from `CC_*` environment variables (`backend/app/config.py`):

  | Variable | Default | Notes |
  |---|---|---|
  | `CC_ENV` | development | `production` turns on the safety checks below |
  | `CC_SECRET_KEY` | dev value | ≥ 32 random characters in production |
  | `CC_DATABASE_URL` | SQLite file | PostgreSQL required in production; `postgres://` URLs accepted |
  | `CC_EMAIL_DOMAINS` | bic.edu.pk | Only these domains can register |
  | `CC_CAMPUS_LAT/LNG` | 24.7990, 67.1330 | Approximate (~1 km) position of Ibrahim Hyderi Road, Korangi Creek; refine with a map pin |
  | `CC_FUEL_PRICE_PKR` | 352.59 | Petrol price per litre |
  | `CC_FUEL_KM_PER_LITRE` | 12 | Average car efficiency |

  In production the app **refuses to start** with a weak secret key, SQLite, or no email
  domain, hides the Swagger docs, and the seed script refuses to run (it would wipe real data).

## 3. Data model

| Table | Purpose | Key fields |
|---|---|---|
| `users` | Accounts | email (unique), password_hash (bcrypt), role, phone (normalised +92…), is_active, consented_at, consent_version, research_consent |
| `profiles` | Commute preferences, **only edited by the student** | area, pickup_landmark, gender, same_gender_only, has_car, seats, schedule (JSON per day), seeking |
| `circles` | A carpool group | status (proposed/active/dissolved), algorithm, score, dissolved_reason |
| `circle_members` | Membership | is_driver, status (pending/accepted/declined/left) |
| `rota_entries` | Who drives which day | day, driver_id, arrive |
| `driver_unavailability` | Days a driver can't drive | circle_id, user_id, day |
| `declined_pairs` | Pairs never to propose again | user_id, other_id |
| `reports` | Safety reports | reason, details, status, admin_note; reporter/reported set to NULL if an account is deleted |
| `match_runs` | Audit log and research data for every run | algorithm, pool_size, metrics (JSON) |

**Privacy by design.** No home address or GPS coordinates are stored. Students choose
an *area*; distances use approximate area centroids (`app/areas.py`). Phone numbers and
pickup landmarks are hidden until **every** member has accepted the circle.

## 4. Circle lifecycle

```
             run_matching
 (seeking) ───────────────▶ PROPOSED ──all accept──▶ ACTIVE
                               │                       │
                 decline ──────┤                leave / suspend / admin
                               ▼                       ▼
              still feasible? ─no──▶ DISSOLVED ◀── still feasible? no
                     │ yes
                     └─ stays PROPOSED / ACTIVE (rota rebuilt)
```

* A decline records `declined_pairs` so the same pairing is not proposed again.
* After any membership change the circle is re-checked against every hard constraint
  (`services/circles.py::_settle`). Members whose circle dissolves return to the pool.
* Editing a profile never dissolves a circle automatically; the student is warned if
  the change breaks it.

## 5. Matching engine (`backend/app/matching/`)

### 5.1 Hard constraints (`compat.py::feasible`)
1. 2 to 5 members, with at least one driver; size ≤ largest car's seats + 1.
2. Same-gender preference: if any member requires it, all members share one disclosed gender.
3. At least 2 days a week when **all** members are on campus and arrivals fall within 30 minutes.
4. The best driver's detour to collect everyone is ≤ 6 km (straight line).
5. No previously declined pair.

### 5.2 Soft score
For each pair: `0.6 × schedule overlap (shared days / union of days) + 0.4 × proximity`,
where proximity falls linearly from 1 to 0 over 8 km. A circle's score is the mean over its pairs.

### 5.3 Algorithms compared
| ID | Approach |
|---|---|
| `greedy` (baseline) | Drivers in order of seats; each takes the nearest riders that keep the circle feasible. |
| `cluster` | k-means++ on locations (k = ⌈n/4⌉), then split each cluster into feasible circles. |
| `compatibility` (proposed) | Build the compatibility graph; seed circles from the **most constrained** drivers; grow by highest average pairwise score, preferring riders over spare drivers; repair pass places leftovers into circles with spare seats, then forms new circles from what remains. |

All three are deterministic for a given seed.

### 5.4 Metrics (`evaluate.py`)
Match rate, number and size of circles, mean compatibility, mean detour, mean shared
days, and estimated weekly km, fuel (PKR) and CO₂ saved compared with everyone driving alone.

### 5.5 Preliminary results (synthetic data)

`python -m app.benchmark` generates 5 independent synthetic pools at each size (campus
at Korangi Creek, south-east areas weighted as most common) and reports mean ± SD.
The raw output is in `docs/benchmark-synthetic.csv`.

| Pool | Algorithm | Match rate | Avg compatibility | Avg detour km | Fuel saved PKR/wk | Runtime ms |
|---|---|---|---|---|---|---|
| 60 | Greedy | 64.7% ± 6.6 | 0.674 ± 0.029 | 2.86 ± 0.57 | 30,212 ± 8,446 | 5 |
| 60 | k-means | 45.3% ± 4.3 | **0.728** ± 0.044 | **2.19** ± 0.60 | 22,674 ± 5,843 | 9 |
| 60 | Compatibility | **66.0%** ± 8.0 | 0.653 ± 0.036 | 3.30 ± 0.37 | **31,943** ± 7,990 | 13 |
| 200 | Greedy | **83.4%** ± 2.2 | 0.727 ± 0.020 | 2.94 ± 0.20 | 148,218 ± 9,447 | 32 |
| 200 | k-means | 74.0% ± 4.7 | **0.762** ± 0.019 | **1.62** ± 0.36 | 143,981 ± 17,227 | 253 |
| 200 | Compatibility | 79.3% ± 2.8 | 0.726 ± 0.025 | 2.78 ± 0.06 | **153,971** ± 19,031 | 127 |

**Interpretation.**
* The proposed compatibility method **does not yet beat the greedy baseline** on match
  rate. At 60 students the difference (66.0% vs 64.7%) is well inside one standard
  deviation. At 200 students greedy is ahead by about 4 points.
* k-means produces the tightest, most compatible circles with the shortest detours,
  but leaves the most students unmatched, because it groups by geography before
  looking at timetables.
* There is a clear trade-off between *coverage* (match rate) and *quality*
  (compatibility, detour). No method wins on both.
* These are synthetic pools. The final evaluation must be re-run on the real,
  consented student data via the research export (Section 9a).

**Next steps for the research component:** a local-search improvement pass for the
compatibility method (move or swap students between circles while the objective
improves); an exact integer-programming solution on small pools as an upper bound;
and a significance test (paired, across datasets) before claiming any method is better.

## 6. Driving rota (`services/rota.py`)
For each shared day in the next 14 days, the rota picks the available driver with the
fewest turns so far in that circle, breaking ties by who drove least recently. Past
turns count, so the balance holds across weeks. A driver can mark a day "can't drive",
which reassigns it; if no driver is free, the day shows "No driver: arrange together".

## 7. Cost model (`services/costs.py`)
Trip km = (driver's distance to campus + detour) × 1.3 road factor. The trip cost is
split equally between members. Monthly cost = per-trip share × shared days × 2 × 4.33.
Each member is compared with driving their own route alone. Fuel price and
efficiency are configurable; **update `CC_FUEL_PRICE_PKR` to the current OGRA price.**

## 8. API summary
Interactive OpenAPI docs: `http://localhost:8000/docs`.

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | /api/auth/register, /api/auth/login | public | Account, JWT |
| GET/PATCH | /api/auth/me | user | Account details |
| GET | /api/meta | public | Areas, days, campus, report reasons |
| GET/PUT | /api/profile | student | Commute profile |
| GET | /api/circles/mine, /api/circles/{id} | member | Circle, rota, costs |
| POST | /api/circles/{id}/respond, /leave, /unavailable | member | Lifecycle actions |
| POST | /api/reports | member | Report a circle-mate |
| GET | /api/admin/stats, /runs, /circles, /reports, /users | admin | Monitoring |
| POST | /api/admin/compare | admin | Dry-run all algorithms |
| POST | /api/admin/match | admin | Create circles |
| POST | /api/admin/circles/{id}/dissolve | admin | Dissolve |
| PATCH | /api/admin/reports/{id}, /api/admin/users/{id} | admin | Resolve report, suspend |

## 9a. Personal data, consent and research use

Real student data is collected, so the system implements:

| Requirement | Implementation |
|---|---|
| Informed consent | Registration requires agreeing to the privacy notice (`/privacy`); time and notice version are stored |
| Separate research consent | Optional checkbox at sign-up, changeable any time on the Account page |
| Data minimisation | Area instead of address; no GPS; landmark and phone optional |
| Right of access | Account > *Download my data* (`GET /api/auth/me/export`, JSON) |
| Right to erasure | Account > *Delete my account* (password confirmed): leaves the circle, deletes all personal records; safety reports are kept but unlinked |
| Pseudonymised research data | `GET /api/admin/research-export` (CSV): **only** students who opted in; no name, email, phone or landmark; IDs are HMAC-SHA256 hashes keyed by the server secret |

## 9. Security
* Passwords hashed with bcrypt; JWT (HS256) bearer tokens expire after 12 hours.
* Registration can be restricted to campus email domains (`CC_EMAIL_DOMAINS`).
* Login throttling: 5 failed attempts per email in 15 minutes returns HTTP 429.
* Authorisation: non-members get **404** for circles (existence is not leaked); students
  can only report people they have shared a circle with; admin routes check the role.
* All input is validated with Pydantic: times, day names, areas, seats, and phone format.
* Suspending a user signs them out and removes them from their circle immediately.
* Security headers on every response: `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, and HSTS in production. The container runs as a non-root user.
* Admin accounts are created with `python -m app.create_admin` (password ≥ 12 characters),
  never through the public sign-up.

## 10. Fixes to the original prototype
| Prototype issue | Resolution | Regression test |
|---|---|---|
| Re-running matching overwrote profiles and circles | Matching only reads profiles and only considers unmatched, seeking students | `test_rematching_does_not_touch_profiles_or_circles` |
| Rota always assigned the first driver | Fair rotation using turn history | `test_rota_is_fair_between_drivers` |
| Inconsistent phone formats | Normalised to +923XXXXXXXXX | `test_phone_normalised` |

## 11. Testing
`backend/tests/` holds 54 automated tests. They run on **both SQLite and PostgreSQL 16**
(GitHub Actions runs both on every push):
* **Matching engine (34):** every algorithm is checked over 5 random pools of 50
  students. No circle may break a hard constraint, no student may appear twice, and
  every student must be accounted for. The tests also cover determinism and edge
  cases (empty pool, lone driver).
* **API journeys (13):** registration validation, throttling, the full accept flow,
  decline handling, a driver leaving, privacy, rota fairness, reassignment when a
  driver is unavailable, suspension, reports, and the dry-run compare.
* **Personal data (7):** consent is required, the research toggle, data export,
  account deletion (circle survives, report is unlinked), the research CSV
  (opted-in students only, no identifiers), database URL handling, and production
  configuration guards.

Two browser walkthroughs ran in Chromium with no console errors: (1) the admin
compares algorithms and runs matching, then every member accepts; (2) on the
production configuration with PostgreSQL, a student signs up with consent, sets up a
Korangi Creek profile, downloads their data, the admin downloads the research CSV, and
the student deletes their account. Screenshots are in `docs/screenshots/`.

## 12. Known limitations and next steps (to the final build)
* Distances use straight-line distance between area centroids. Next step: a road-distance
  API (e.g. OSRM) and finer pickup zones.
* The login throttle is held in memory per process; use Redis for multi-worker deploys.
* No email verification or notifications yet. Next steps: an email OTP at registration,
  then email or WhatsApp alerts when a circle is proposed.
* No database migrations yet. Add Alembic before the schema changes in production.
* Campus coordinates are approximate (~1 km); confirm them with a map pin.
* The proposed algorithm needs the improvements listed in Section 5.5.
* The Docker image could not be built in the development sandbox (Docker Hub rate
  limit). It builds on Render and GitHub Actions; check the first deploy log.
