# The Oura-Centered Personal Health Analytics Powerhouse

**A 2026 Technical Blueprint**

*Prepared for: Atharva (Pune, India) — targeting Oura Cardiovascular Age of −3 to −4 in 8 weeks, built on a self-hosted, developer-first stack.*

---

## Executive Summary

Your Oura Ring's Cardiovascular Age (CVA) is a slow-moving metric derived from nocturnal photoplethysmography (PPG) waveform features that estimate pulse-wave velocity (PWV) — it is not driven by workouts directly, but by the downstream arterial-stiffness effects of training, sleep, weight, sodium, and recovery habits (Oura Help). Anecdotally, Oura members have moved CVA from +7.5 to +3 in seven weeks with twice-weekly cardio/strength plus a weekly swim (Oura Blog), and a NUS/Oura study published in *PLOS Digital Health* found Oura's overnight PPG-derived vascular age has a mean error of 6–7 years against clinical pulse-wave references (Oura/NUS). Going from 0 to −3 or −4 in 8 weeks is aggressive but plausible if you drive the underlying physiology: aerobic volume, a single weekly Norwegian 4×4 (proven to raise VO₂max ~7–13% in 8 weeks, Helgerud et al. 2007), sleep depth, sodium restriction, weight-loss continuation, and HRV-guided recovery.

The recommended opinionated stack, tuned for a Go/TypeScript developer hosting near Pune:

- **Ingestion:** Go-based Oura sync daemon (OAuth2 + webhooks) → Prefect 3 for orchestration of secondary sources.
- **Storage:** TimescaleDB (Postgres 16 + hypercore + pgvector extension) as a single unified store for time-series, relational, and vector data.
- **Backend API:** Go (Fiber/Echo) for ingestion hot paths + a thin FastAPI service for ML/analytics endpoints.
- **Dashboards:** Grafana for operational/biometric monitoring + Evidence.dev for weekly narrative "reports."
- **Notebooks:** marimo (reactive, git-friendly Python) for exploration; not Jupyter.
- **Agents:** Claude Agent SDK (TypeScript) orchestrating MCP servers (Oura MCP, PubMed MCP, custom TimescaleDB MCP).
- **Deployment:** Single Hetzner CCX33 dedicated-vCPU server (Falkenstein or Hillsboro) + Dokploy for PaaS ergonomics + Caddy for TLS.
- **Causal/stats layer:** `CausalImpact` (via rpy2 or Python port), `pymc`, `statsforecast` (Nixtla) for forecasting, `darts` for anomaly detection.

The remainder of this report is the depth behind every decision, plus a week-by-week 8-week roadmap.

---

## 1. Oura Ring API Deep Dive

### 1.1 API surface and endpoints (v2)

The v1 API was removed on January 22, 2024; everything you build must target API v2 at `https://cloud.ouraring.com/v2/docs` (Oura API v1 notice). Oura Gen3 and Ring 4 users must hold an active Oura Membership for the API to return data (Oura Help).

The full v2 endpoint list (confirmed against active third-party clients) is:

**Daily summaries** (`/v2/usercollection/...`):

- `daily_activity`, `daily_sleep`, `daily_readiness`, `daily_stress`, `daily_resilience`, `daily_spo2`, `daily_cardiovascular_age` (Pinta365/oura_api).

**Detail streams:**

- `sleep` (sessions, phases, HR/HRV interval arrays, breathing), `sleep_time` (ideal bedtime), `heartrate` (daytime intraday), `workout`, `session` (breathwork/meditation), `rest_mode_period`, `ring_configuration`, `personal_info`, `vO2_max`, `enhanced_tag` (the replacement for deprecated `tag`).

**Webhook subscription** (`/v2/webhook/subscription`):

- `list`, `create`, `update`, `delete`, `renew` — enables near-real-time push notifications when new data is processed; recommended over polling (Pinta365).

**Data granularity — the most important thing to understand:**

- Daily summaries are one record per `day`.
- Sleep sessions embed interval arrays: `heart_rate.items` is sampled at a 5-minute interval (300 s), `hrv.items` at 5-minute (300 s) during sleep, `movement_30_sec` at 30 s, `sleep_phase_5_min` at 5 min (hedgertronic/oura-ring).
- Daytime heart rate is measured for 1 full minute every 5 minutes under low-movement conditions (Oura Help – Heart Rate Graph). The `/heartrate` endpoint returns these 5-minute aggregated values (not raw PPG).
- MET values are returned per minute in `daily_activity.met.items` (60-second interval).
- Raw PPG waveform is not exposed via the API. Oura's CVA and Cardio Capacity models run server-side on the raw signal; consumers receive only derived scores.

### 1.2 Authentication — important 2025 change

Historically Oura exposed two auth flows: Personal Access Token (PAT) and OAuth2. As of 2025 there is conflicting messaging in the ecosystem: the Pinta365 TypeScript client and Oura's developer platform announcements indicate that direct PATs have been deprecated for new applications in favor of OAuth2 (Pinta365 JSR). However, `https://cloud.ouraring.com/personal-access-tokens` still issues PATs for personal use, and multiple active MCP servers rely on them (oura-mcp README). **Practical recommendation for a personal project:** generate a PAT today, but build the app with an OAuth2 refresh-token path so you aren't caught out when/if PATs are fully retired. OAuth2 implicit-flow access tokens expire in 30 days without a refresh token (Pinta365).

### 1.3 Rate limits

Public documentation and official MCP servers confirm **5,000 requests per rolling 5-minute window per token** (pokidyshev/oura-mcp) — this is generous enough that you will never hit it legitimately in a personal project. Pagination is token-based via `next_token` on list endpoints.

### 1.4 Webhooks

Oura's webhook subscription mechanism delivers push notifications for new/updated objects. You `POST /v2/webhook/subscription` with a callback URL, event type (e.g., `daily_sleep.created`), and a verification handshake. Subscriptions must be renewed periodically (the `renew` endpoint exists precisely for this). This is the correct pattern for "materialize into my TimescaleDB as soon as Oura processes a night's sleep." Example existing integration: Terra's Oura bridge POSTs normalized JSON to user webhooks whenever new data arrives (Terra API).

### 1.5 What drives Cardiovascular Age specifically (see §2 for depth)

**Feature-level:** CVA is computed from age-related changes in PPG waveform shape plus estimated pulse wave velocity (PWV). The official Oura explainer states that CVA is affected by "diet, exercise, genetic predisposition, blood pressure, cholesterol levels, and smoking" (Oura Help – CVA). It requires ≥14 nights of data in the past 30 days to calibrate; it is a slow-moving metric by design and Oura explicitly warns that "lifestyle changes can take several weeks to show a noticeable effect."

As of April 2025, Oura added the ability to attach custom Tags to specific lifestyle behaviors to correlate with CVA trends (Oura Blog – All About CVA). The `enhanced_tag` endpoint exposes these, which matters enormously for your own causal-inference pipeline (see §5).

### 1.6 Recent (2025–2026) API additions

- `daily_cardiovascular_age` endpoint surfacing the metric daily (previously only visible in-app).
- `daily_resilience` score (stress resilience over rolling windows).
- `enhanced_tag` replacing legacy `tag`.
- `vO2_max` endpoint surfacing walking-test and manually-added values.
- NUS/Oura validation paper on vascular age (2025) (Oura).
- Independent study in *The Physiological Society* found Oura Ring Gen3/4 had the best HRV and RHR accuracy vs. WHOOP, Garmin, Polar across 500+ nights (Oura).

### 1.7 Minimal Go fetcher skeleton

```go
// oura/client.go
package oura

import (
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

const base = "https://api.ouraring.com/v2/usercollection"

type Client struct {
    token string
    http  *http.Client
}

func New(token string) *Client {
    return &Client{token: token, http: &http.Client{Timeout: 30 * time.Second}}
}

func (c *Client) fetch(ctx context.Context, path string, out any) error {
    req, _ := http.NewRequestWithContext(ctx, "GET", base+path, nil)
    req.Header.Set("Authorization", "Bearer "+c.token)
    resp, err := c.http.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()
    if resp.StatusCode != 200 {
        return fmt.Errorf("oura %s: %d", path, resp.StatusCode)
    }
    return json.NewDecoder(resp.Body).Decode(out)
}

func (c *Client) DailyCVA(ctx context.Context, start, end string) (*CVAResp, error) {
    var r CVAResp
    err := c.fetch(ctx, fmt.Sprintf("/daily_cardiovascular_age?start_date=%s&end_date=%s", start, end), &r)
    return &r, err
}
```

---

## 2. What Specifically Drives Oura Cardiovascular Age

### 2.1 The physiology — distinguish CVA from Cardio Capacity

These are two separate metrics and Oura explicitly states they do not directly affect each other (Oura Help):

| Metric | What it measures | Input | Cadence |
|---|---|---|---|
| **Cardiovascular Age (CVA)** | Arterial stiffness (PWV proxy) from nocturnal PPG waveform shape | Passive every night | Slow (weeks to shift) |
| **Cardio Capacity (VO₂max)** | Cardiorespiratory fitness | 6-minute (not 7-minute) walking test via GPS + HR | Updated per test, recommended monthly (Oura Help) |

Your target metric is **CVA**. Its drivers, per Oura and the underlying cardiovascular literature:

1. **Aerobic exercise volume** — improves endothelial function and reduces arterial stiffness. Target: 150+ minutes/week moderate-to-vigorous (Oura Blog).
2. **Resistance training** — member anecdotes in Oura's blog cite combined cardio + strength reducing CVA from +7.5 to +3 in 7 weeks (Oura).
3. **Sleep quality** — deep sleep reduces inflammation and stress hormones that stiffen arteries.
4. **Dietary sodium restriction** — explicitly called out by Oura's in-app guidance.
5. **Weight loss** — you've already dropped from 95 kg → 86 kg, which mechanically reduces afterload.
6. **Smoking cessation, blood pressure, cholesterol, stress management.**

### 2.2 Interventions that move VO₂max fastest (supporting CVA via cardiorespiratory fitness)

**Norwegian 4×4** (the single best-researched protocol):

- 4 min at 85–95% HRmax, 3 min active recovery, repeated 4× (total ~38 min including warm-up/cool-down).
- Helgerud et al. 2007 found ~7–9% VO₂max increase in 8 weeks at 3×/week in moderately trained subjects (peakvo2trainer).
- Wisløff et al. 2007 reported even larger gains in heart-failure patients.
- Generation 100 study (~1,500 elderly Norwegians) confirmed sustained CV benefit.
- More recent cautions: once per week is sufficient; twice can drive overtraining in beginners. Some coaches report 4×4 is "overhyped" and that Billat 30/30 or 400 m repeats at 5k pace produce similar time-at-VO₂max with less stress (dlakecreates).

**Zone 2** (Iñigo San Millán / Attia):

- ~3–4 days/week, 45–90 min each, at the intensity where blood lactate sits at ~1.7–1.9 mmol/L or you can just barely nasal-breathe (Peter Attia #201).
- Builds mitochondrial density and lactate clearance — the base on top of which 4×4 improves VO₂max. Iñigo: "elite athletes spend 80% of training time in zone 2" even if their sport is high-intensity (Chris Masterjohn).

**Attia's "Centenarian Decathlon" four-pillar framework** (Peter Attia #261):

- Zone 2 (3–4 hrs/week), VO₂max work (1×/week), strength (2–3×/week), stability (daily).

**HRV-guided individualization:**

- Nature 2025 study on 28 cyclists found vmHRV (RMSSD) + RHR + subjective well-being, used to gate intensity day-to-day, produced significant gains in FTP and Pmax over 40 days (Nature 2025).
- A 12-week RCT protocol confirmed HRV-guided endurance training produced better VO₂max improvements than fixed periodization (PubMed 32751204).
- Practical rule: if lnRMSSD7d stays in your normal range → hit the planned high-intensity session; if below → swap to zone 2 or rest (Kubios).

**Sauna** (Rhonda Patrick / Laukkanen Finnish data):

- 4–7 sessions/week, 20–30 min at 79–82°C → 40% lower all-cause mortality, 50% lower fatal CVD vs. 1×/week in the Kuopio 20-year cohort (JAMA Intern Med 2015, Peak Saunas).
- Heat exposure raises HSPs, improves endothelial function — plausibly improves PWV. If you have access to a sauna in Pune (many premium gyms do), stack this with your training days.

### 2.3 Realistic magnitude over 8 weeks

CVA is slow. Oura states that their own Ring displays month-over-month CVA views and lifestyle changes "can take several weeks to show a noticeable effect." A shift from 0 to −3/−4 in 8 weeks would place you in the ~top percentile of observed Oura-member improvements. The data points we have:

- **Anecdote 1 (Oura blog):** +7.5 → +3 CVA in 7 weeks with 2×/week cardio/strength + 1 swim (delta −4.5 with concurrent PWV drop 7.6 → 7.3 m/s) (Oura).
- **Anecdote 2 (r/ouraring):** multiple members reporting 3–5 year CVA reductions over similar windows with sustained training.

Your situation is actually favorable: you're already losing weight (86 from 95 kg = ~9 kg lost, ~10% body weight), which directly drops systolic BP and arterial stiffness. The model is: if CVA = 0 because untrained physiology, targeted 8 weeks of Zone 2 + 4×4 + sleep optimization + low sodium + continued weight loss could realistically produce **−2 to −4** — but there is individual noise in the PPG-PWV estimate that can swing ±1 year week-to-week. Track the 14-day rolling average, not the daily number.

### 2.4 Opinionated 8-week CVA protocol

**Weekly schedule** (assuming you're moderately active):

- **Mon:** Zone 2, 60 min (bike/treadmill/outdoor, HR ~70% max)
- **Tue:** Full-body strength, 45 min
- **Wed:** Norwegian 4×4 (only 1×/week — this is the VO₂max stimulus)
- **Thu:** Zone 2, 60 min + mobility/stability
- **Fri:** Strength (push) or rest (gated by HRV score)
- **Sat:** Long Zone 2, 90 min
- **Sun:** Active recovery: walk + sauna 30 min if available

**Nutrition:** Mediterranean-leaning, <2,300 mg sodium/day, 1.6 g/kg protein (~140 g at 86 kg), time-restricted eating 10-hr window if compatible with sleep.

**Sleep:** Prioritize 7.5–8.5 hours in bed; Oura sleep efficiency target >88%; cool bedroom (~19°C).

---

## 3. Self-Hostable Architecture: The Opinionated Stack

### 3.1 Storage — TimescaleDB wins for this use case

The three finalists for personal biometric time-series at your data volumes:

| DB | Strengths | Weaknesses for this use case |
|---|---|---|
| **TimescaleDB** (now TigerData brand, June 2025 rebrand) | Postgres, hypertables + hypercore hybrid row/columnar, continuous aggregates, pgvector coexists, joins with relational data | Not the fastest raw ingest |
| **QuestDB** | 12–36× faster ingest than Influx 3, 16–20× faster analytical queries than Timescale (QuestDB 2026 bench) | Weaker joins, separate system from relational/vector data |
| **InfluxDB 3.0 Core** (Rust rewrite, GA April 2025) | Unlimited cardinality, Arrow/Parquet | New engine, lacks built-in continuous aggregates, 72h retention in Core tier (TigerData 2026 review) |
| **ClickHouse** | Unmatched analytical query speed | Overkill for personal data, heavy ops |

**Recommendation:** TimescaleDB. You have ~86 kg × 365 days of minute-ish data = under 100M rows/year even with heart rate at 5-min resolution — this is laughably small for any of them. What matters is that TimescaleDB lets you put (a) time-series biometrics, (b) relational metadata (interventions, tags, supplement log), and (c) pgvector embeddings of research papers in one Postgres instance, which dramatically simplifies the agent's ability to JOIN "my HRV drop last Wednesday" with "the supplement I started Tuesday" with "similar cases in the literature." QuestDB is faster but this isn't a high-frequency-trading problem.

Enable `timescaledb`, `pgvector`, and `pg_partman` extensions. Use a single hypertable per metric type (`sleep_summaries`, `hr_intraday`, `hrv_intraday`, `activity_met`, `workouts`, `tags`, `interventions`).

### 3.2 Ingestion — Go daemon + Prefect 3

- **Oura sync:** small long-running Go binary that (a) subscribes to webhooks, (b) runs a 3-hourly reconciliation backfill (Oura sometimes revises scores after the fact), (c) writes to TimescaleDB via pgx. Go because you already use it and because it's the ideal language for a sidecar-style network daemon.
- **Secondary sources** (Apple Health exports, CGM, blood tests, PubMed/bioRxiv crawls): Prefect 3 flows. Prefect vs. alternatives 2025:
  - **Airflow 3.0** (April 2025): industry standard, 30M+ monthly downloads, but heavy (ZenML).
  - **Dagster** (Components framework GA Oct 2025): asset-centric, excellent if you're building a data-platform product; overkill here.
  - **Prefect 3:** Pythonic, minimal boilerplate, hybrid-execution, easy self-host. Right weight for personal project.
  - **n8n:** great for no-code webhook chains but not where you want heavy Python analytics.

### 3.3 Backend/API layer

Split the backend by latency sensitivity:

- **Go (Echo or Fiber)** for the public API, Oura webhook receiver, and any user-facing endpoint. Low memory, fast cold start.
- **FastAPI (Python)** for the analytics service that wraps `statsmodels`, `pymc`, `CausalImpact`, `darts`, `sklearn`. The agent calls this service to run a causal-inference check.
- **Next.js App Router** for the dashboard UI — consume both APIs via `tRPC` or plain REST.

### 3.4 Dashboards — Grafana for ops, Evidence.dev for weekly reports

This pairing is the sweet spot for you:

- **Grafana** (70.3k GitHub stars): unbeatable for real-time biometric monitoring, time-series heatmaps, threshold alerting. Native TimescaleDB (Postgres) datasource. Use for "continuous cockpit" dashboards — HRV trend, sleep-score sparkline, training-load, CVA 14-day rolling avg (portalZINE 2025).
- **Evidence.dev:** SQL + Markdown, git-versioned "BI-as-code." Ideal for your weekly narrative report — "This week: CVA ticked to −0.5, HRV recovered after Thursday's 4×4, two intervention tags active" (Basedash 2026 review).

Skip Metabase (too point-and-click), Superset (too heavy), Lightdash (only useful if you have dbt).

### 3.5 Notebook layer — marimo, not Jupyter

marimo stores notebooks as `.py` files, enforces a reactive DAG (no hidden state), and is ideal for version control and LLM coding agents (marimo docs). A 2024 study cited by the marimo team found 36% of Jupyter notebooks on GitHub aren't reproducible; marimo eliminates the root cause. For a dev who values reproducibility and wants Claude Code to be able to read/edit notebooks, marimo is strictly better.

### 3.6 Deployment — Hetzner + Dokploy, hosted near Pune

Your location (Pune) creates real hosting constraints. The best options:

- **Hetzner Cloud** — they now operate in Hillsboro, Oregon; Ashburn, VA; Falkenstein, Nuremberg, Helsinki; and Singapore (Hetzner). Use Singapore (hel1 or sin1 depending on availability) for lowest latency from Pune (typically 60–90 ms). Hetzner is 10–12× cheaper than AWS/Azure for equivalent specs (Hetzner). Indian residents can pay with Aadhaar/PAN-verified cards (mohits.dev).
- **DigitalOcean Bangalore (BLR1)** — best Indian latency but ~2–3× Hetzner pricing.
- **AWS Mumbai (ap-south-1)** — closest hyperscaler region but expensive; worth considering only if you later use managed services.

**Recommended concrete spec:** Hetzner CCX33 (8 dedicated vCPU, 32 GB RAM, 240 GB NVMe SSD) in Singapore for ~€49/month. Runs TimescaleDB + all services comfortably.

**Deployment abstraction — Dokploy over Coolify.** Both are open-source self-hosted PaaS alternatives to Vercel/Heroku. Key 2026 considerations:

- **Coolify** (44.7k stars) has the larger ecosystem but was hit with 11 CVEs in January 2026, three at CVSS 10.0 — root SSH key exposure and privilege escalation issues (virtua.cloud). If you run Coolify, patch past v4.0.0-beta.374 and do not expose the dashboard publicly.
- **Dokploy** (~24k stars, ~32k in March 2026): cleaner Docker-native workflow, 350 MB idle RAM vs. Coolify's 500 MB–1.2 GB, no comparable CVE history. LogRocket's hands-on production review tips to Dokploy (LogRocket).
- **Alternative if you want zero PaaS overhead:** Kamal (37signals' tool) + Docker Compose + Caddy. Absolutely minimal but no GUI.

**Final recommendation:** Hetzner CCX33 Singapore → Dokploy → Caddy for TLS (auto-renewal from Let's Encrypt) → Cloudflare Tunnel in front to avoid exposing the origin IP.

### 3.7 The stack in one diagram

```
                         ┌─────────────────────────────┐
                         │   Oura Cloud API (v2)       │
                         └─────────┬───────────────────┘
                                   │ webhooks + cron
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  Hetzner CCX33 — Singapore — Dokploy (Docker Compose)             │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Go ingest    │  │ FastAPI      │  │ Next.js dashboard    │   │
│  │ daemon (Oura)│  │ analytics    │  │ (App Router + tRPC)  │   │
│  │ + webhooks   │  │ (pymc,       │  │                      │   │
│  └──────┬───────┘  │ CausalImpact)│  └──────────┬───────────┘   │
│         │          └──────┬───────┘             │               │
│         │                 │                     │               │
│         ▼                 ▼                     ▼               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  TimescaleDB 2.x (Postgres 16 + pgvector + timescaledb)    │ │
│  │  Hypertables: hr_intraday, hrv_intraday, sleep, activity,  │ │
│  │  workouts, tags, interventions, bloods, cgm, embeddings    │ │
│  └────────────────────────────────────────────────────────────┘ │
│         ▲                 ▲                     ▲               │
│         │                 │                     │               │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────────┴───────────┐   │
│  │ Grafana      │  │ Evidence.dev │  │ marimo (exploration) │   │
│  │ (operational)│  │ (weekly rpt) │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Prefect 3 (secondary ingestion: Apple Health, CGM,      │   │
│  │  PubMed/bioRxiv, TruDiagnostic, SiPhox)                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Agent runtime: Claude Agent SDK + MCP servers           │   │
│  │  (oura-mcp, pubmed-mcp, timescale-mcp, custom)           │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ TLS via Caddy + Cloudflare Tunnel
                                   ▼
                              You (Pune)
```

---

## 4. The Research Agent Layer

### 4.1 Framework choice — Claude Agent SDK + MCP

State of play as of April 2026:

- **LangGraph 1.0** (stable since October 2025) — mature, graph-first, strong for complex multi-step workflows, best-in-class visual debugging via LangGraph Studio (dev.to 2025 comparison).
- **Pydantic AI v1** (Sept 2025, API-stability commitment) — best developer experience, type-safe, lowest lock-in, ~160 LOC equivalent chat app vs. LangGraph's ~280 (Medium 2026, Speakeasy 2026).
- **Claude Agent SDK** (renamed from Claude Code SDK, Sept 2025) — Python & TypeScript, ships with the exact agent loop and context compaction that powers Claude Code. Native MCP support, built-in tools (Read/Write/Bash/Glob/Grep), subagents, hooks (Anthropic docs).
- **CrewAI** — great for role-based multi-agent but overkill for a single-user system.

**Opinionated choice:** Claude Agent SDK (TypeScript) as the primary orchestrator, because (a) you're a TS/Next.js developer so the SDK integrates cleanly, (b) it already wraps Claude's best tool-use loop with compaction and subagents, (c) MCP is the canonical way to wire Oura, your database, PubMed, etc. Fall back to Pydantic AI in Python if you need strict structured outputs in the analytics path (e.g., a "propose N-of-1 experiment" endpoint that must return a validated JSON schema).

### 4.2 MCP servers to wire up

Already-available MCP servers relevant to your stack:

- **Oura MCP servers** — there are at least four mature implementations:
  - `pokidyshev/oura-mcp` (Python, 15+ tools, OAuth2 token refresh) (Glama).
  - `hemantkamalakar/oura-mcp-server` (18 resources, 20 tools, advanced analytics including circadian rhythm, correlations, anomaly detection) (GitHub).
  - `mitchhankins01/oura-ring-mcp` (Node, OAuth proxy for remote Railway deploy) (mcpservers.org).
  - `gjlumsden/OuraMcp` (.NET, Azure-style CLI login) (LobeHub).
- **PubMed / biomedical MCP** — build your own thin server around NCBI E-utilities + Semantic Scholar API (1 RPS unauthenticated, higher with a free key, Semantic Scholar docs).
- **Your own TimescaleDB MCP** — one read-only tool that executes SQL against the warehouse with row-level safety guards.

### 4.3 RAG setup for personal health knowledge

**Vector store:** pgvector inside the same TimescaleDB, not a separate Qdrant/Weaviate. At your corpus size (tens of thousands of paper abstracts + your journal entries, well under 1M vectors), pgvector HNSW returns in 5–8 ms and beats Elasticsearch across the board (HuggingFace benchmark 2026). Supabase's own benchmarks show pgvector with HNSW outperforming Qdrant on equivalent compute at 99% accuracy (DEV 2026). Only switch to Qdrant if you cross 10M+ vectors — you won't.

**Embeddings for biomedical text:** `NeuML/pubmedbert-base-embeddings` (Hugging Face), a Sentence-Transformers model fine-tuned on PubMed + MeSH that outperforms general-purpose embeddings on biomedical similarity tasks (Hugging Face). Dimension: 768. Run on a CPU; throughput is fine for batch indexing.

For your personal journal and free-text notes, use a general-purpose model (`BAAI/bge-large-en-v1.5` or OpenAI `text-embedding-3-large`) and store in a separate namespace.

### 4.4 Ingestion pipeline for external research

**Prefect flow (runs nightly):**

1. **PubMed** — query E-utilities for your standing topics: `"pulse wave velocity"`, `"cardiovascular age" wearable`, `"heart rate variability" training`, `"VO2 max" longevity`, `zone 2 mitochondria`, etc. Filter to last 30 days to keep fresh.
2. **bioRxiv / medRxiv** — their free API supports `details/bio(med)rxiv/{interval}` queries; pull abstracts in the `physiology` / `sports medicine` / `cardiovascular medicine` categories.
3. **Semantic Scholar** — enrich with citations and recommended papers via `/recommendations/v1/papers/forpaper/{id}` (Semantic Scholar API).
4. **Curated podcasts** — transcripts via YouTube Data API v3 → Whisper → chunk. Sources: Peter Attia's Drive, Huberman Lab, Rhonda Patrick FoundMyFitness, Attia's patient roundups, Bryan Johnson Blueprint updates.
5. **Embed** everything with PubMedBERT (biomedical) or bge-large (general) → insert into `pgvector` with metadata (source, date, authors, DOI).

### 4.5 Trust and citation controls

To keep the agent surfacing peer-reviewed literature rather than blog chatter, enforce:

- **Source weighting in retrieval:** multiply cosine similarity by a source-reliability prior (PubMed=1.0, bioRxiv=0.8, curated-podcast=0.6, blog=0.3).
- **Minimum citation count** for papers older than 2 years (via Semantic Scholar).
- **Retraction Watch API** check before citing a paper.
- **Agent prompt discipline:** system prompt must require (a) inline DOI/PMID, (b) explicit mention of study type (RCT, observational, N-of-1), (c) sample size, (d) whether result is primary or secondary endpoint.
- **LLM-as-judge pass:** after the agent drafts a recommendation, a second Claude call scores it on evidence quality (1–5) and rejects below threshold.

### 4.6 Example agent workflows

**Workflow 1 — "Weekly Sunday Review"** (cron-triggered):

```typescript
// agents/weekly-review.ts
import { query, ClaudeAgentOptions } from '@anthropic-ai/claude-agent-sdk';

await query({
  prompt: `
    1. Call timescale_mcp.get_weekly_summary() for the last 7 days.
    2. Compute CVA trend, HRV 7d avg, sleep efficiency trend, training load.
    3. Flag any anomalies (HRV drop >1.5 SD, temperature deviation >0.5°C,
       resting HR elevated >5 bpm).
    4. Call pubmed_mcp.search() for each anomaly signature.
    5. Cross-reference with active interventions (tags) for the week.
    6. Output: markdown report with 3 hypotheses, each linked to an N-of-1
       experiment proposal (intervention, duration, primary outcome,
       minimum detectable effect).
  `,
  options: {
    mcpServers: {
      oura: { type: 'stdio', command: 'oura-mcp' },
      timescale: { type: 'stdio', command: 'timescale-mcp' },
      pubmed: { type: 'http', url: 'http://localhost:8001/mcp' },
    },
    allowedTools: ['mcp__oura__*', 'mcp__timescale__query', 'mcp__pubmed__*', 'Write'],
    settingSources: ['project'],
  }
});
```

**Workflow 2 — "HRV-drop investigator"** (event-triggered from Grafana alert):

> Given the 3-day HRV average dropped 22% vs. your baseline, search recent literature on HRV recovery protocols, cross-reference with my last 10 days of sleep, workouts, travel, and tag data, and propose the top 3 candidate causes with their falsifiable follow-up test.

**Workflow 3 — "Intervention designer":**

> I'm adding 5 g creatine daily. Propose a 4-week N-of-1 design. Identify which Oura metrics would detect any effect, the expected effect size from literature, and the TimescaleDB query for the CausalImpact pre/post comparison.

---

## 5. Beyond Dashboards: The Frontier

*This is the section that actually matters. Dashboards plateau in value after about a month; everything below compounds.*

### 5.1 Causal inference on personal interventions

The core tool: **CausalImpact**. Brodersen et al. 2015 at Google pioneered Bayesian structural time-series for causal attribution in non-experimental settings (Google Research, CRAN). Given a response series (your HRV, sleep score, CVA) plus control covariates that were not affected by the intervention, CausalImpact fits a BSTS model, predicts the counterfactual, and quantifies the intervention's effect with Bayesian credible intervals.

**Workflow:**

1. For every intervention you start (new supplement, protocol, sauna block), log it as a timestamped row in your `interventions` table.
2. Select response (CVA 14-d rolling) and control covariates that are plausibly independent (e.g., ambient temperature, daylight hours).
3. Run CausalImpact with `pre.period = 30 days prior` and `post.period = 28 days after`.
4. Store the posterior effect size, credible interval, and the impact plot.

Use R via `rpy2` or the Python port `causalimpact` / `tfcausalimpact` (TensorFlow Probability).

**Complementary tools:**

- `pymc` for fully Bayesian hierarchical models (e.g., partial pooling across multiple similar interventions).
- `DoWhy` (Microsoft) for explicit causal-graph specification and refutation tests.
- Interrupted time-series regression (`statsmodels` with segmented breakpoints) for simpler cases.

### 5.2 Predictive modeling

**Forecasting tomorrow's HRV / readiness / illness onset.**

- **Nixtla StatsForecast / MLForecast / NeuralForecast** (single API, blazing fast for AutoARIMA, ETS, LightGBM, N-BEATS, TFT) — ideal for "forecast next 7 days of HRV conditional on planned training load" (Nixtla suite).
- **darts (Unit8)** — unified scikit-learn-like API, excellent anomaly detection module with PyOD wrappers, native handling of past/future covariates (darts GitHub). Best when you want one API across ARIMA, LightGBM, N-BEATS, TFT with conformal prediction intervals.
- **sktime** — more academic, rigorous pipelines, weaker on large panels.

**Specific personal models to build:**

1. **Next-day HRV predictor** — inputs: today's training load, sleep, prior HRV 7-d, ambient temp, stress tags. Output: point forecast + interval. Retrain weekly.
2. **Illness onset warning** — ensemble of anomaly detectors on skin-temperature deviation + RHR + HRV; threshold set by your own historical 95th-percentile false-alarm rate. Laboratories like the Stanford Snyder lab have shown wearable-detected pre-symptomatic infection with 2-day lead time.
3. **Optimal training day recommender** — policy that picks `{hard, moderate, easy, rest}` given predicted HRV and sleep debt; evaluate with counterfactual off-policy estimation.

### 5.3 Digital twin / personal physiology simulator

A heavier project but uniquely valuable: build a state-space model of your physiology. Baseline variables: HRV, RHR, sleep, training load, weight, estimated mitochondrial-function proxy (Zone 2 HR at fixed pace), PWV (CVA). Dynamics learned via Bayesian system identification (`pymc`) or a neural ODE. Once calibrated, you can simulate "what if I add 3 hrs Zone 2 per week for 6 weeks?" and get a distribution over the predicted trajectory — before you commit the time. This is how Bryan Johnson's Blueprint team models his protocol in simulation; you can do a scaled-down personal version.

### 5.4 Integration with wider data

- **CGM** — Over-the-counter options live now:
  - **Dexcom Stelo** (FDA-cleared March 2024, 15-day wear, MARD 8.3%) — for non-insulin adults, integrates with Apple Health and Oura Ring (Not Just a Patch comparison).
  - **Abbott Lingo** (14-day wear, MARD 9.3%, iOS only) — marketed purely for wellness (GoodRx).
  - Both cost ~$89–99/month. Availability in India is still limited but CGMs can be imported or obtained via partner labs.
  - Pipe via `shortcuts-http` or custom scraper into `cgm_readings` hypertable.
- **Apple Health** — use Health Auto Export (iOS app) to push JSON/CSV to a REST endpoint nightly (Personal Science Wiki). For one-time deep exports, HLExport (free iOS app) outputs full HealthKit raw JSON (QS Forum).
- **Blood biomarkers** — in India the `1mg Labs`, `Thyrocare Aarogyam`, or `HealthifyMe` panels cover 60+ markers for ₹2,000–5,000. For a more complete longevity panel, SiPhox Health offers up to 60 markers at-home and provides a REST API for partners (SiPhox). Function Health covers 160+ markers with personalized protocols (Function Health). Parse PDF/CSV outputs into a `bloods` table.
- **Epigenetic age** — TruDiagnostic TruAge COMPLETE analyzes 900,000+ methylation markers, returns DunedinPACE pace-of-aging, OMICmAge, telomere length, immune cell deconvolution, and the age of 11 organ systems (TruDiagnostic). Test every 3–4 months to track intervention response. There's no public API — you'll parse the PDF report manually or OCR it into JSON.
- **Genetics** — 23andMe raw data → Promethease (discontinued) or Nebula Explore. Store variants keyed by `rsid`.
- **Environmental** — PurpleAir public API for local AQI (critical in Pune in winter), `home-assistant` for CO₂ / bedroom temp (Aranet4 BLE sensor).

### 5.5 Longevity-protocol adherence tracker

Materialize each protocol as a set of daily/weekly goals against your data:

- **Attia Centenarian Decathlon:** zone-2 minutes/week, one VO₂max session/week, 3× strength, daily stability.
- **Bryan Johnson Blueprint:** supplement adherence (27–40 compounds in his current "Blueprint Stack" per 2025 updates; 74 compounds across the 7 retail products plus his snake-oil EVOO) (Neurogan, Blueprint protocol page); 2,250-calorie plant-forward diet; sleep window discipline.
- **Rhonda Patrick sauna:** 4+ sessions/week, 20–30 min at 174°F+ (Peak Saunas).
- **San Millán Zone 2:** 3–4 sessions/week, 60–90 min, heart-rate within your personal Z2 band (INSCYD).

A Grafana "Protocol Adherence" dashboard shows each protocol's weekly % compliance as a stacked bar chart.

### 5.6 Voice journaling + NLP

**Workflow:**

1. Record 2-minute morning voice note on iOS Shortcuts → upload to your server.
2. Whisper v3 large (local via whisper.cpp or OpenAI API) → transcript.
3. Claude extracts structured fields: mood (1–10), energy (1–10), symptoms (list), stress triggers (list), subjective sleep (1–10), adherence flags.
4. Insert into `journal_entries` table with embeddings.
5. **Correlation layer:** run rolling Spearman between `mood` and each biometric — this is where you catch "my mood drops 2 days before resting HR spikes."

### 5.7 Computer vision for food logging

Oura's in-app meal logging is OCR + manual; you can do better with your own pipeline:

- Photo → GPT-5-vision or Claude 4 Opus vision with a prompt to estimate portion, food items, and macros.
- Cross-reference against USDA FoodData Central via API for accuracy.
- Store per-meal rows; derive daily sodium, protein, fiber, polyphenol-containing foods.
- Over 30 days you get CGM ↔ meal associations for free.

### 5.8 Personalized research-agent workflows (concrete examples)

- **Sunday "3 Hypotheses" brief:** agent reads the week's biometrics + tags + recent PubMed pulls → generates exactly 3 falsifiable hypotheses, each with a proposed N-of-1 design and power estimate.
- **"What moves my CVA?":** monthly job runs CausalImpact over every tag that has ≥10 days of before/after data → surfaces top 3 movers with CI.
- **Pre-workout gate:** at 6 a.m., agent checks last night's HRV against your rolling 60-day baseline, recommends hard vs. moderate vs. rest for today, and adjusts the planned Zone 2 / 4×4 split accordingly.

### 5.9 Alerting & proactive interventions

Grafana Alerting rules, all wired to Pushover or a Telegram bot:

- `HRV_drop_gt_1.5_sd AND skin_temp_deviation_gt_0.4` → "Possible illness brewing. Switch to Zone 2 only today."
- `resting_hr_elevated_3_consecutive_days AND sleep_score_declining` → "Overtraining signal. Recommend full rest day."
- `sleep_debt_over_5h_in_7d` → "Prioritize early bedtime."
- `CVA_14d_trend_reversed` → "CVA ticked up. Review sodium/sleep/alcohol tags."

### 5.10 Sharing and Open Humans

Open Humans is the open-source quantified-self data exchange maintained by the same community that ran the Quantified Flu study. Their Oura wiki page and the `OpenHumans/qf-heartrate-apple-health` repo demonstrate how to donate anonymized data (Open Humans Wiki, GitHub). You can (a) pull other members' Oura-and-flu data to inform your own illness-onset model, and (b) optionally donate your own de-identified data to help public research.

### 5.11 Physiological experiments to run

- **Breathwork:** 4 weeks of 10-min box-breathing (4-4-4-4) every evening → measure impact on overnight HRV and sleep-onset latency.
- **Wim Hof:** caveat — causes transient sympathetic surge; measure with morning HRV and RHR.
- **Cold exposure:** 11 minutes/week across 2–4 sessions at ≤15°C (Huberman's synthesis) → endpoints: baseline norepinephrine proxy (RHR at rest), mood.
- **Sauna:** build to 4–7 sessions/week at 80°C for 20–30 min; expect HRV benefits and CVA improvement over 8–12 weeks per Finnish cohort data.
- **Zone 2 block periodization:** compare 3 weeks of 5×60-min Z2 + 1 4×4 vs. 3 weeks of 3×90-min Z2 + 1 4×4. Use CausalImpact on the block boundaries.

---

## 6. Concrete 8-Week Roadmap

### Week 1–2 — Data pipeline + dashboard MVP

- **Day 1–2:** Rent Hetzner CCX33 (Singapore), install Dokploy, bring up TimescaleDB 2.x + pgvector, Caddy with Cloudflare Tunnel.
- **Day 3–5:** Build the Go Oura sync daemon (OAuth2 + PAT fallback, webhook receiver, nightly backfill reconciliation). Schema: hypertables for `sleep`, `sleep_intraday_hr`, `sleep_intraday_hrv`, `daily_activity`, `activity_met_minute`, `daily_readiness`, `daily_stress`, `daily_resilience`, `daily_cva`, `daily_spo2`, `workouts`, `enhanced_tags`, `vo2_max`.
- **Day 6–8:** Full historical backfill (Oura returns up to several years). Sanity-check against the app.
- **Day 9–11:** Stand up Grafana, build core dashboards: (1) "Today" (last 24h HR/HRV/activity), (2) "CVA tracker" (14-d rolling + trend arrow), (3) "Training load" (ATL/CTL/TSB from workouts), (4) "Sleep architecture" heatmap.
- **Day 12–14:** Start the physical protocol (§2.4). Begin doing one Norwegian 4×4 session on Wednesdays, three Z2 sessions at 60–90 min, two strength sessions. **This is the single most important week for the CVA goal. Dashboards without protocol execution will not move CVA.**

**Intervention priority** (this matters more than the tooling): by end of Week 2 you should have started training consistently. CVA takes weeks to shift and you only have 8 of them.

### Week 3–4 — Research agent layer

- **Week 3:** Install one of the Oura MCP servers, build a custom TimescaleDB MCP (read-only with a SQL whitelist), set up Claude Agent SDK project. Validate the agent can answer "how did my CVA trend compare to my Wednesday 4×4 compliance this month?"
- **Week 3 ingestion:** Prefect flow for PubMed + bioRxiv nightly pulls. Embed with PubMedBERT into pgvector. Target ~5,000 papers in the cardiovascular/sleep/training space.
- **Week 4:** Wire the "Sunday 3-Hypothesis" workflow. Test the weekly-review agent on real data. Build the "pre-workout gate" alert.
- Keep training at the protocol intensity. Start logging supplements / sleep interventions as tags.

### Week 5–6 — N-of-1 experiment infrastructure

- **Week 5:** `interventions` table + CausalImpact wrapper as a FastAPI endpoint. Start your first formal N-of-1: "Does nightly 800 mg magnesium glycinate improve deep-sleep duration?" (pre = 14 days without, post = 21 days with; response = deep sleep min, control = bedtime consistency).
- **Week 5:** Introduce Apple Health import (Health Auto Export), if you have an iPhone, for walking workouts and extra HR context.
- **Week 6:** First TruDiagnostic TruAge COMPLETE kit (if budget allows) to establish epigenetic baseline. Add `bloods` table; if possible run a basic lipid + CRP + HbA1c + fasting insulin panel in Pune.
- **Week 6:** Build the Evidence.dev weekly report — git-versioned markdown that renders your CVA trend, top interventions, and recent PubMed hits.

### Week 7–8 — Advanced modeling + validation

- **Week 7:** Train the next-day HRV forecaster (StatsForecast AutoARIMA as baseline, darts TFT as stretch). Deploy behind FastAPI.
- **Week 7:** Anomaly detection: darts with rolling z-score + isolation forest for illness detection.
- **Week 8:** Run CausalImpact on the whole 8-week protocol (pre-period = 30 days before Week 1 training began, post-period = Weeks 3–8). Quantify what the intervention moved in CVA with Bayesian credible intervals. This is your personal RCT-equivalent.
- **Week 8:** Repeat Oura 6-min walking test (CardioCapacity) for the second time since Week 1 — expect 3–6% VO₂max increase after 8 weeks of the Norwegian 4×4 + Zone 2 block.
- **Week 8 validation:** Check 14-d rolling CVA. Write up findings in marimo, share publicly if you want.

### Relative-impact priority (most important to least)

1. **Actually doing the training protocol** (Z2 volume + 1 4×4/week, consistently). **70% of the CVA outcome.**
2. **Sleep discipline + sodium restriction.** ~15%.
3. **Continuing weight loss toward 82 kg.** ~10%.
4. **Tooling, dashboards, agents, forecasting.** ~5% of the 8-week goal, but 100% of what you learn and keep forever.

**Do not let the tooling become the project. The goal is −3 CVA.**

---

## 7. Specific Tools & Libraries — Curated List

### Oura-specific

- `hedgertronic/oura-ring` — Python v2 client with full endpoint coverage and pandas helpers.
- `turing-complet/python-ouraring` — alternate Python client with DataFrame ergonomics.
- `@pinta365/oura-api` — TypeScript client for Deno/Bun/Node with OAuth2 and webhook subscription helpers.
- `arzzen/oura` CLI — dynamic OpenAPI-driven CLI for quick data exports.
- Oura v2 Home Assistant integration — 30 sensors if you run HA alongside for environmental data.
- `pokidyshev/oura-mcp`, `hemantkamalakar/oura-mcp-server`, `mitchhankins01/oura-ring-mcp` — MCP servers for Claude integration.
- Airbyte has a built-in Oura connector for ELT if you prefer that pattern (Airbyte docs).

### Quantified self / wider data

- Health Auto Export (iOS) — Apple Health → JSON/MQTT/REST.
- HLExport (iOS) — one-tap full HealthKit JSON.
- Open Humans — data donation / sharing infrastructure.
- Nutrisense — integrates Stelo/Lingo/G7 CGM with a better analytics UI.

### Analysis & modeling

- `statsmodels`, `pymc`, `bambi` — classical and Bayesian stats.
- `CausalImpact` (R via rpy2) or `tfcausalimpact` (TF Probability port) — Bayesian structural time-series (Brodersen 2015).
- `DoWhy`, `EconML` — causal-graph-based estimators.
- `darts` (Unit8) — unified forecasting + anomaly detection API with covariates (darts).
- `statsforecast`, `neuralforecast`, `mlforecast`, `hierarchicalforecast` (Nixtla) — blazing-fast classical + neural forecasting.
- `sktime` — scikit-learn-style time-series pipelines.
- `pyts`, `tsfresh` — feature extraction.
- `scikit-posthocs`, `pingouin` — post-hoc analyses for N-of-1 repeated-measures.

### Agent & LLM

- Claude Agent SDK (Python / TypeScript) — the recommended primary.
- Pydantic AI v1 — structured-output analytics endpoints.
- LangGraph 1.0 — fallback if you need complex branching.
- MCP spec — for building custom servers.
- Langfuse — LLM observability; self-hostable.
- NeuML/pubmedbert-base-embeddings — biomedical embeddings.

### Storage & infra

- TimescaleDB / TigerData — https://www.tigerdata.com (rebrand of Timescale as of June 2025 (TigerData)).
- pgvector — `pgvector/pgvector` Postgres extension.
- QuestDB — if you outgrow Timescale on ingest.
- Dokploy — https://dokploy.com.
- Hetzner Cloud — https://www.hetzner.com/cloud; Singapore region for Pune latency.
- Caddy — automatic HTTPS reverse proxy.
- Cloudflare Tunnel — keeps origin IP private.

### Observability

- Grafana — biometric dashboards + alerting.
- Evidence.dev — weekly markdown reports from SQL.
- marimo — reactive notebooks (marimo).
- Prefect 3 — orchestration (Prefect).

### Blood / genetics / epigenetics

- TruDiagnostic TruAge COMPLETE — 900k methylation markers, OMICmAge, DunedinPACE.
- SiPhox Health — 60-biomarker at-home blood test, REST API for partners.
- Function Health — 160+ biomarker panel with protocols.
- Nebula Genomics — WGS with ongoing variant updates.

---

## Caveats and Honest Uncertainty

- **CVA magnitude.** The only quantified Oura-blog data point is a user going from +7.5 to +3 in 7 weeks with disciplined training; there is no public data on how fast someone at CVA 0 can reach −3 to −4. The NUS/Oura validation paper explicitly reports a mean vascular-age error of 6–7 years against clinical references (Oura/NUS 2025), meaning a single day's CVA reading has substantial noise; trust only the rolling trend.
- **Oura Ring is not a medical device** and is not intended to diagnose, treat, or prevent medical conditions — this applies to CVA, Cardio Capacity, and every other metric (Oura Help). Independent validation showed Oura Gen3/4 led in HRV and RHR accuracy against WHOOP, Garmin, and Polar (Oura 2025) — but this does not mean CVA is clinically actionable; consult a physician for any cardiovascular decision.
- **PAT deprecation status.** The Pinta365 TypeScript client documents that "direct Personal Access Tokens" are deprecated, but Oura's own `https://cloud.ouraring.com/personal-access-tokens` page still issues them and multiple MCP servers depend on them. Treat this as "in flux" and build in OAuth2 support from day one.
- **Blueprint protocol.** Bryan Johnson's regimen has changed repeatedly (he previously took ~100 pills; the current "Blueprint Stack" is 7 products covering 74 compounds plus his Snake Oil EVOO). Numbers like "5.1-year age reversal" are self-reported from his own protocol page and should be treated as anecdote, not RCT evidence.
- **CausalImpact assumptions.** Its validity depends on having control covariates that were not affected by the intervention. For personal data, truly independent controls are hard; interpret credible intervals conservatively and prefer interventions that can be switched on/off multiple times (A/B/A designs) where possible.
- **Sauna access in Pune.** Finnish-style 80°C saunas are rare in India; infrared is more common and operates at ~60°C. Finnish-cohort mortality benefits were established at traditional-sauna temperatures; infrared benefits exist but are less well-quantified (Peak Saunas).

---

## Closing Note

The dashboard is the hobby; the protocol is the point. Build the data pipeline in Weeks 1–2 because you'll compound on it for years, but the CVA goal will be won or lost on whether you execute the one Norwegian 4×4 every Wednesday, three Zone 2 sessions a week, and eight hours of sleep for 56 straight days. Use the agent to hold yourself accountable, the forecasts to plan recovery, and the causal-inference layer to learn which of your interventions actually move your physiology — that compounding loop is the real product you're building, and it outlives any specific 2-month goal.

**Go build.**
