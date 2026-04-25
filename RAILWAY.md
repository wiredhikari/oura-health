# Deploying to Railway — click-by-click

No Docker on your laptop, no SSH, no CLI. You push the code to GitHub once,
add six services in Railway's web UI, and you end up with a self-hosted
Oura analytics stack + AI assistant + weekly digest at a public URL.

Time: ~40 min the first time. Cost: ~$15–25/month, with $5 free trial credit.

---

## What you'll end up with

```
        public URL  (https://<your-app>.up.railway.app)        ← the Next.js app
                                 │
                                 ▼
                       ┌────────────────────┐
                       │      app           │   Next.js 14 — Today / Chat / Log / Trends / Digest
                       └──────────┬─────────┘
                                  │  Railway private network
                                  ▼
                       ┌────────────────────┐
                       │      api           │   FastAPI + Claude SSE chat + insights
                       └──────────┬─────────┘
                                  │
                       ┌──────────┴──────────┐
                       ▼                     ▼
                ┌────────────┐         ┌────────────┐
                │ timescaledb│ ◄────── │ sync (cron)│   Pulls Oura data every 3h
                └─────┬──────┘         └────────────┘
                      ▲
                      │
                ┌─────┴──────┐         ┌─────────────────┐
                │  grafana   │         │ digest (weekly) │   Sun 09:00 UTC,
                │ (public)   │         │     cron        │   Claude-written email
                └────────────┘         └─────────────────┘
```

Six services, one project. Two get public URLs:
- `app` — the main UI (where you log in with the passcode)
- `grafana` — the deep-dive dashboards (embedded into the app's Trends tab)

Everything else stays private.

---

## Phase 1 — Push the code to GitHub (one time)

Create a free GitHub account at <https://github.com> if you don't have one.

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

> **Don't worry about secrets being in `.env`** — that file stays on your
> laptop. Railway gets these values via its own variables screen, not from
> the repo.

---

## Phase 2 — Create the Railway project

1. Sign in at <https://railway.app> with GitHub.
2. **+ New Project → Deploy from GitHub repo → oura-health**.
3. Railway will create one service automatically and start building. Cancel
   the build (the auto-detected service is wrong root) and delete it; we'll
   add the six real services in a controlled way below.

You should now have an empty project. Note the project URL — you'll be back
on this page a lot.

---

## Phase 3 — Add the six services

For each service below, click **+ Create → GitHub Repo → oura-health**, then
**Settings → Source → Root Directory** and set the directory shown.

> **Order matters.** Add them top-down: `timescaledb` first (everyone
> depends on it), then `sync`, then `grafana`, then `api`, then `app`, then
> `digest`. Railway resolves `${{service.VAR}}` references at deploy time,
> so the referenced service must already exist.

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
`/var/lib/postgresql/data`, size `2 GB`.

**Networking**: leave private only (no public domain).

Click **Deploy**. Wait until it says "Deployed".

### 3b. `sync` — the Oura → DB worker (cron)

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
Railway picks it up automatically.

Click **Deploy**. The first run is the 2-year backfill (~5 min). Watch logs
to make sure it finishes cleanly: `inserted 14 daily_cva rows`,
`inserted 730 sleep sessions`, etc.

### 3c. `grafana` — the deep-dive dashboards

| field           | value         |
| --------------- | ------------- |
| Service name    | `grafana`     |
| Root Directory  | `grafana`     |

**Variables** — many reference the `timescaledb` service. In Railway's
variable input, type `${{` and a dropdown auto-completes from existing
services.

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
| `GF_AUTH_ANONYMOUS_ENABLED`      | `true`                                      |
| `GF_AUTH_ANONYMOUS_ORG_ROLE`     | `Viewer`                                    |
| `GF_USERS_DEFAULT_THEME`         | `dark`                                      |
| `GF_USERS_HOME_PAGE`             | `/d/oura-today`                             |
| `GF_SERVER_ROOT_URL`             | (set in two passes — see below)             |

> The `GF_SECURITY_ALLOW_EMBEDDING=true` + `GF_AUTH_ANONYMOUS_ENABLED=true`
> pair is what lets the `app`'s Trends tab iframe Grafana panels without
> a second login. Anonymous access is read-only (Viewer); admin actions
> still require login.

**Volume**: mount path `/var/lib/grafana`, size `1 GB`.

**Networking**: Settings → Networking → **Generate Domain**. Copy the URL
that appears (e.g. `https://oura-grafana-production.up.railway.app`). Set
the **Target Port** to `3000` when prompted. Bookmark this URL — it's where
you go to edit dashboards.

Now go back to **Variables** and set `GF_SERVER_ROOT_URL` to that exact URL
(must include the `https://`). Without this, Grafana's login redirects break.

Click **Deploy**.

### 3d. `api` — FastAPI backend

| field           | value     |
| --------------- | --------- |
| Service name    | `api`     |
| Root Directory  | `api`     |

**Variables**:

| key                 | value                                                            |
| ------------------- | ---------------------------------------------------------------- |
| `POSTGRES_HOST`     | `${{timescaledb.RAILWAY_PRIVATE_DOMAIN}}`                        |
| `POSTGRES_PORT`     | `5432`                                                           |
| `POSTGRES_DB`       | `${{timescaledb.POSTGRES_DB}}`                                   |
| `POSTGRES_USER`     | `${{timescaledb.POSTGRES_USER}}`                                 |
| `POSTGRES_PASSWORD` | `${{timescaledb.POSTGRES_PASSWORD}}`                             |
| `APP_PASSCODE`      | (long random string — what you'll type to log into the UI)       |
| `JWT_SECRET`        | (32+ random bytes — `openssl rand -hex 32` is fine)              |
| `JWT_TTL_DAYS`      | `30`                                                             |
| `ANTHROPIC_API_KEY` | `sk-ant-...` from <https://console.anthropic.com>                |
| `ANTHROPIC_MODEL`   | `claude-opus-4-6`                                                |
| `USER_NAME`         | (your first name — used in LLM prompts)                          |
| `USER_AGE`          | (number)                                                         |
| `USER_TIMEZONE`     | `Asia/Kolkata` (or your IANA TZ)                                 |
| `CORS_ORIGIN`       | `*` for now; tighten to your `app` URL after Phase 4             |
| `PORT`              | `8000`                                                           |

**Networking**: leave private only. The `app` will reach `api` via the
private network. **Do not** generate a public domain for `api` — that
would expose your `/auth/login` to the internet without rate limiting.

Click **Deploy**. Watch logs for `applying V2 schema migration` followed
by `V2 schema migration done` — this confirms the new tables (food_log,
supplement_log, chat_message, digest, weather_daily) were created on top
of the existing volume.

### 3e. `app` — the Next.js UI (public)

| field           | value     |
| --------------- | --------- |
| Service name    | `app`     |
| Root Directory  | `app`     |

**Variables**:

| key                       | value                                                |
| ------------------------- | ---------------------------------------------------- |
| `API_BASE_URL`            | `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000`        |
| `NEXT_PUBLIC_GRAFANA_URL` | (the public Grafana URL from step 3c)                |
| `PORT`                    | `3001`                                               |

**Networking**: Settings → Networking → **Generate Domain**, target port
`3001`. **This is your main public URL** — the one you'll bookmark on your
phone and "Add to Home Screen" to install as a PWA.

Click **Deploy**. Once it boots, open the URL — you should land on
`/login`. Type your `APP_PASSCODE` from step 3d and you're in.

> If you generated a custom Anthropic key, this is a good moment to confirm
> the chat works end-to-end: open the **Chat** tab, ask "what's my CVA
> trend looking like", and you should see streaming tokens come back.

### 3f. `digest` — weekly LLM email (cron)

| field           | value      |
| --------------- | ---------- |
| Service name    | `digest`   |
| Root Directory  | `digest`   |

**Variables**:

| key                 | value                                                        |
| ------------------- | ------------------------------------------------------------ |
| `POSTGRES_HOST`     | `${{timescaledb.RAILWAY_PRIVATE_DOMAIN}}`                    |
| `POSTGRES_PORT`     | `5432`                                                       |
| `POSTGRES_DB`       | `${{timescaledb.POSTGRES_DB}}`                               |
| `POSTGRES_USER`     | `${{timescaledb.POSTGRES_USER}}`                             |
| `POSTGRES_PASSWORD` | `${{timescaledb.POSTGRES_PASSWORD}}`                         |
| `ANTHROPIC_API_KEY` | (same as `api`)                                              |
| `ANTHROPIC_MODEL`   | `claude-opus-4-6`                                            |
| `RESEND_API_KEY`    | `re_...` from <https://resend.com> (optional — leave blank to skip email and only save to DB) |
| `DIGEST_EMAIL_FROM` | `digest@your-verified-domain.com` (Resend verified sender)   |
| `DIGEST_EMAIL_TO`   | (your inbox)                                                 |
| `USER_NAME`         | (same as `api`)                                              |

The cron schedule (`0 9 * * 0` — Sundays at 09:00 UTC) is already set in
`digest/railway.json`. Each run is idempotent: it skips if the digest for
that week already exists in the `digest` table.

**Networking**: leave private only.

Click **Deploy**. The first run won't fire until the next Sunday — to test
manually, hit **Deployments → ⋯ → Redeploy** on the digest service. After
it finishes, open the **Digest** tab in the app to see the rendered output.

---

## Phase 4 — First boot

1. Open the **app** public URL → log in with your `APP_PASSCODE`.
2. **Today** tab should populate within ~30s with your latest Oura data
   pulled by the sync service.
3. **Trends** tab embeds Grafana — if it shows a refused-to-connect frame,
   double-check `GF_SECURITY_ALLOW_EMBEDDING=true` and
   `GF_AUTH_ANONYMOUS_ENABLED=true` on the `grafana` service.
4. **Chat** tab — ask anything; you should see tokens stream in.

If the Today tab is empty, the sync service hasn't finished its first
backfill — check `sync` logs. If login itself fails, you typed the
passcode wrong: it must match `APP_PASSCODE` on the `api` service exactly.

---

## Phase 5 — Lock down `CORS_ORIGIN`

Once you know the `app`'s public URL, go back to the **api** service's
variables and change:

```
CORS_ORIGIN = https://your-app-name-production.up.railway.app
```

Redeploy `api`. From now on, only your real frontend can call the API
— a small but worthwhile defense-in-depth on top of the JWT auth.

---

## Day-to-day

| what                         | how                                                                |
| ---------------------------- | ------------------------------------------------------------------ |
| New ring data                | Already automatic — sync runs every 3h.                            |
| Force a sync now             | Sync service → **⋯ → Redeploy**.                                   |
| Talk to Claude about your data | Chat tab in the app.                                              |
| Log a meal / supplement      | Log tab in the app.                                                |
| Edit a Grafana dashboard     | Grafana public URL → log in as admin → edit. To make changes survive a rebuild, export the JSON and commit it back to `grafana/dashboards/` then `git push`. |
| Update code                  | `git push` to `main` — Railway auto-deploys all six services.      |
| Force a digest now           | Digest service → **⋯ → Redeploy**.                                 |
| Rotate Oura token            | sync service → Variables → edit `OURA_PAT` → Redeploy.             |
| Rotate the passcode          | api service → Variables → edit `APP_PASSCODE` → Redeploy. Existing JWTs stay valid until they expire (30 days). To invalidate immediately, also change `JWT_SECRET`. |

---

## Troubleshooting

**Sync fails with "could not translate host name"** — `POSTGRES_HOST` isn't
the right Railway variable; should be `${{timescaledb.RAILWAY_PRIVATE_DOMAIN}}`.

**Sync fails with 401** — Oura token is invalid or revoked. Generate a fresh
PAT and update the variable.

**App shows "Network error" on login** — `API_BASE_URL` is wrong on the
`app` service; must be `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000`. Note
`http://`, not `https://` — Railway's private network doesn't terminate TLS.

**Login succeeds but Today is empty** — sync hasn't finished its first
backfill. Open sync logs.

**Chat tab — "Anthropic API error"** — the `ANTHROPIC_API_KEY` on the
`api` service is wrong, or your Anthropic account is out of credit.

**Trends tab — refused to connect / blank iframe** — Grafana's
`GF_SECURITY_ALLOW_EMBEDDING` is missing or `false`. Add it and redeploy.

**Digest never sends** — leave `RESEND_API_KEY` blank → DB-only mode (you
can still read it in the Digest tab). Set it once you have a Resend
account + verified sender domain.

**Login redirect loop on Grafana** — `GF_SERVER_ROOT_URL` doesn't match
the public URL exactly (must include `https://`).

**`api` logs say "migration failed"** — usually a `permission denied` or
schema-mismatch on an older volume. The api keeps booting either way; if
nothing else seems broken, it usually means the tables already existed.

---

## Costs

Railway bills per resource-second. Rough monthly numbers for this stack
(idle most of the time, you're the only user):

| service       | typical cost |
| ------------- | ------------ |
| timescaledb   | ~$4          |
| grafana       | ~$4          |
| api           | ~$3          |
| app           | ~$3          |
| sync (cron)   | < $1         |
| digest (cron) | < $0.10      |
| **Total**     | **~$15/mo**  |

Plus Anthropic API costs: ~$0.50–2/month for casual chat use, more if you
chat heavily. The first $5/mo on Railway is free.

To shave costs: scale down the `app` and `grafana` services overnight via
Railway's "sleep" schedule, or drop to `claude-haiku-4-5-20251001` in
`ANTHROPIC_MODEL` for ~10x cheaper chat at slightly lower quality.

---

## Backups

Railway volumes don't auto-snapshot. For a one-off manual backup, use the
Railway CLI to open a shell against the timescaledb service and run
`pg_dump` from there. For automated weekly dumps to S3 / Backblaze, add a
seventh service that runs `ops/backup.sh` on cron.

---

## Rotating secrets

If you ever paste a secret into chat, a screenshot, a public Slack channel,
etc., treat it as compromised:

- **Oura PAT**: <https://cloud.ouraring.com/personal-access-tokens> →
  revoke, mint new, update `OURA_PAT` on the sync service.
- **Postgres password**: edit `POSTGRES_PASSWORD` on `timescaledb`. Because
  every other service references it via `${{timescaledb.POSTGRES_PASSWORD}}`,
  Railway auto-redeploys all dependents.
- **App passcode**: edit `APP_PASSCODE` on `api`. Existing browser sessions
  keep working until their JWT expires; to invalidate them immediately,
  also rotate `JWT_SECRET`.
- **Anthropic API key**: edit `ANTHROPIC_API_KEY` on **both** `api` and
  `digest` services.
- **Grafana admin password**: edit `GF_SECURITY_ADMIN_PASSWORD` on
  `grafana`. Only takes effect on **fresh** Grafana installs — to change
  it on an existing install, log in with the old password and use the UI.
- **JWT secret**: edit `JWT_SECRET` on `api`. Logs everyone (= you) out
  immediately.
