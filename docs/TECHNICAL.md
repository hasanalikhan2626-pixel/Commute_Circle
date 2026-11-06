# CommuteCircle: Technical Documentation

_Version 2.0 (December 2026). Rebuilt to match the CommuteCircle prototype
(`CommuteCircle_Prototype.html`). Campus: BIC Karachi, 273/1/A Main Ibrahim Hyderi Road,
Korangi Creek, Karachi 75190 (24.8086702, 67.1217257)._

## 1. Overview

CommuteCircle introduces BIC students who live near each other, or on each other's way,
and come to campus at the same times, so they can travel together. BIC doesn't arrange
transport: the app only introduces classmates, and they decide how to travel.

| Students (prototype tabs) | Student Affairs (prototype tabs) |
|---|---|
| **Find my circle**: three questions, then up to three circle options with a 0–100 fit score and a map | **Usage**: totals, trips per day, demand map, gaps by area |
| **Today**: one-tap “Reached campus?”, fare entry, “Not going tomorrow”, one-day seat in another circle, streaks | **Fares**: what students actually pay, by area and way of travelling |
| **My circle**: members, show-up rate and badges, weekly plan, travel mode, driving rota, private feedback, re-match, report or leave | **Circle health**: completion, no-shows and negative feedback, with “Check in” flags |
| **Money**: who paid, who owes, settle-up | **Approvals**: checking each sign-up against the student record |
| **My savings**: alone vs your share, fare guide | **Reports**: decisions, suspension, private negative feedback |
| | **Matching lab** (research) and **Students** |

## 2. What changed from the prototype

The prototype was a single HTML page with dummy data in memory. Version 2 keeps its
screens, wording, styles and matching method, and adds what a real service needs.

| Prototype | Version 2 |
|---|---|
| “Testing as” switcher, data resets on reload | Real accounts (BIC email + password), PostgreSQL database |
| Approvals list with dummy sign-ups | Every new account is *pending* until Student Affairs approves it |
| Accepting a circle = everyone accepts at once | The others are asked; numbers are shared only when all accept; proposals lapse after 3 days |
| “Find my circle” overwrote per-day times with one arrive/leave time | Per-day times are kept (“Different times on some days”) |
| Re-match removed people from other circles immediately | The old circle is left only once the new one is confirmed |
| Rota assigned turns by position | Fair rota from turn history, “Can’t do it” / “I’ll take it” |
| Seat request accepted automatically | The host circle accepts or declines |
| A circle could form with no travel method in common | A common way of travelling is required (and a car with enough seats for “Classmate drives”) |
| WhatsApp group shown as “Created” | Shown as a preview (“Coming soon”): no group is actually created |
| Detour only lowered the fit score | Proposal hard rule: no rider's detour over 12 minutes |
| Circle fit averaged one direction per pair | Both directions, so a circle's score doesn't depend on listing order |
| Auto-rickshaw circles of 4 | Rickshaw carries 3 passengers (proposal Appendix C) |

## 3. Architecture

```
React SPA (Vite)  ──JSON over HTTPS──▶  FastAPI  ──SQLAlchemy──▶  PostgreSQL (Neon) / SQLite (dev)
frontend/src                            backend/app
  pages/          one file per tab        routers/     HTTP, auth, validation (student.py, admin.py)
  components/Map  the prototype map       services/    circles, trips & money, rota, clock
  styles.css      the prototype CSS       matching/    pure algorithms, fit score, fares, evaluation
                                          migrate.py   Alembic migrations on start-up
```

* **Pure matching core.** `matching/` has no database access, so the algorithms are
  unit-tested and benchmarked on their own (`python -m app.benchmark`).
* **Single deployable.** FastAPI serves the built React app from `frontend/dist`
  (the Dockerfile builds both). Render runs the container; Neon holds the database.
* **Karachi time.** “Today” is the date in Asia/Karachi (`services/clock.py`), not the
  server's time zone. Weekends have no trips.
* **Configuration** (`backend/app/config.py`, environment variables):

  | Variable | Default | Notes |
  |---|---|---|
  | `CC_ENV` | development | `production` enables the safety checks below |
  | `CC_SECRET_KEY` | dev value | ≥ 32 random characters in production |
  | `CC_DATABASE_URL` | SQLite file | PostgreSQL in production; `postgres://` accepted |
  | `CC_EMAIL_DOMAINS` | bic.edu.pk | Only these can register |
  | `CC_CAMPUS_LAT/LNG` | 24.8086702, 67.1217257 | Campus map pin |
  | `CC_FUEL_PRICE_PKR` | 352.59 | Used for “Classmate drives” fuel sharing |
  | `CC_ADMIN_EMAIL` / `CC_ADMIN_PASSWORD` | – | Creates the first admin on start-up (hosts with no shell) |
  | `CC_SEED_DEMO` | – | `true` loads the prototype's demo data into an *empty*, non-production database |
  | `CC_AVG_SPEED_KMH` | 22 | Average speed used to turn detour km into minutes |
  | `CC_MAX_DETOUR_MIN` | 12 | Hard limit on any rider's detour |
  | `CC_TODAY` | – | Development only: pin “today” (YYYY-MM-DD), e.g. for a weekend demo |

  In production the app refuses to start with a weak secret, SQLite or no email domain;
  the API docs are hidden and the seed script refuses to run.

## 4. Data model

| Table | Purpose |
|---|---|
| `users` | Account, role, status (pending / approved / rejected / suspended), consent version and time, research consent |
| `profiles` | Gender, programme, year, area, women-only, ways of travelling, car and seats, weekly timetable (per-day arrive/leave) |
| `circles`, `circle_members` | Circle (proposed / active / dissolved), way of travelling, fit, who found it; members in order |
| `trips`, `trip_members` | One circle trip per day: travelled / not going / didn't turn up, who confirmed, fare total and payer; guests from other circles |
| `absences` | “Not going tomorrow” |
| `rota_entries`, `rota_unavailable` | Who drives or drops each day; days someone can't |
| `settlements` | “I've paid” / “Mark as received” |
| `feedback` | Private 👍/👎 with a tag |
| `seat_requests` | One-day seats in another circle |
| `declined_pairs` | Pairs never suggested together again |
| `reports`, `match_runs` | Safety reports; research batch runs |

Schema changes go through **Alembic** (`backend/migrations`). On start-up `app/migrate.py`
creates or upgrades the schema. A database still on the v1 layout is rebuilt only if it
holds **no student accounts** (admin logins are carried across); otherwise the app refuses
to start rather than risk data.

**Privacy by design.** Students choose an area, never an address. Suggested circles show
first name, initial, programme and area. Phone numbers appear only once every member has
accepted. Student Affairs screens show totals; names appear only for approvals and reports.

## 5. Matching engine (prototype fit score + proposal optimisation methods)

### 5.1 Fit score (`matching/compat.py::pair_fit`)
For student A looking at classmate B, 0–100 (ported from the prototype):

| Part | Points | Rule |
|---|---|---|
| Route | 40 | 0 % detour → 40, falling to 0 at 35 % extra distance (better of the two pickup orders) |
| Nearby | 20 | ≤ 1.5 km apart → 20, falling to 0 at 8 km |
| Timetable | 30 | For each of A's days: arrival within 15 min = 1, within 30 = 0.5 (70 %); leaving time likewise (30 %) |
| Travel | 10 | At least one way of travelling in common |

“On your way” = detour ≤ 12 %. A circle's fit is the average over every pair **in both
directions**, so it doesn't depend on who is listed first (the prototype averaged one
direction per pair, which made the score order-dependent). 75+ “Great fit”, 60+ “Good fit”,
otherwise “Fair fit”. Minimum to be suggested: **45**.

For a whole pool, `Scorer` computes every pair's fit at once with NumPy (identical results
to `pair_fit`, checked by a test on ~19,000 pairs), which keeps every algorithm under half a
second on 500 students.

### 5.2 Hard rules (`Scorer.feasible`, proposal §14.7 stage 1)
2–4 members; women-only students only with women; every pair scores ≥ 35 with at least
one good day; at least one weekday when everyone arrives within 20 minutes of the circle's
founder; a way of travelling everyone accepts that can carry the group (auto-rickshaw 3
passengers, others 4; “Classmate drives” needs a car with enough seats); no previously
declined pair; and **no rider's detour over 12 minutes** (proposal §13). A set of students is
a valid circle if *any* of them can be its founder (`Scorer.arrange`).

**Detour minutes** = extra road km a rider travels compared with going straight to campus
(pickups furthest-first; road km = straight line × 1.35) ÷ an assumed average speed of
22 km/h (`CC_AVG_SPEED_KMH`). This is an estimate until a routing API (OSRM / OpenRouteService)
provides real travel times.

### 5.3 Find my circle (`algorithms.py::build_for`, `options_for`)
Start from the student; repeatedly add the classmate who maximises
`0.6 × (weakest pair score in the circle) + 0.4 × (fit with the student)` while the circle
stays feasible, up to 4. Options: the best circle overall, plus circles seeded with each of
the student's six best matches; duplicates removed; ranked by `fit + 6 × size`; top three.
Accepting re-checks everything, because classmates may have been matched meanwhile.
One search takes **0.04 s on average (worst 0.10 s) with 500 students**, against the
proposal's ≤ 1.5 s target.

### 5.4 Algorithms compared (RQ1)
| Algorithm | Idea |
|---|---|
| **Greedy** (baseline) | In sign-up order, each student takes the nearest classmates that keep the circle feasible |
| **k-means** | Cluster by location (k = ⌈n/4⌉), then form circles inside each cluster |
| **Compatibility** | The Find my circle method applied to everyone, hardest-to-place students first, then a repair pass |
| **DBSCAN + Kuhn–Munkres** (proposal §14.6–14.7) | DBSCAN finds dense neighbourhood pods (radius 1.5 km, ≥ 3 students); in each pod, well-connected students anchor circles and riders are assigned to anchor seats with the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`); a final pass forms circles “on the way” across pods |
| **Genetic Algorithm** (proposal §14.7) | Grouping GA: individuals are sets of feasible circles; seeded with the Compatibility, Greedy and DBSCAN solutions; tournament selection, circle-preserving crossover, dissolve/swap/move mutations with repair, elitism; 24 × 40 generations |
| **Exact optimum (MILP)** (RQ1) | Enumerates every feasible circle and solves the set-partitioning problem exactly (`scipy.optimize.milp`); up to ~90 students. Used to measure how close the heuristics get |

All share the hard rules above and are deterministic for a given seed.

**Objective** (`matching/optimise.py`), maximised by the Genetic Algorithm and the MILP and
reported for every algorithm: per circle,
`size × (100 + fit) − 60 − 2 × (total rider detour minutes)`. Matching a student is worth
far more than any fit or detour difference, so coverage comes first; each vehicle costs 60,
which favours fuller circles (RQ1: maximise occupancy); shorter detours break ties.

### 5.5 Results (synthetic data)
`python -m app.benchmark`: 5 synthetic pools per size, mean ± SD
(`docs/benchmark-synthetic.csv`). Every rider in every algorithm is within the 12-minute limit.

| Pool | Algorithm | Matched | Avg fit | Rider detour (min) | Occupancy | Gap to optimum | Time (s) |
|---|---|---|---|---|---|---|---|
| 70 | Greedy | 84.0 % ± 3.8 | 80.3 | 2.3 | 74 % | 12.1 % | 0.02 |
| 70 | k-means | 64.9 % ± 7.1 | **87.5** | 1.8 | **78 %** | 28.8 % | 0.01 |
| 70 | Compatibility | 88.0 % ± 3.4 | 78.4 | 2.2 | 70 % | 9.4 % | 0.01 |
| 70 | DBSCAN + Kuhn–Munkres | 85.4 % ± 3.8 | 85.3 | **1.3** | 61 % | 9.2 % | 0.04 |
| 70 | Genetic Algorithm | **92.3 %** ± 3.3 | 82.1 | 1.7 | 67 % | **2.9 %** | 0.34 |
| 70 | *Exact optimum* | *94.3 % ± 1.4* | *84.3* | *1.3* | *62 %* | *0* | *0.38* |
| 200 | Greedy | 92.2 % ± 1.5 | 83.1 | 2.0 | **86 %** | – | 0.03 |
| 200 | k-means | 85.1 % ± 3.5 | 90.4 | 1.2 | 82 % | – | 0.05 |
| 200 | Compatibility | 96.2 % ± 1.5 | 82.9 | 1.9 | 85 % | – | 0.07 |
| 200 | DBSCAN + Kuhn–Munkres | 95.4 % ± 1.6 | **91.4** | **0.8** | 63 % | – | 0.05 |
| 200 | Genetic Algorithm | **97.4 %** ± 1.0 | 89.2 | 1.1 | 78 % | – | 1.35 |
| 500 | Greedy | 95.7 % ± 0.9 | 87.2 | 1.4 | 92 % | – | 0.18 |
| 500 | k-means | 92.6 % ± 1.5 | 93.2 | 0.6 | 89 % | – | 0.30 |
| 500 | Compatibility | 98.3 % ± 0.5 | 87.7 | 1.4 | **94 %** | – | 0.37 |
| 500 | DBSCAN + Kuhn–Munkres | 98.3 % ± 0.5 | **94.8** | **0.4** | 66 % | – | 0.17 |
| 500 | Genetic Algorithm | **99.0 %** ± 0.5 | 92.4 | 0.7 | 83 % | – | 4.54 |

On the prototype's own 66 approved students: exact optimum 95.5 % matched, Genetic Algorithm
and DBSCAN + Kuhn–Munkres 93.9 %, Greedy 86.4 %, Compatibility 84.9 %, k-means 80.3 %.

**Interpretation (RQ1).**
* The Genetic Algorithm matches the most students at every size and comes within about 3 %
  of the exact optimum on 70-student pools, against 9–29 % for the other methods.
* DBSCAN + Kuhn–Munkres gives the most compatible circles and the shortest detours, but
  uses many 2–3 person circles (occupancy about 62–66 %): it trades occupancy for comfort.
* Greedy and Compatibility fill vehicles best but leave more students unmatched on small
  pools and detour riders more.
* All methods meet the proposal's targets on synthetic data: ≥ 75 % matched (except k-means
  on 70 students), every rider ≤ 12 minutes, one student's search ≤ 1.5 s. The whole-cohort
  Genetic Algorithm takes about 4.5 s for 500 students, acceptable for an occasional batch run.
* These are synthetic pools and estimated minutes. The final evaluation must be repeated on
  the consented pilot data (Matching lab → Research export), with OSRM travel times and a
  paired significance test across datasets.

## 6. Trips, money and the rota

* **Travel days**: weekdays when at least two members arrive within 20 minutes of that
  day's first member. A trip is created when a member first opens Today.
* **Check-in**: one member's “Yes” marks every planned member as travelled; anyone can
  correct their own record; “Didn't go” before confirmation marks only yourself.
* **Fare**: the confirmer may enter their share (suggestions from the median of fares in
  their area for that way of travelling); total = share × travellers, recorded against the
  payer. Ride-hailing and rickshaw are a fare split; “Classmate drives” shares fuel; family
  driver and parent drop cost nothing.
* **Balances**: each traveller owes total ÷ travellers, and the payer is owed the total;
  settlements and “Everyone settled up” reset the balance. Settle-up lines pair the
  largest debtor with the largest creditor.
* **Savings**: your share vs travelling alone the same way (road km = straight line × 1.35;
  ride-hailing Rs 52/km, rickshaw Rs 38/km, fuel Rs 352.59 ÷ 12 km/L).
* **Rota** (driving modes only): next two weeks; each day goes to the eligible member
  with the fewest turns so far (ties: who went least recently), skipping days they can't
  do; manual swaps are kept.
* **One-day seats**: other active circles travelling today that are compatible with you
  (women-only respected), have a free seat, are ≤ 8 km away or on your way, and arrive
  within 30 minutes. The host circle accepts or declines.
* **Reliability and badges**: shows-up % = travelled ÷ (travelled + didn't turn up).
  “Didn't turn up” feedback marks that member's latest confirmed trip as a no-show.
  Badges: a positive tag given twice (after 5+ trips), or “Reliable” at ≥ 95 %.

## 7. API summary

Interactive docs at `/docs` in development (hidden in production).

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `/login`; `GET/PATCH/DELETE /api/auth/me`; `GET /api/auth/me/export` |
| Find | `GET/PUT /api/trip`; `GET /api/find/options`; `POST /api/find/accept` |
| My circle | `GET /api/circle`; `POST /api/circle/respond`, `/leave`, `/feedback`, `/report`, `/rota/take`, `/rota/cant`; `PATCH /api/circle/mode` |
| Today | `GET /api/today`; `POST /api/today/yes`, `/no`, `/correct`, `/fare`; `POST /api/tomorrow` |
| Seats | `GET/POST /api/seats`; `POST /api/seats/{id}/answer`, `/cancel` |
| Money, savings | `GET /api/money`; `POST /api/money/settle`, `/settle-all`; `GET /api/savings` |
| Student Affairs | `GET /api/admin/usage`, `/fares`, `/health`, `/approvals`, `/reports`, `/users`, `/circles`, `/runs`, `/research-export`; `POST /api/admin/approvals/{id}`, `/compare`, `/match`, `/circles/{id}/dissolve`; `PATCH /api/admin/reports/{id}`, `/users/{id}` |

## 8. Security and personal data

* bcrypt passwords; JWT bearer tokens (12 h); 5 failed logins per email in 15 min → 429.
* Only `@bic.edu.pk` addresses can register, and every account waits for Student Affairs approval.
* Consent to the Terms, Privacy Notice and Code of Conduct is required and logged with
  its version; research consent is separate, optional and reversible.
* Students can download all their data and delete their account (password confirmed);
  safety reports survive deletion without identifying the person.
* The research export contains opted-in students only, with keyed-hash IDs and no names,
  emails or phone numbers.
* Non-members cannot see a circle; feedback and reports only about your own circle;
  suspension signs the student out and removes them from their circle.
* Security headers on every response (HSTS in production); the container runs as non-root.

## 9. Testing

`backend/tests/` holds **74 automated tests**, run on both SQLite and PostgreSQL 16 by
GitHub Actions on every push.

* **Matching (45):** fit score parts, women-only, detour, timetable window, travel modes and
  capacities, feasibility, options; the NumPy score table equals `pair_fit` on every pair;
  DBSCAN, the 12-minute detour rule, founder order; every algorithm (including DBSCAN +
  Kuhn–Munkres and the Genetic Algorithm) over random pools never breaks a rule, never places
  a student twice, and is deterministic; the exact optimum is never beaten and the Genetic
  Algorithm never does worse than its seeds; the prototype's students are mostly matched.
* **Student journeys (17):** sign-up validation, approval gate, trip questions, options and
  acceptance, availability re-check, decline memory, women-only, check-in and correction,
  fare entry and balances, not going tomorrow, weekends, fair and swappable rota, travel
  mode and leaving, feedback, badges and no-shows, report and leave, one-day seats,
  re-matching, savings.
* **Student Affairs and safety (12):** admin-only access, approvals, usage/fares/health,
  suspension from a report, matching lab, export and deletion, login throttle, admin
  bootstrap, production guards, safe v1 migration, demo seeding.

Browser checks (Playwright, Chromium): every screen rendered side by side with the
prototype; a full journey (sign up → approval → find → classmates accept → check in →
fare → money) with no console or server errors; no horizontal scrolling at phone width.

## 10. Known limitations and next steps

* Distances are straight lines between area centre points × 1.35 and minutes assume 22 km/h; a routing API (OSRM / OpenRouteService) would give real travel times.
* No email verification or notifications yet (Student Affairs approval covers identity for the pilot).
* WhatsApp group creation is a preview only.
* The login throttle is per process; use Redis if running several workers.
* Fare suggestions need real entries; until then they fall back to an estimate.
