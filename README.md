# oura-health

A self-hosted, one-command personal health analytics stack for Oura Ring
data. Targets the "lower your Cardiovascular Age" goal laid out in
[`oura-cva-blueprint.md`](./oura-cva-blueprint.md), but it works as a
general-purpose longitudinal Oura analytics box.

Everything runs as containers on your laptop (or a Railway project). No
cloud dependency beyond Oura's own API.

```
                 ┌──────────────────────────────────────────┐
                 │  UI (nginx)          :8080  ← you open   │
                 │  ├─ landing page with mission state      │
                 │  └─ reverse-proxies Grafana on same      │
                 │     origin so iframes just work          │
                 └───────────────────┬──────────────────────┘
                                     │
                                     ▼
                 ┌──────────────────────────────────────────┐
                 │  Grafana 11 (provisioned)                │
                 │  ├─ CVA Tracker                          │
                 │  ├─ Today / live vitals                  │
                 │  ├─ Training load (ATL/CTL/TSB)          │
                 │  └─ Sleep architecture                   │
                 │     + alert rules for illness / overtrain │
                 └───────────────────┬──────────────────────┘
                                     │ SQL
                                     ▼
                 ┌──────────────────────────────────────────┐
                 │  TimescaleDB (Postgres 16 + pgvector)    │
                 │  hypertables: hr_intraday, hrv_intraday, │
                 │               activity_met               │
                 │  daily: cva / sleep / readiness /        │
                 │         activity / stress / resilience / │
                 │         spo2 / vo2_max                   │
                 │  + continuous aggregates + views         │
                 └───────────────────▲──────────────────────┘
                                     │
                 ┌───────────────────┴──────────────────────┐
                 │  Sync worker (Python)                    │
                 │  ├─ cron: 0 */3 * * *                    │
                 │  ├─ first run: 730-day backfill          │
                 │  └─ subsequent: 7-day reconciliation     │
                 └──────────────────────────────────────────┘
```

## Quickstart

You need Docker Desktop (or any Docker engine 24+ with Compose v2) and an
Oura Ring subscription that lets you mint a Personal Access Token.

```bash
git clone <this repo> oura-health
cd oura-health

cp .env.example .env
# Edit .env:  OURA_PAT=<your token from https://cloud.ouraring.com/personal-access-tokens>
#             POSTGRES_PASSWORD=<something strong>
#             GF_SECURITY_ADMIN_PASSWORD=<something strong>

make up
```

First boot takes ~2 minutes (TimescaleDB init + Grafana provisioning + 2-year
Oura backfill). Then open **<http://localhost:8080>**.

You'll see the landing page. Click any tile to drop into Grafana.

## Day-to-day

| what                                 | how                                    |
| ------------------------------------ | -------------------------------------- |
| Pull the latest Oura data on demand  | `make sync`                            |
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

Interventions (new protocol, supplement, bedtime shift, etc.) are logged into
the `intervention` table — see `sql/03_views.sql` for the view that renders
them as Grafana annotations.

## Dashboards

All four are provisioned automatically. URLs are on the same origin as the
landing page:

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

## Deploying to Railway

See [`RAILWAY.md`](./RAILWAY.md). Four services (db, grafana, sync, ui), same
images, sync runs on a 3-hour cron instead of an embedded one.

## Repo layout

```
oura-health/
├── docker-compose.yml          # one-command stack
├── Makefile                    # make up / sync / backup / …
├── .env.example                # template — copy to .env and fill in
├── oura-cva-blueprint.md       # the "why" / protocol doc
├── README.md                   # this file
├── RAILWAY.md                  # cloud deploy
│
├── db/
│   └── Dockerfile              # timescale/timescaledb-ha:pg16 + init SQL
├── sql/
│   ├── 01_schema.sql           # tables + hypertables
│   ├── 02_continuous_aggregates.sql
│   └── 03_views.sql            # rolling CVA, ATL/CTL/TSB, daily join
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
├── ui/
│   ├── Dockerfile              # nginx + the landing page
│   ├── nginx.conf              # proxies /d/ /api/ etc. to grafana
│   ├── proxy.conf
│   └── index.html              # the glass-morphic hero you saw
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
- Grafana is exposed only behind the UI reverse-proxy. Anonymous view-only is
  enabled so the embedded dashboard tiles render without a login; to require
  login everywhere, set `GF_AUTH_ANONYMOUS_ENABLED=false` in `.env`.
- Postgres is not exposed to the host network by default. Uncomment the
  `ports:` block in `docker-compose.yml` if you want to connect with
  psql/DBeaver.

## Verifying your Oura token

Locally (outside the stack):

```bash
curl -s -H "Authorization: Bearer $OURA_PAT" \
  https://api.ouraring.com/v2/usercollection/personal_info | jq .
```

A 200 with your ring details means you're good. A 401 means the token is
invalid or has been revoked — go mint a new one.

## License

Personal use. Bring your own ring.
