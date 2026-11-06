# CommuteCircle: Technical Documentation (MVP, Week 9)

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
  `CC_SECRET_KEY`, `CC_DATABASE_URL`, `CC_EMAIL_DOMAINS`, `CC_CAMPUS_LAT/LNG`,
  `CC_FUEL_PRICE_PKR`, `CC_FUEL_KM_PER_LITRE`, `CC_CORS_ORIGINS`.

## 3. Data model

| Table | Purpose | Key fields |
|---|---|---|
| `users` | Accounts | email (unique), password_hash (bcrypt), role, phone (normalised +92…), is_active |
| `profiles` | Commute preferences, **only edited by the student** | area, pickup_landmark, gender, same_gender_only, has_car, seats, schedule (JSON per day), seeking |
| `circles` | A carpool group | status (proposed/active/dissolved), algorithm, score, dissolved_reason |
| `circle_members` | Membership | is_driver, status (pending/accepted/declined/left) |
| `rota_entries` | Who drives which day | day, driver_id, arrive |
| `driver_unavailability` | Days a driver can't drive | circle_id, user_id, day |
| `declined_pairs` | Pairs never to propose again | user_id, other_id |
| `reports` | Safety reports | reason, details, status, admin_note |
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

### 5.5 Preliminary results (60 synthetic students, seed 0)

| Algorithm | Match rate | Circles | Avg compatibility | Avg detour km | Fuel saved / week |
|---|---|---|---|---|---|
| Greedy | 65.0% | 11 | 0.716 | 3.22 | PKR 21,929 |
| k-means | 43.3% | 7 | **0.782** | **2.03** | PKR 16,819 |
| Compatibility | **68.3%** | 13 | 0.723 | 2.72 | PKR 21,211 |

The proposed method places the most students. k-means makes the tightest circles but
leaves many students unmatched, because grouping by geography alone ignores
timetables. These numbers come from synthetic data and must be re-run on real
(consented) student data for the final evaluation.

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

## 9. Security
* Passwords hashed with bcrypt; JWT (HS256) bearer tokens expire after 12 hours.
* Registration can be restricted to campus email domains (`CC_EMAIL_DOMAINS`).
* Login throttling: 5 failed attempts per email in 15 minutes returns HTTP 429.
* Authorisation: non-members get **404** for circles (existence is not leaked); students
  can only report people they have shared a circle with; admin routes check the role.
* All input is validated with Pydantic: times, day names, areas, seats, and phone format.
* Suspending a user signs them out and removes them from their circle immediately.

## 10. Fixes to the original prototype
| Prototype issue | Resolution | Regression test |
|---|---|---|
| Re-running matching overwrote profiles and circles | Matching only reads profiles and only considers unmatched, seeking students | `test_rematching_does_not_touch_profiles_or_circles` |
| Rota always assigned the first driver | Fair rotation using turn history | `test_rota_is_fair_between_drivers` |
| Inconsistent phone formats | Normalised to +923XXXXXXXXX | `test_phone_normalised` |

## 11. Testing
`backend/tests/` holds 47 automated tests:
* **Matching engine (34):** every algorithm is checked over 5 random pools of 50
  students. No circle may break a hard constraint, no student may appear twice, and
  every student must be accounted for. The tests also cover determinism and edge
  cases (empty pool, lone driver).
* **API journeys (13):** registration validation, throttling, the full accept flow,
  decline handling, a driver leaving, privacy, rota fairness, reassignment when a
  driver is unavailable, suspension, reports, and the dry-run compare.

A browser walkthrough (admin compares, then runs matching, then every member accepts)
ran in Chromium with no console errors. Screenshots are in `docs/screenshots/`.

## 12. Known limitations and next steps (to the final build)
* Distances use straight-line distance between area centroids. Next step: a road-distance
  API (e.g. OSRM) and finer pickup zones.
* The login throttle is held in memory per process; use Redis for multi-worker deploys.
* No email verification or notifications yet. Next steps: an email OTP at registration,
  then email or WhatsApp alerts when a circle is proposed.
* No database migrations yet. Add Alembic before the schema changes in production.
* Campus coordinates, fuel price and the email domain are placeholders to confirm.
