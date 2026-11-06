# Deploying CommuteCircle (free tier)

**Stack:** Render (free web service, Docker) + Neon (free PostgreSQL). Both are free
with no card required, and give you a public HTTPS URL.

> Why not Render's own database? Render's free PostgreSQL is deleted after 30 days,
> which would lose real student data mid-year. Neon's free tier does not expire.
> Why not SQLite? Render's free disk is wiped on every deploy or restart.

## 1. Put the code on GitHub
Create an empty repository and push this folder to it (`git push -u origin main`).

## 2. Create the database (Neon)
1. In the Neon console, open your project (or choose **New project**: Postgres **16**,
   region **AWS Asia Pacific (Singapore)**, nearest to Karachi).
2. Click **Connect**, turn **Connection pooling off**, and copy the connection string
   (`postgresql://…neon.tech/neondb?sslmode=require…`). The app runs one process, so it
   doesn't need the pooler, and a direct connection avoids PgBouncer prepared-statement issues.
3. Treat this string as a password: paste it only into Render, never into chat or the repo.

`neon.ts` and the root `package.json` hold the Neon CLI project config (`neon init`).
The Python app does not use them; it only reads `CC_DATABASE_URL`.

## 3. Create the web service (Render)
1. Sign up at render.com **with GitHub** and allow access to the `Commute_Circle` repository.
2. Choose **New → Blueprint** and select the repository; Render reads `render.yaml`.
3. Render asks for two secret values:
   * `CC_DATABASE_URL`: the Neon string from step 2.
   * `CC_ADMIN_PASSWORD`: a new password (12+ characters) for the transport-office
     account `transport@bic.edu.pk`, which the app creates on first start.
   `CC_SECRET_KEY` is generated for you.
4. Click **Apply** and wait for the first deploy (about 5–10 minutes; the log ends with
   `Application startup complete`).
5. Open `https://<service>.onrender.com/api/health`; it should show `{"status":"ok"}`.
6. If your URL is not `commutecircle.onrender.com`, set `CC_CORS_ORIGINS` to it under
   **Environment** (this saves and redeploys).

## 4. First sign-in
1. Sign in at your Render URL as `transport@bic.edu.pk` with the password from step 3.
2. Optionally delete `CC_ADMIN_PASSWORD` under **Environment** afterwards. The account
   stays; the variable is only read when the account does not exist yet, and an existing
   account is never overwritten.
3. Students register themselves with their `@bic.edu.pk` email.

Render's free plan has no Shell. Where a shell is available, `python -m app.create_admin`
also creates or resets an admin. Never run `python -m app.seed` against production
(it refuses when `CC_ENV=production`).

## 5. Before the Week 25 demo
* Free Render services **sleep after 15 minutes idle** and take about 50 seconds to wake.
  Open the site a few minutes before presenting.
* For a demo with fake data, deploy a **second** service pointing at a **separate** Neon
  database with `CC_ENV=development`, then seed that one. Never mix demo and real data.

## Backups
Neon keeps 24 hours of point-in-time history on the free tier. For extra safety,
export weekly: `pg_dump "$CC_DATABASE_URL" > backup-YYYY-MM-DD.sql`.
