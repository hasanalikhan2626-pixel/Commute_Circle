# Deploying CommuteCircle (free tier)

**Stack:** Render (free web service, Docker) + Neon (free PostgreSQL). Both are free
with no card required, and give you a public HTTPS URL.

> Why not Render's own database? Render's free PostgreSQL is deleted after 30 days,
> which would lose real student data mid-year. Neon's free tier does not expire.
> Why not SQLite? Render's free disk is wiped on every deploy or restart.

## 1. Put the code on GitHub
Create an empty repository and push this folder to it (`git push -u origin main`).

## 2. Create the database (Neon)
1. Sign up at neon.tech and create a project (region: *AWS Asia Pacific (Singapore)*, nearest to Karachi).
2. Copy the **connection string** (`postgresql://…?sslmode=require`).

## 3. Create the web service (Render)
1. Sign up at render.com with GitHub, then choose **New → Blueprint** and pick the repository.
   Render reads `render.yaml`.
2. When asked, paste the Neon string into `CC_DATABASE_URL`. `CC_SECRET_KEY` is generated for you.
3. Wait for the first deploy (about 5 minutes). Then open `https://<service>.onrender.com/api/health`;
   it should return `{"status":"ok"}`.
4. If your service URL differs from `commutecircle.onrender.com`, update `CC_CORS_ORIGINS`.

## 4. Create the transport-office admin
In Render, open the service, then **Shell**, and run:
```
python -m app.create_admin transport@bic.edu.pk "Transport Office"
```
Never run `python -m app.seed` against production (it refuses when `CC_ENV=production`).

## 5. Before the Week 25 demo
* Free Render services **sleep after 15 minutes idle** and take about 50 seconds to wake.
  Open the site a few minutes before presenting.
* For a demo with fake data, deploy a **second** service pointing at a **separate** Neon
  database with `CC_ENV=development`, then seed that one. Never mix demo and real data.

## Backups
Neon keeps 24 hours of point-in-time history on the free tier. For extra safety,
export weekly: `pg_dump "$CC_DATABASE_URL" > backup-YYYY-MM-DD.sql`.
