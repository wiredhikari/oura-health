# oura-health

A self-hosted, one-command personal health analytics stack for Oura Ring
data — plus a Claude-powered AI assistant, a custom Today/Chat/Log/Trends
UI, and a weekly LLM-written digest emailed every Sunday.

Targets the "lower your Cardiovascular Age" goal laid out in
[`oura-cva-blueprint.md`](./oura-cva-blueprint.md), but it works as a
general-purpose longitudinal Oura analytics box.

Everything runs as containers on your laptop (or a Railway project). No
cloud dependency beyond Oura, Anthropic, and (optionally) Resend.

```
                                          public URL
                                              │
                                              ▼
                  ┌────────────────────────────────────────────┐
                  │  app (Next.js 14, PWA)                     │
                  │  ├─ Today      live CVA / sleep / HR       │
                  │  ├─ Chat       Claude SSE assistant        │
                  │  ├─ Log        food / supplement / cron    │
                  │  ├─ Trends     embeds Grafana dashboards   │
                  │  └─ Digest     weekly Claude reports       │
                  └────────────────────┬───────────────────────┘
                                       │
                                       ▼
                  ┌────────────────────────────────────────────┐
                  │  api (FastAPI + psycopg + Anthropic SDK)   │
                  │  passcode → JWT, /chat is SSE-streamed     │
                  └────────────────────┬───────────────────────┘
                                       │
                                       ▼
                  ┌────────────────────────────────────────────┐
                  │  TimescaleDB (Postgres 16)                 │
                  │  hypertables: hr_intraday, hrv_intraday,   │
                  │               activity_met                 │
                  │  daily: cva / sleep / readiness /          │
                  │         activity / stress / resilience /   │
                  │         spo2 / vo2_max                     │
                  │  v2:    food_log, supplement_log,          │
                  │         chat_message, digest, weather      │
                  │  + continuous aggregates + views           │
                  └─────────▲───────────────────────▲──────────┘
                            │                       │
              ┌─────────────┴───────┐    ┌──────────┴──────────┐
              │ sync (cron, 3h)     │    │ grafana (public)    │
              │ Oura → DB           │    │ deep-dive dashboards│
              └─────────────────────┘    └─────────────────────┘
                            ▲
                            │
                  ┌─────────┴───────────┐
                  │ digest (cron, weekly)│
                  │ Claude → email      │
                  └─────────────────────┘
```

Six services. Two get public URLs (`app`, `grafana`); the rest are private.

## Quickstart

You need Docker Desktop (or any Docker engine 24+ with Compose v2), an
Oura Ring subscription that lets you mint a Personal Access Token, and an
Anthropic API key.

```bash
git clone <this repo> oura-health
cd oura-health

cp .env.example .env
# Edit .env. The minimum to run:
#   OURA_PAT             — https://cloud.ouraring.com/personal-access-tokens
#   POSTGRES_PASSWORD    — anything strong
#   APP_PASSCODE         — what you'll type to log into the UI
#   JWT_SECRET           — `openssl rand -hex 32`
#   ANTHROPIC_API_KEY    — https://console.anthropic.com
#   USER_NAME            — your first name (used in LLM prompts)

make up
```

First boot takes ~2 minutes (TimescaleDB init + Grafana provisioning + 2-year
Oura backfill + Next.js build). Then:

- **App**:     <http://localhost:3001>      ← log in with `APP_PASSCODE`
- **Grafana**: <http://localhost:3000>      ← admin / `GF_SECURITY_ADMIN_PASSWORD`
- **API**:     <http://localhost:8000/docs> ← OpenAPI / interactive docs

The `digest` service is under the `manual` compose profile so it doesn't
auto-start. To fire one off locally (writes to DB and optionally emails):

```bash
docker compose --profile manual run --rm digest
```

## What's in the app

The app is a Next.js 14 PWA — installable to your phone's home screen via
the address-bar "Add to Home Screen" on iOS / "Install app" on Android.

- **Today** — live CVA card, Claude-written morning insight, sleep /
  readiness / activity scorecards, 24h HR chart, quick-log buttons,
  preview of the latest digest.
- **Chat** — full conversational assistant with access to your data
  (last night's HRV, today's CVA delta, recent food/supplement log,
  active interventions). Streams tokens via SSE. History persists per
  session in the `chat_message` table.
- **Log** — three tabs: food, supplement, intervention. Forms post to
  the API; recent entries render below.
- **Trends** — embeds the four Grafana dashboards in iframes (kiosk
  mode, dark theme).
- **Digest** — weekly markdown reports rendered with `react-markdown`.

## Day-to-day

| what                                 | how                                    |
| ------------------------------------ | -------------------------------------- |
| Pull the latest Oura data on demand  | `make sync`                            |
| Generate a weekly digest now         | `docker compose --profile manual run --rm digest` |
| Tail logs                            | `make logs` / `make logs-sync`         |
| Open a psql shell                    | `make shell-db`                        |
| Backup the database                  | `make backup`                          |
| Restore                              | `make restore f=backups/<file>.sql.gz` |
| Print all useful URLs                | `make url`                             |
| Stop the stack (keep data)           | `make down`                            |
| Wipe everything                      | `make nuke`                            |

`make help` prints the full command list.

## What it captures

Every relevant Oura endpoint, per day or per minute:

| scope          | source                                                       |
| -------------- | ------------------------------------------------------------ |
| Cardiovascular | `daily_cardiovascular_age`, `vo2_max`                        |
| Sleep          | `sleep` (per-session) + `daily_sleep`                        |
| Recovery       | `daily_readiness`, `daily_resilience`                        |
| Activity       | `daily_activity` (+ per-minute MET), `workout`               |
| Stress         | `daily_stress`                                               |
| Oxygen         | `daily_spo2`                                                 |
| Time-series    | `heartrate` (nightly + daytime), HRV arrays from sleep files |
| Journal        | `enhanced_tag`                                               |

Plus user-supplied data via the Log tab: food (with macros), supplements,
and interventions (new protocol, supplement, bedtime shift, etc.). The
`intervention` table also drives Grafana annotations — see
`sql/03_views.sql`.

## Dashboards (Grafana — deep-dive)

All four are provisioned automatically and embedded into the app's
**Trends** tab:

- `/d/oura-cva` — **CVA Tracker**: 14-day avg, 7-day Δ, raw vs smoothed, HRV & RHR overlays, intervention annotations.
- `/d/oura-today` — **Today**: readiness/sleep/activity gauges, live HR over the last 24h, daily Δ sparklines.
- `/d/oura-training` — **Training Load**: ATL / CTL / TSB, performance management chart, zone distribution.
- `/d/oura-sleep` — **Sleep Architecture**: stage stack, HRV-by-night, temperature deviation, 30-night table.

You can edit them live in Grafana; to make edits survive a container rebuild,
export the dashboard JSON back into `grafana/dashboards/<name>.json`.

## Alerts

Four rules ship in `grafana/provisioning/alerting/alerts.yaml`:

1. **Illness early-warning** — HRV drops > 1.5 SD below 60-day baseline *and* body-temp deviation > +0.30 °C on the same night.
2. **Overtraining risk** — RHR elevated + HRV depressed for 3 consecutive days.
3. **Sleep debt** — < 6.5h on 4+ of the last 7 nights.
4. **CVA regression** — 7-day rolling vascular age drifts ≥ +1.0 off its 30-day best.

By default they fire into a placeholder webhook. Edit
`grafana/provisioning/alerting/contact-points.yaml` to point them at Slack,
Discord, ntfy, Pushover, or a Shortcut.

## AI assistant + weekly digest

`api/app/llm.py` defines three system prompts (chat, insight, digest) and
`build_data_snapshot()` that pulls a JSON of your current state — last
night's HRV, today's CVA, 7-day deltas, recent food/supplement log,
active interventions. Each LLM call grounds in this snapshot, so Claude
talks about *your* data instead of generalities.

- **Chat** (`POST /chat`) streams tokens as SSE. Session history is kept
  in `chat_message`; the last 20 turns are replayed each call.
- **Insight** (`GET /insight/today`) is a single-shot Claude call —
  rendered on the Today tab, regenerable with a button.
- **Digest** is a separate service that runs Sundays at 09:00 UTC,
  pulls the trailing 7 days, asks Claude for a structured weekly review,
  saves it to the `digest` table, and (if `RESEND_API_KEY` is set) emails
  it to `DIGEST_EMAIL_TO`.

## Deploying to Railway

See [`RAILWAY.md`](./RAILWAY.md). Six services (timescaledb, sync, grafana,
api, app, digest), same images. Both `app` and `grafana` get Railway public
domains; everything else stays on the private network.

## Repo layout

```
oura-health/
├── docker-compose.yml          # one-command stack (6 services)
├── Makefile                    # make up / sync / backup / …
├── .env.example                # template — copy to .env and fill in
├── oura-cva-blueprint.md       # the "why" / protocol doc
├── README.md                   # this file
├── RAILWAY.md                  # cloud deploy
│
├── db/
│   └── Dockerfile              # timescale/timescaledb:latest-pg16 + init SQL
├── sql/
│   ├── 01_schema.sql           # tables + hypertables (Oura)
│   ├── 02_continuous_aggregates.sql
│   ├── 03_views.sql            # rolling CVA, ATL/CTL/TSB, daily join
│   └── 04_v2_schema.sql        # food_log, supplement_log, chat, digest, weather
│
├── sync/
│   ├── Dockerfile
│   ├── entrypoint.sh           # supports ONESHOT=1 for cron-mode
│   ├── oura_sync.py            # full Oura v2 sync
│   └── requirements.txt
│
├── grafana/
│   ├── Dockerfile
│   ├── dashboards/             # JSON, one per dashboard
│   └── provisioning/
│       ├── datasources/timescaledb.yaml
│       ├── dashboards/dashboards.yaml
│       └── alerting/{alerts,contact-points}.yaml
│
├── api/
│   ├── Dockerfile              # python:3.12-slim + uvicorn
│   ├── railway.json
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI entrypoint, lifespan migrations
│       ├── config.py           # pydantic-settings env loader
│       ├── db.py               # psycopg pool + helpers
│       ├── auth.py             # passcode → JWT (HS256)
│       ├── queries.py          # all SQL helpers (today, CVA, HR, daily, …)
│       ├── llm.py              # Anthropic system prompts + snapshot builder
│       ├── migrations.py       # idempotent CREATE IF NOT EXISTS for v2 tables
│       └── routes/             # auth, health, log, chat (SSE), digest
│
├── app/
│   ├── Dockerfile              # multi-stage Next.js standalone build
│   ├── railway.json
│   ├── package.json            # next 14, recharts, react-markdown
│   ├── next.config.js          # rewrites /api/backend/* → API_BASE_URL/*
│   ├── tailwind.config.ts
│   ├── app/                    # App Router pages (Today / Chat / Log / Trends / Digest / Login)
│   ├── components/             # Nav, AuthGate, ScoreCard, Spark, Insight
│   ├── lib/                    # typed API client (lib/api.ts)
│   └── public/                 # PWA manifest + service worker
│
├── digest/
│   ├── Dockerfile
│   ├── railway.json            # cronSchedule: "0 9 * * 0"
│   ├── digest.py               # 7-day window → Claude → DB + (Resend) email
│   └── requirements.txt
│
└── ops/
    ├── backup.sh               # pg_dump → ./backups/ (rolling 14)
    └── restore.sh              # inverse
```

## Security notes

- `.env` is in `.gitignore` — don't commit it.
- The Oura PAT grants read access to everything the ring records; treat it
  like a password and rotate it if it ever lands in chat logs, screenshots,
  or a public repo.
- The app uses passcode → JWT auth (HS256). Pick a long `APP_PASSCODE`
  and a `JWT_SECRET` of 32+ random bytes. Tokens expire after `JWT_TTL_DAYS`.
- The Anthropic API key has full account access; use a project-scoped key
  if you can.
- Postgres is not exposed to the host network by default. Uncomment the
  `ports:` block in `docker-compose.yml` if you want to connect with
  psql/DBeaver.
- In production (Railway), only `app` and `grafana` get public domains.
  `api`, `sync`, `digest`, and `timescaledb` stay on the private network.

## Verifying your setup

```bash
# Oura token
curl -s -H "Authorization: Bearer $OURA_PAT" \
  https://api.ouraring.com/v2/usercollection/personal_info | jq .

# API liveness
curl -s http://localhost:8000/healthz

# API readiness (touches DB)
curl -s http://localhost:8000/readyz

# App
curl -s http://localhost:3001/api/healthz
```

A 200 with your ring details (or `{"ok": true}`) means you're good.

## License

Personal use. Bring your own ring.
