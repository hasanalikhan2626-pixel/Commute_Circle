# CommuteCircle: Technical Documentation

_Version 2.2 (November 2026). Rebuilt to match the CommuteCircle prototype
(`CommuteCircle_Prototype.html`) and the CE201 project proposal. Campus: BIC Karachi,
273/1/A Main Ibrahim Hyderi Road, Korangi Creek, Karachi 75190 (24.8086702, 67.1217257)._

## 1. Overview

CommuteCircle introduces BIC students who live near each other, or on each other's way,
and come to campus at the same times, so they can travel together. BIC doesn't arrange
transport: the app only introduces classmates, and they decide how to travel.

| Students (prototype tabs) | Student Affairs (prototype tabs + additions) |
|---|---|
| **Find my circle**: three questions, then up to three circle options with a 0–100 fit score, a map and an explanation of the fit, detour and cost | **Usage**: totals, trips per day, demand map, gaps by area, trust, women-only, open SOS |
| **Today**: one-tap “Reached campus?”, fare entry, star ratings, **SOS**, “Not going tomorrow”, one-day seat in another circle, streaks | **Fares**: what students actually pay, by area and way of travelling |
| **My circle**: members with show-up rate, trust score and badges, weekly plan, travel mode with its cost, driving rota, private feedback, re-match, report or leave | **Circle health**: completion, no-shows, negative feedback and trust, with “Check in” flags |
| **Money**: who paid, who owes, settle-up | **Approvals**: sign-ups checked against the student record (email verified?) |
| **My savings**: alone vs your share, fare guide, evaluation surveys | **Reports**: SOS alerts, reports, suspension, private negative feedback |
| **Account**: details, emergency contact, WhatsApp opt-in, research consent, data download, deletion | **Matching lab** (research), **Evaluation** (proposal targets), **Students**, **Messages** (outbox) |

The app is installable on phones (Progressive Web App).

## 2. What changed from the prototype

The prototype was a single HTML page with dummy data in memory. Version 2 keeps its
screens, wording, styles and matching method, and adds what a real service and the
proposal need.

| Prototype | Version 2 |
|---|---|
| “Testing as” switcher, data resets on reload | Real accounts (BIC email + password), PostgreSQL database |
| Approvals list with dummy sign-ups | Every new account is *pending* until Student Affairs approves it; 6-digit email verification; password reset by email |
| Accepting a circle = everyone accepts at once | The others are asked; numbers are shared only when all accept; proposals lapse after 3 days |
| “Find my circle” overwrote per-day times with one arrive/leave time | Per-day times are kept (“Different times on some days”) |
| Re-match removed people from other circles immediately | The old circle is left only once the new one is confirmed |
| Rota assigned turns by position | Fair rota from turn history, “Can’t do it” / “I’ll take it” |
| Seat request accepted automatically | The host circle accepts or declines |
| A circle could form with no travel method in common | A common way of travelling is required, with a vehicle that can carry the group |
| Five ways of travelling, family driver / parent drop free | Adds **motorbike pillion** (Rs 15/km); family driver / parent drop passengers pay a Rs 20/km fuel contribution (proposal Appendix C) |
| Detour only lowered the fit score | Proposal hard rule: no rider's detour over 12 minutes, using **real road times** (OSRM) |
| Circle fit averaged one direction per pair | Both directions, so a circle's score doesn't depend on listing order |
| Auto-rickshaw circles of 4 | Rickshaw carries 3 passengers (proposal Appendix C) |
| 👍/👎 feedback only | Adds 1–5 star ratings and a **Bayesian trust score** (proposal §14.7) |
| “Contact campus security” text | **SOS button**: call 15 / 1122 / campus security and alert Student Affairs (proposal Appendix D) |
| WhatsApp group shown as “Created” | **WhatsApp Cloud API** reminders, check-ins and replies (switches on with Meta credentials); the group card stays a preview |

## 3. Architecture

```
React PWA (Vite)  ──JSON over HTTPS──▶  FastAPI  ──SQLAlchemy──▶  PostgreSQL (Neon) / SQLite (dev)
frontend/src                            backend/app
  pages/          one file per tab        routers/     auth, student, admin, integrations (WhatsApp, jobs)
  components/     Map, SOS, surveys…      services/    circles, trips & money, rota, notify, codes, jobs, surveys, clock
  styles.css      the prototype CSS       matching/    pure algorithms, fit score, roads, fares, evaluation
public/           manifest, icons, sw.js  migrate.py   Alembic migrations on start-up
                                          data/        OSRM road table (committed)
External: Brevo (email), Meta WhatsApp Cloud API, GitHub Actions (every-15-minute jobs)
```

* **Pure matching core.** `matching/` has no database access, so the algorithms are
  unit-tested and benchmarked on their own (`python -m app.benchmark`).
* **Single deployable.** FastAPI serves the built React app from `frontend/dist`
  (the Dockerfile builds both). Render runs the container; Neon holds the database.
* **Karachi time.** “Today” is the date in Asia/Karachi (`services/clock.py`). Weekends have no trips.
* **Configuration** (`backend/app/config.py`, environment variables):

  | Variable | Default | Notes |
  |---|---|---|
  | `CC_ENV` | development | `production` enables the safety checks below |
  | `CC_SECRET_KEY` | dev value | ≥ 32 random characters in production |
  | `CC_DATABASE_URL` | SQLite file | PostgreSQL in production; `postgres://` accepted |
  | `CC_EMAIL_DOMAINS` | bic.edu.pk | Only these can register |
  | `CC_CAMPUS_LAT/LNG` | 24.8086702, 67.1217257 | Campus map pin |
  | `CC_FUEL_PRICE_PKR` | 352.59 | Petrol price for “Classmate drives” |
  | `CC_MAX_DETOUR_MIN` | 12 | Hard limit on any rider's detour |
  | `CC_TRAFFIC_FACTOR` | 2.0 | OSRM free-flow times × this = peak-hour times |
  | `CC_AVG_SPEED_KMH` | 22 | Fallback speed for points not in the road table |
  | `CC_ROAD_MATRIX` | on | `off` uses straight line × 1.35 instead of the OSRM table |
  | `CC_ADMIN_EMAIL` / `CC_ADMIN_PASSWORD` | – | Creates the first admin on start-up (hosts with no shell) |
  | `CC_BREVO_API_KEY`, `CC_EMAIL_FROM`, `CC_EMAIL_FROM_NAME` | – | Email (Brevo); without them emails are logged as “mock” |
  | `CC_WHATSAPP_TOKEN`, `CC_WHATSAPP_PHONE_ID`, `CC_WHATSAPP_APP_SECRET`, `CC_WHATSAPP_VERIFY_TOKEN` | – | WhatsApp Cloud API (`docs/WHATSAPP.md`) |
  | `CC_JOBS_TOKEN` | – | Protects `/api/jobs/run` (called by GitHub Actions) |
  | `CC_SECURITY_PHONE`, `CC_SECURITY_WHATSAPP` | – | Campus security number shown on SOS / messaged on SOS |
  | `CC_SEED_DEMO` | – | `true` loads the prototype's demo data into an *empty*, non-production database |
  | `CC_TODAY`, `CC_NOW` | – | Development only: pin today's date / time (weekend demos, tests) |

  In production the app refuses to start with a weak secret, SQLite or no email domain;
  the API docs are hidden; the seed script refuses to run; unsigned WhatsApp webhooks are refused.

## 4. Data model

| Table | Purpose |
|---|---|
| `users` | Account, role, status (pending / approved / rejected / suspended), approval time, email verified, consent version and time, research consent, WhatsApp opt-in, emergency contact |
| `profiles` | Gender, programme, year, area, women-only, ways of travelling, car and seats, motorbike, weekly timetable (per-day arrive/leave) |
| `circles`, `circle_members` | Circle (proposed / active / dissolved), way of travelling, fit, who found it; members in order |
| `trips`, `trip_members` | One circle trip per day: travelled / not going / didn't turn up, who confirmed, fare total and payer; guests from other circles |
| `trip_ratings` | 1–5 stars between members after a confirmed trip |
| `absences`, `rota_entries`, `rota_unavailable` | “Not going tomorrow”; who drives or drops each day; days someone can't |
| `settlements`, `feedback`, `seat_requests`, `declined_pairs` | Settle-ups; private 👍/👎; one-day seats; pairs never suggested again |
| `reports`, `sos_alerts` | Safety reports; SOS presses with circle, route and handling note |
| `survey_responses` | SUS, safety perception, monthly spending before and after |
| `notifications` | Outbox of every WhatsApp message and email (sent / mock / failed), de-duplicated |
| `email_codes` | Hashed one-time codes for verification and password reset |
| `match_runs` | Research batch runs |

Schema changes go through **Alembic** (`backend/migrations`, versions 0001 and 0002). On
start-up `app/migrate.py` creates or upgrades the schema. A database still on the v1 layout is
rebuilt only if it holds **no student accounts** (admin logins are carried across); otherwise the
app refuses to start rather than risk data. A test fails if the models and migrations ever differ.

**Privacy by design.** Students choose an area, never an address. Suggested circles show first
name, initial, programme and area. Phone numbers appear only once every member has accepted.
Student Affairs screens show totals; names appear only for approvals, reports and SOS.

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
directions** (the prototype averaged one direction per pair, which made the score
order-dependent). 75+ “Great fit”, 60+ “Good fit”, otherwise “Fair fit”. Minimum to be
suggested: **45**. For a whole pool, `Scorer` computes every pair's fit at once with NumPy
(identical to `pair_fit`, checked on ~19,000 pairs).

### 5.2 Hard rules (`Scorer.feasible`, proposal §14.7 stage 1)
2–4 members; women-only students only with women; every pair scores ≥ 35 with at least one
good day; at least one weekday when everyone arrives within 20 minutes of the circle's
founder; a way of travelling everyone accepts that can carry the group (rickshaw 3 passengers,
motorbike 2 people and a member with a bike, “Classmate drives” a car with enough seats,
others 4); no previously declined pair; and **no rider's detour over 12 minutes**. A set of
students is a valid circle if *any* of them can be its founder (`Scorer.arrange`).

### 5.3 Road distances and detour minutes (`matching/roads.py`)
A 33 × 33 table of road km and driving times between every pickup area and campus was
fetched once from the **OSRM** routing engine (OpenStreetMap road network,
`python -m app.data.fetch_road_matrix`) and is committed in `backend/app/data/road_matrix.json`,
so the app never calls a routing service at runtime and sends no personal data. Roads are on
average 1.42 × the straight-line distance. OSRM times are free-flow, so they are multiplied by
a traffic factor of 2.0 (about 25 km/h door to door at peak; configurable). Pickups run
furthest-first; a rider's **detour** is the extra time they spend in the vehicle compared with
going straight to campus. Points outside the table fall back to straight line × 1.35 at 22 km/h.

### 5.4 Find my circle (`algorithms.py::build_for`, `options_for`)
Start from the student; repeatedly add the classmate who maximises
`0.6 × (weakest pair score in the circle) + 0.4 × (fit with the student)` while the circle
stays feasible, up to 4. Options: the best circle overall plus circles seeded with each of the
student's six best matches; duplicates removed; ranked by `fit + 6 × size`; top three. Each
option comes with an explanation (fit parts per classmate, each person's detour, and the cost
working for every way the group could travel; proposal §14.9). Accepting re-checks everything.
One search takes **0.03 s on average (worst 0.10 s) with 500 students** (target ≤ 1.5 s).

### 5.5 Algorithms compared (RQ1)
| Algorithm | Idea |
|---|---|
| **Greedy** (baseline) | In sign-up order, each student takes the nearest classmates that keep the circle feasible |
| **k-means** | Cluster by location (k = ⌈n/4⌉), then form circles inside each cluster |
| **Compatibility** | The Find my circle method applied to everyone, hardest-to-place students first, then a repair pass |
| **DBSCAN + Kuhn–Munkres** (proposal §14.6–14.7) | DBSCAN finds dense neighbourhood pods (radius 1.5 km, ≥ 3 students); in each pod, well-connected students anchor circles and riders are assigned to anchor seats with the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`); a final pass forms circles “on the way” across pods |
| **Genetic Algorithm** (proposal §14.7) | Grouping GA: individuals are sets of feasible circles; seeded with the Compatibility, Greedy and DBSCAN solutions; tournament selection, circle-preserving crossover, dissolve/swap/move mutations with repair, elitism; 24 × 40 generations |
| **Exact optimum (MILP)** (RQ1) | Enumerates every feasible circle and solves the set-partitioning problem exactly (`scipy.optimize.milp`); up to ~90 students. Measures how close the heuristics get |

**Objective** (`matching/optimise.py`), maximised by the Genetic Algorithm and the MILP and
reported for every algorithm: per circle, `size × (100 + fit) − 60 − 2 × (total rider detour
minutes)`. Coverage comes first; each vehicle costs 60, which favours fuller circles (RQ1:
maximise occupancy); shorter detours break ties.

### 5.6 Results (synthetic data, OSRM road times)
`python -m app.benchmark`: 5 synthetic pools per size, mean ± SD
(`docs/benchmark-synthetic.csv`). Every rider in every algorithm is within 12 minutes.

| Pool | Algorithm | Matched | Avg fit | Rider detour (min) | Occupancy | Gap to optimum | Time (s) |
|---|---|---|---|---|---|---|---|
| 70 | Greedy | 78.0 % ± 5.1 | 79.7 | 3.2 | 71 % | 13.0 % | 0.02 |
| 70 | k-means | 60.9 % ± 3.9 | 85.9 | 2.4 | **77 %** | 28.3 % | 0.01 |
| 70 | Compatibility | 78.6 % ± 5.3 | 82.8 | 2.9 | 70 % | 11.1 % | 0.01 |
| 70 | DBSCAN + Kuhn–Munkres | 77.7 % ± 6.9 | **86.1** | **2.2** | 67 % | 10.1 % | 0.04 |
| 70 | Genetic Algorithm | **85.7 %** ± 3.6 | 83.2 | 2.5 | 67 % | **2.4 %** | 0.46 |
| 70 | *Exact optimum* | *88.9 % ± 1.9* | *83.5* | *2.3* | *62 %* | *0* | *0.29* |
| 200 | Greedy | 89.5 % ± 1.4 | 83.5 | 2.9 | **81 %** | – | 0.04 |
| 200 | k-means | 79.7 % ± 3.1 | 91.3 | 1.7 | 80 % | – | 0.06 |
| 200 | Compatibility | 92.9 % ± 0.9 | 84.1 | 2.9 | 79 % | – | 0.08 |
| 200 | DBSCAN + Kuhn–Munkres | 90.5 % ± 1.8 | **91.7** | **1.3** | 67 % | – | 0.04 |
| 200 | Genetic Algorithm | **93.9 %** ± 1.0 | 89.9 | 1.8 | 74 % | – | 1.69 |
| 500 | Greedy | 94.3 % ± 0.9 | 87.5 | 2.1 | 88 % | – | 0.18 |
| 500 | k-means | 88.9 % ± 2.0 | 93.2 | 1.1 | 87 % | – | 0.29 |
| 500 | Compatibility | **96.6 %** ± 0.4 | 87.9 | 2.5 | **90 %** | – | 0.38 |
| 500 | DBSCAN + Kuhn–Munkres | 95.7 % ± 0.5 | **94.4** | **1.0** | 68 % | – | 0.18 |
| 500 | Genetic Algorithm | 96.5 % ± 0.9 | 93.1 | 1.3 | 80 % | – | 5.09 |

On the prototype's own 66 approved students: exact optimum 95.5 % matched, Genetic Algorithm
92.4 %, DBSCAN + Kuhn–Munkres 90.9 %, Compatibility 84.9 %, Greedy 81.8 %, k-means 78.8 %.

**Interpretation (RQ1).**
* On small pools the Genetic Algorithm matches the most students and comes within about 2.4 %
  of the exact optimum, against 10–28 % for the other methods.
* On large pools Compatibility and the Genetic Algorithm match about equally (96.6 % vs 96.5 %),
  but the Genetic Algorithm's circles fit better (93.1 vs 87.9) with half the detour.
* DBSCAN + Kuhn–Munkres gives the most compatible circles and the shortest detours but uses
  many 2–3 person circles (occupancy about 67 %): it trades occupancy for comfort.
* Real road times make detours longer than the earlier straight-line estimate, so the 12-minute
  rule rules out more circles and match rates are 3–8 points lower than with the estimate.
* All methods except k-means meet the ≥ 75 % matching target on synthetic data; every rider is
  within 12 minutes; one student's search is far under 1.5 s. The final evaluation must be
  repeated on the consented pilot data, with a paired significance test across datasets.

### 5.7 Privacy vs efficiency (RQ2, `python -m app.privacy_sim`)
The app never collects addresses, so RQ2 is a simulation: synthetic “true homes” are scattered
around each area centre, and the same 200 students (5 pools) are matched with pickups at the
exact home, at the nearest point of a 600 m landmark grid (proposal §14.5), or at the area
centre (the app). `docs/privacy-sim.csv`; homes within 1 km of the centre:

| Pickup point | Matched | Vehicle km vs exact | Mean walk | Walk ≤ 300 m | Students per pickup point |
|---|---|---|---|---|---|
| Exact home | 94.1 % | baseline | 0 m | 100 % | 1.0 |
| Landmark grid (600 m) | 93.9 % | −3.9 % | 233 m | 77 % | 1.0 |
| Area centre (app) | 94.5 % | −5.2 % | 663 m | 9 % | 7.5 |

* Abstracting pickups costs **no** vehicle efficiency (riders walk to the pickup point, which
  shortens the car's route by 1–6 %), so the ≤ 8 % route-penalty target is met at every level.
* Area centres give real anonymity (about 7–8 students share each point) but long walks; the
  ≤ 300 m walking target is not met (9 % of riders). Landmarks meet it for ~80 % of riders, but
  on a 200-student pilot almost every landmark belongs to one student, so it reveals roughly
  where they live. Recommendation: use a public landmark only when at least 3 students share
  it, otherwise the area centre.

## 6. Trips, money and the rota

* **Travel days**: weekdays when at least two members arrive within 20 minutes of that day's
  first member. A trip is created when a member first opens Today (or replies on WhatsApp).
* **Check-in**: one member's “Yes” (in the app or replying **1** on WhatsApp) marks every planned
  member as travelled; anyone can correct their own record.
* **Cost model** (`matching/fares.py`, proposal Appendix C):

  | Way | Cost of one trip | Who pays |
  |---|---|---|
  | Shared ride-hailing | Rs 52/km × road km | split equally between everyone who travelled |
  | Auto-rickshaw (≤ 3) | Rs 38/km × road km | split equally |
  | Classmate drives | road km ÷ 12 km/L × Rs 352.59 | split equally, driver included |
  | Motorbike pillion (2) | Rs 15/km × road km | the passenger pays the rider |
  | Family driver / parent drop | Rs 20/km × road km | shared by the passengers; the host family pays nothing |

  The confirmer enters their share; total = share × the people who share the cost; the
  provider in passenger-pays modes is never charged. Suggestions come from the median of real
  fares in the student's area, or the cost card when there are none.
* **Balances and savings**: each sharer owes total ÷ sharers, the payer is owed the total;
  savings compare your share with travelling alone the same way (motorbike: bike ride-hailing at
  Rs 50/km).
* **Rota** (driving modes, including motorbike): next two weeks; each day goes to the eligible
  member with the fewest turns so far, skipping days they can't do; manual swaps are kept.
* **One-day seats**: other active circles travelling today that are compatible, have a free
  seat, are ≤ 8 km away or on your way, and arrive within 30 minutes; the host circle decides.

## 7. Safety, trust and evaluation

* **SOS** (proposal Appendix D): a red button on Today and My circle offers one-tap calls to
  Police 15, Rescue 1122 and (if set) campus security, and “Alert Student Affairs now”, which
  records the time, circle, route areas and message, shows it at the top of Reports, and (with
  WhatsApp set up) messages campus security and the student's emergency contact.
* **Trust score** (proposal §14.7 stage 3), 0–5, shown to the circle:
  `0.5 × rating + 0.5 × 5 × reliability`, where *rating* is a Bayesian average of 1–5 star
  ratings with a prior of 4.0 worth 5 ratings, and *reliability* is a Beta(4, 1)-smoothed
  show-up rate. New students start at 4.0; a few ratings can't swing it. Circles with a member
  below 3.5 are flagged in Circle health. Individual ratings are private to Student Affairs.
* **Surveys** (proposal §14.8): monthly spending when joining; after 5 trips, the standard
  10-item **SUS** (score 0–100), three safety statements, and monthly spending now.
* **Evaluation tab**: the proposal's targets against live data: matching rate (≥ 75 %), mean
  rider detour (≤ 12 min), riders within 12 min, cost reduction (paired survey and app
  estimate, ≥ 40 %), female students in a circle (≥ 85 %), SUS (≥ 78), female safety
  perception, safety incidents (0), active circles (≥ 20), trust (≥ 4.5), and admin
  verification latency (≤ 4 h, from sign-up to approval).

## 8. Messages: email and WhatsApp

* **Outbox** (`services/notify.py`): every email and WhatsApp message is stored first, then
  sent; without credentials it is stored as **mock** (visible in Student Affairs → Messages), so
  everything works before the accounts exist. Reminders are de-duplicated per student per day.
* **Email (Brevo)**: a 6-digit code at sign-up verifies the BIC address (codes are hashed,
  expire, allow 5 attempts, and can be resent once a minute); once email is connected, a
  student must verify before matching. **Forgot password** emails a 30-minute reset code and
  never reveals whether an account exists.
* **WhatsApp Cloud API** (`docs/WHATSAPP.md`): opt-in on the Account page. GitHub Actions calls
  `POST /api/jobs/run` every 15 minutes on weekdays: a reminder 30–60 minutes before the circle's
  arrival (proposal: 45 minutes prior), a check-in after arrival time, and expiry of stale
  proposals. Incoming replies arrive at a signature-checked webhook: **1** confirms the trip,
  **2** marks “didn't go”, a number records the fare share, **skip** skips it, **STOP** opts out.
  Invitations to a proposed circle are messaged to opted-in classmates. Mobile numbers are unique
  per account so replies always reach the right student.

## 9. API summary

Interactive docs at `/docs` in development (hidden in production).

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `/login`, `/verify`, `/verify/send`, `/forgot`, `/reset`, `/consent`; `GET/PATCH/DELETE /api/auth/me`; `GET /api/auth/me/export` |
| Find | `GET/PUT /api/trip`; `GET /api/find/options`; `POST /api/find/accept` |
| My circle | `GET /api/circle`; `POST /api/circle/respond`, `/leave`, `/feedback`, `/report`, `/rota/take`, `/rota/cant`; `PATCH /api/circle/mode` |
| Today | `GET /api/today`; `POST /api/today/yes`, `/no`, `/correct`, `/fare`, `/rate`; `POST /api/tomorrow` |
| Safety, surveys | `POST /api/sos`; `GET /api/surveys`; `POST /api/surveys/{sus,safety,spend_before,spend_after}` |
| Seats | `GET/POST /api/seats`; `POST /api/seats/{id}/answer`, `/cancel` |
| Money, savings | `GET /api/money`; `POST /api/money/settle`, `/settle-all`; `GET /api/savings` |
| Student Affairs | `GET /api/admin/usage`, `/fares`, `/health`, `/approvals`, `/reports`, `/users`, `/circles`, `/runs`, `/evaluation`, `/outbox`, `/research-export`; `POST /api/admin/approvals/{id}`, `/compare`, `/match`, `/circles/{id}/dissolve`; `PATCH /api/admin/reports/{id}`, `/users/{id}`, `/sos/{id}` |
| Integrations | `POST /api/jobs/run` (token); `GET/POST /api/whatsapp/webhook` (Meta) |

## 10. Security and personal data

* bcrypt passwords; JWT bearer tokens (12 h); 5 failed logins per email in 15 min → 429.
  Tokens carry a keyed stamp of the password hash, so resetting or changing a password signs
  out every other device.
* Abuse limits: one feedback per classmate per day (no badge farming or repeated no-show
  marks); pressing SOS again within 5 minutes updates the same alert instead of messaging
  everyone twice; one live one-day-seat request per day; seat offers respect the vehicle's
  real capacity (rickshaw 3, motorbike 2).
* Only `@bic.edu.pk` addresses can register; email ownership is verified by code; every
  account waits for Student Affairs approval.
* Consent to the Terms, Privacy Notice and Code of Conduct is required and logged with its
  version; when the notice changes, students are asked to agree again. Research consent is
  separate, optional and reversible. WhatsApp is opt-in and can be stopped by replying STOP.
* Students can download all their data (including ratings, surveys, SOS alerts and the log of
  messages sent to them) and delete their account (password confirmed); deletion also erases
  their entries in the message log; safety reports survive without identifying the person.
* The research export contains opted-in students only, with keyed-hash IDs and no names,
  emails or phone numbers.
* WhatsApp webhooks must carry Meta's HMAC signature; the jobs endpoint needs a secret token;
  email codes are hashed and rate-limited.
* Non-members cannot see a circle; feedback, ratings and reports only about your own circle;
  suspension signs the student out and removes them from their circle.
* Security headers on every response (HSTS in production); static files cannot escape the
  build folder; the container runs as non-root.

## 11. Performance

Every screen makes a small, fixed number of database queries however many students or trips
exist, which matters because the database (Neon) is reached over the network.
Relationships that are always needed load eagerly (a circle with its members and their
profiles; a trip with its members); statistics for many students come from grouped SQL
(`services/trips.py::stats_for`); fare guides use the last 90 days of fares in three queries.

| Screen (demo data: 71 students, ~200 trips) | Queries before | Now |
|---|---|---|
| Student Affairs → Fares | 18,434 | 6 |
| Student Affairs → Circle health | 821 | 9 |
| Student Affairs → Usage | 781 | 13 |
| My savings | 594 | 13 |
| Today | 319 | 27 |
| One-day seats | 115 | 7 |

A test fails if any of these screens goes above 40 queries.

## 12. Installable app (PWA)

`frontend/public` holds the web app manifest, icons (192, 512, maskable, Apple touch) and a
service worker. The app shell is cached so the app opens instantly and can be added to the
home screen; **API calls always go to the network**, so trips, money and SOS are never stale.

## 13. Testing

`backend/tests/` holds **92 automated tests**, run on both SQLite and PostgreSQL 16 by GitHub
Actions on every push, together with a lint check (ruff).

* **Matching and research (49):** fit score parts, women-only, detour, timetable window, travel
  modes and capacities (rickshaw 3, motorbike 2), feasibility, founder order, options; the NumPy
  score table equals `pair_fit`; the OSRM road table and its fallback; DBSCAN; the 12-minute rule;
  every algorithm over random pools never breaks a rule, never places a student twice and is
  deterministic; the exact optimum is never beaten and the Genetic Algorithm never does worse than
  its seeds; the cost card matches Appendix C; the privacy simulation.
* **Student journeys (24):** sign-up validation and unique phones, approval gate, trip questions,
  options and acceptance, availability re-check, decline memory, women-only, check-in and
  correction, fares and balances, passenger-pays modes, not going tomorrow, weekends, fair rota,
  travel mode and leaving, feedback and no-shows, report and leave, one-day seats, re-matching,
  savings, SOS, ratings and trust, surveys and SUS scoring, WhatsApp jobs, webhook and replies,
  abuse limits, seat offers and vehicle capacity.
* **Student Affairs and safety (17):** admin-only access, approvals, usage/fares/health,
  suspension from a report, matching lab, export and deletion, login throttle, admin bootstrap,
  production guards, safe v1 migration, demo seeding, email verification and password reset,
  re-consent to an updated privacy notice, sign-out on password reset, erasing the message log,
  and the per-screen query budget.
* **Migrations (2):** the migrations build exactly the models' schema; upgrading keeps rows.

The v1 → v2.1 upgrade was also run in production mode on PostgreSQL with a copy of the live
layout (admin login kept, every screen loading). Browser checks (Playwright, Chromium): every
screen rendered side by side with the prototype; a full journey (sign up → approval → find →
classmates accept → check in → fare → money) with no console or server errors; no horizontal
scrolling at phone width.

## 14. Known limitations and next steps

* Pickup points are area centres (≈ 660 m average walk in the simulation); a catalogue of
  public landmarks shared by ≥ 3 students would meet the 300 m target without losing anonymity.
* Peak-hour times use one traffic factor (2.0) for the whole city; real times vary by corridor
  and hour.
* WhatsApp needs a Meta Business account and approved templates; until then it runs in mock mode.
* The login throttle is per process; use Redis if running several workers.
* The proposal's “repeat cancellations reduce matching priority” is not implemented: low trust
  is flagged to Student Affairs (Circle health) but does not yet change who is suggested.
* There are no automated front-end tests in CI; the browser checks are run by hand.
* All results so far are synthetic; the pilot must provide the real evaluation.
