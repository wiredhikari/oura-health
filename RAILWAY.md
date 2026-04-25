# Deploying to Railway — click-by-click

No Docker on your laptop, no SSH, no CLI. You just push the code to GitHub
once, and Railway builds and runs everything in their cloud.

Time: ~25 min the first time. Cost: ~$5–15/month, with $5 free trial credit.

---

## What you'll end up with

```
                              public URL  (https://<your-app>.up.railway.app)
                                   │
                                   ▼
                       ┌──────────────────────┐
                       │   ui  (nginx)        │
                       └──────────┬───────────┘
                                  │  Railway private network
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
       ┌────────────┐      ┌────────────┐      ┌────────────┐
       │  grafana   │ ◄─── │ timescaledb│ ◄─── │ sync (cron)│
       └────────────┘      └────────────┘      └────────────┘
```

Four services, one project. Only `ui` gets a public URL.

---

## Phase 1 — Push the code to GitHub (one time)

You need a GitHub account; sign up free at <https://github.com> if you don't
have one. Then:

### 1a. Create an empty repo

1. Click **+ → New repository** in the GitHub top-right.
2. Name it `oura-health` (or whatever you like).
3. **Private** is fine — Railway can pull private repos.
4. Don't add a README/license/gitignore — we already have those.
5. Click **Create repository**. Leave the page open; you'll need the URL.

### 1b. Push from your laptop

Open Terminal and paste these commands one block at a time. Replace
`YOUR_USERNAME` with your GitHub username.

```bash
cd /Users/wired/repos/oura/health

# Wipe any stray .git from earlier setup, start fresh.
rm -rf .git

git init -b main
git add .
git status                 # double-check .env is NOT in this list
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/oura-health.git
git push -u origin main
```

If `git status` shows `.env`, stop — your `.gitignore` isn't catching it. Run
`echo .env >> .gitignore && git rm --cached .env` and commit again.

> **Don't worry about the Oura PAT or DB password being in `.env`** — that
> file stays on your laptop. Railway gets these values via its own variables
> screen, not from the repo.

---

## Phase 2 — Create the Railway project

1. Sign in at <https://railway.app> with GitHub.
2. **+ New Project → Deploy from GitHub repo → oura-health**.
3. Railway will create one service automatically and start building. Cancel
   the build (the auto-detected service is wrong root) and delete it; we'll
   add the four real services in a controlled way.

You should now have an empty project. Note the project URL — you'll be back
on this page a lot.

---

## Phase 3 — Add the four services

For each service below, click **+ Create → GitHub Repo → oura-health**, then
**Settings → Source → Root Directory** and set the directory shown.

### 3a. `timescaledb` — the database

| field           | value                |
| --------------- | -------------------- |
| Service name    | `timescaledb`        |
| Root Directory  | `db`                 |

**Variables** (Settings → Variables → Add):

| key                 | value                          |
| ------------------- | ------------------------------ |
| `POSTGRES_DB`       | `oura`                         |
| `POSTGRES_USER`     | `oura`                         |
| `POSTGRES_PASSWORD` | (generate a strong password)   |

**Volume**: Settings → Volumes → **Mount New Volume**, mount path
`/home/postgres/pgdata/data`, size `2 GB`.

**Networking**: leave private only (no public domain).

Click **Deploy**. Wait until it says "Deployed".

### 3b. `grafana` — the dashboards

| field           | value         |
| --------------- | ------------- |
| Service name    | `grafana`     |
| Root Directory  | `grafana`     |

**Variables** — many of these reference the timescaledb service. In
Railway's variable input, type `${{` and a dropdown appears letting you pick
`timescaledb.POSTGRES_PASSWORD` etc.; it auto-completes.

| key                              | value                                       |
| -------------------------------- | ------------------------------------------- |
| `POSTGRES_HOST`                  | `${{timescaledb.RAILWAY_PRIVATE_DOMAIN}}`   |
| `POSTGRES_PORT`                  | `5432`                                      |
| `POSTGRES_DB`                    | `${{timescaledb.POSTGRES_DB}}`              |
| `POSTGRES_USER`                  | `${{timescaledb.POSTGRES_USER}}`            |
| `POSTGRES_PASSWORD`              | `${{timescaledb.POSTGRES_PASSWORD}}`        |
| `GF_SECURITY_ADMIN_USER`         | `admin`                                     |
| `GF_SECURITY_ADMIN_PASSWORD`     | (strong)                                    |
| `GF_SECURITY_ALLOW_EMBEDDING`    | `true`                                      |
| `GF_SECURITY_COOKIE_SAMESITE`    | `lax`                                       |
| `GF_AUTH_ANONYMOUS_ENABLED`      | `true`                                      |
| `GF_AUTH_ANONYMOUS_ORG_ROLE`     | `Viewer`                                    |
| `GF_SERVER_ROOT_URL`             | (leave blank for now — set after step 3d)   |
| `GF_SERVER_SERVE_FROM_SUB_PATH`  | `false`                                     |

**Volume**: mount path `/var/lib/grafana`, size `1 GB`.

**Networking**: private only — do **not** generate a public domain. The UI
service proxies it.

Click **Deploy**.

### 3c. `sync` — the Oura → DB worker (runs on cron)

| field           | value     |
| --------------- | --------- |
| Service name    | `sync`    |
| Root Directory  | `sync`    |

**Variables**:

| key                 | value                                     |
| ------------------- | ----------------------------------------- |
| `OURA_PAT`          | (your **fresh** Oura token)               |
| `POSTGRES_HOST`     | `${{timescaledb.RAILWAY_PRIVATE_DOMAIN}}` |
| `POSTGRES_PORT`     | `5432`                                    |
| `POSTGRES_DB`       | `${{timescaledb.POSTGRES_DB}}`            |
| `POSTGRES_USER`     | `${{timescaledb.POSTGRES_USER}}`          |
| `POSTGRES_PASSWORD` | `${{timescaledb.POSTGRES_PASSWORD}}`      |
| `BACKFILL_DAYS`     | `730`                                     |
| `ONESHOT`           | `1`                                       |

The cron schedule (`0 */3 * * *`) is already set in `sync/railway.json` —
Railway will pick it up automatically.

Click **Deploy**. The first run is the 2-year backfill (~5 min). Watch logs
to make sure it finishes cleanly.

> If your repo is private, Railway might ask you to grant repo access to its
> GitHub App. Click through — it's read-only.

### 3d. `ui` — the public landing page

| field           | value   |
| --------------- | ------- |
| Service name    | `ui`    |
| Root Directory  | `ui`    |

**Variables**:

| key             | value                                   |
| --------------- | --------------------------------------- |
| `GRAFANA_HOST`  | `${{grafana.RAILWAY_PRIVATE_DOMAIN}}`   |
| `GRAFANA_PORT`  | `3000`                                  |

**Networking**: Settings → Networking → **Generate Domain**. Copy the URL
that appears (something like `https://oura-health-ui-production.up.railway.app`).

### 3e. Tell Grafana its public URL

Go back to the **grafana** service → Variables → edit `GF_SERVER_ROOT_URL`:

```
https://<the URL you copied from step 3d>
```

Click **Deploy** to apply. (Without this, Grafana's login redirects break.)

---

## Phase 4 — First boot

1. Open the **sync** service → **Deployments** tab → click the running
   deployment → watch logs. You want to see lines like
   `inserted 14 daily_cva rows`, `inserted 730 sleep sessions`, etc., and
   then the process exits cleanly.
2. Open the public URL from step 3d. Landing page should load with your
   stats populated. Click any tile to drop into a Grafana dashboard.

If the landing page loads but the dashboard tiles say "loading…" forever,
the most likely cause is `GF_SERVER_ROOT_URL` not matching the public
domain. Double-check step 3e.

---

## Day-to-day

| what                         | how                                                                |
| ---------------------------- | ------------------------------------------------------------------ |
| New ring data                | Already automatic — sync runs every 3h.                            |
| Force a sync now             | Sync service → **⋯ → Redeploy**.                                   |
| Edit a dashboard             | Use Grafana in the browser. To make edits permanent across rebuilds, export the JSON and commit it back to `grafana/dashboards/` then `git push`. |
| Update code                  | `git push` to `main` — Railway auto-deploys all four services.     |
| Rotate Oura token            | sync service → Variables → edit `OURA_PAT` → Redeploy.             |
| Rotate Grafana admin pw      | grafana service → Variables → edit → Redeploy.                     |

---

## Troubleshooting

**sync fails with "could not translate host name"** — `POSTGRES_HOST` isn't
the right Railway variable; should be `${{timescaledb.RAILWAY_PRIVATE_DOMAIN}}`.

**sync fails with 401** — Oura token is invalid or revoked. Generate a fresh
PAT and update the variable.

**UI loads but Grafana iframes 404** — the UI's `GRAFANA_HOST` is wrong.
Confirm the grafana service is named exactly `grafana` and the variable is
`${{grafana.RAILWAY_PRIVATE_DOMAIN}}`.

**Login redirect loop** — `GF_SERVER_ROOT_URL` doesn't match the public URL
exactly (must include `https://`).

**Empty dashboards** — backfill hasn't run or failed. Sync service →
Deployments → check logs.

---

## Costs

Railway bills per resource-second. Rough monthly numbers for this stack:

| service       | typical cost |
| ------------- | ------------ |
| timescaledb   | ~$5          |
| grafana       | ~$5          |
| ui            | ~$3          |
| sync (cron)   | < $1         |
| **Total**     | **~$13/mo**  |

The first $5 each month is free. Bring your usage down by sleeping the
grafana + ui services overnight in Railway's settings if you only check
during the day.

---

## Backups

Railway volumes don't auto-snapshot. Set up a scheduled job that runs
`ops/backup.sh` and ships the dump to S3 / Backblaze, or use the Railway
plugin marketplace for managed Postgres backups.

For a one-off manual backup, you can `railway connect timescaledb` (CLI) to
get a `psql` shell, then `pg_dump` from there.

---

## Rotating secrets

If you ever paste a secret into chat, a screenshot, a public Slack channel,
etc., treat it as compromised:

- Oura PAT: <https://cloud.ouraring.com/personal-access-tokens> → revoke,
  mint new, update the `OURA_PAT` variable in the sync service.
- Postgres password: edit the `POSTGRES_PASSWORD` variable on the timescaledb
  service. Because grafana/sync reference it via `${{timescaledb.POSTGRES_PASSWORD}}`,
  they pick up the change automatically — Railway redeploys all dependents.
- Grafana admin password: edit `GF_SECURITY_ADMIN_PASSWORD` on the grafana
  service. Note: this only changes the password on **fresh** Grafana
  installs. To change it on an existing install, log in with the old
  password and use the UI.
