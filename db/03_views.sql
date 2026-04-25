-- Views used by Grafana dashboards
-- Rolling windows, training load (ATL/CTL/TSB), intervention overlay, joined daily view.
-- Requires 01_schema.sql + 02_continuous_aggregates.sql.

BEGIN;

-- ─── CVA rolling averages ──────────────────────────────────────
CREATE OR REPLACE VIEW v_cva_rolling AS
SELECT
  day,
  vascular_age,
  AVG(vascular_age) OVER (
    ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  )::NUMERIC(5,2) AS cva_7d,
  AVG(vascular_age) OVER (
    ORDER BY day ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
  )::NUMERIC(5,2) AS cva_14d,
  AVG(vascular_age) OVER (
    ORDER BY day ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
  )::NUMERIC(5,2) AS cva_30d
FROM daily_cva
ORDER BY day;

-- ─── HRV rolling averages (from sleep-session avg_hrv) ─────────
CREATE OR REPLACE VIEW v_hrv_rolling AS
WITH nightly AS (
  SELECT
    day,
    AVG(average_hrv)::NUMERIC(6,1) AS avg_hrv
  FROM sleep_session
  WHERE type IN ('long_sleep', 'sleep')
  GROUP BY day
)
SELECT
  day,
  avg_hrv,
  AVG(avg_hrv) OVER (
    ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  )::NUMERIC(6,1) AS hrv_7d,
  AVG(avg_hrv) OVER (
    ORDER BY day ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
  )::NUMERIC(6,1) AS hrv_60d,
  STDDEV(avg_hrv) OVER (
    ORDER BY day ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
  )::NUMERIC(6,1) AS hrv_60d_sd
FROM nightly
ORDER BY day;

-- ─── Resting heart rate nightly (min HR from sleep) ────────────
CREATE OR REPLACE VIEW v_rhr_nightly AS
SELECT
  day,
  MIN(lowest_heart_rate) AS rhr
FROM sleep_session
WHERE type IN ('long_sleep', 'sleep')
GROUP BY day
ORDER BY day;

-- ─── Training Stress Score proxy ───────────────────────────────
-- Proxy: TRIMP-like score from MET-minutes. 1 point per minute at med-intensity,
-- 2 points per minute at high-intensity. Calibrate to your own baseline.
CREATE OR REPLACE VIEW v_daily_tss AS
SELECT
  d.day,
  COALESCE(md.high_min,   0) * 2.0
  + COALESCE(md.medium_min, 0) * 1.0
  + COALESCE(md.low_min,    0) * 0.2
  AS tss
FROM (
  SELECT generate_series(
    COALESCE((SELECT MIN(day) FROM daily_activity), CURRENT_DATE - INTERVAL '365 days')::DATE,
    CURRENT_DATE,
    INTERVAL '1 day'
  )::DATE AS day
) d
LEFT JOIN met_daily md ON md.day = d.day::TIMESTAMPTZ
ORDER BY d.day;

-- ─── ATL / CTL / TSB ───────────────────────────────────────────
-- Classic Banister/Coggan model with exponentially-weighted smoothing.
-- ATL (Acute Training Load): 7-day EWMA
-- CTL (Chronic Training Load): 42-day EWMA
-- TSB (Training Stress Balance) = CTL - ATL   (positive = fresh, negative = loaded)
-- Decay factor alpha = 2 / (N+1) for an N-day EWMA.
CREATE OR REPLACE VIEW v_training_load AS
WITH RECURSIVE tss AS (
  SELECT day, tss, ROW_NUMBER() OVER (ORDER BY day) AS rn
  FROM v_daily_tss
),
load AS (
  -- Base case: first day, ATL=CTL=TSS
  SELECT
    rn, day, tss,
    tss::NUMERIC AS atl,
    tss::NUMERIC AS ctl
  FROM tss WHERE rn = 1

  UNION ALL

  SELECT
    t.rn, t.day, t.tss,
    (t.tss * (2.0/(7+1))  + prev.atl * (1 - 2.0/(7+1)))::NUMERIC  AS atl,
    (t.tss * (2.0/(42+1)) + prev.ctl * (1 - 2.0/(42+1)))::NUMERIC AS ctl
  FROM tss t
  JOIN load prev ON prev.rn = t.rn - 1
)
SELECT
  day,
  tss::NUMERIC(6,1)            AS tss,
  atl::NUMERIC(6,1)            AS atl,
  ctl::NUMERIC(6,1)            AS ctl,
  (ctl - atl)::NUMERIC(6,1)    AS tsb
FROM load
ORDER BY day;

-- ─── Joined daily view (convenience for multi-panel dashboards) ─
CREATE OR REPLACE VIEW v_daily AS
SELECT
  d.day,
  cva.vascular_age,
  cr.cva_14d,
  s.score        AS sleep_score,
  s.efficiency   AS sleep_efficiency,
  s.total_sleep  AS sleep_total_sec,
  s.deep_sleep   AS deep_sleep_sec,
  s.rem_sleep    AS rem_sleep_sec,
  r.score        AS readiness_score,
  r.temperature_deviation,
  r.resting_heart_rate AS readiness_rhr,
  a.score        AS activity_score,
  a.steps,
  a.active_calories,
  hr.hrv_7d,
  hr.avg_hrv,
  rhr.rhr        AS nightly_rhr,
  tl.atl, tl.ctl, tl.tsb, tl.tss
FROM (
  SELECT generate_series(
    COALESCE((SELECT MIN(day) FROM daily_cva), CURRENT_DATE - INTERVAL '90 days')::DATE,
    CURRENT_DATE,
    INTERVAL '1 day'
  )::DATE AS day
) d
LEFT JOIN daily_cva        cva ON cva.day = d.day
LEFT JOIN v_cva_rolling    cr  ON cr.day  = d.day
LEFT JOIN daily_sleep      s   ON s.day   = d.day
LEFT JOIN daily_readiness  r   ON r.day   = d.day
LEFT JOIN daily_activity   a   ON a.day   = d.day
LEFT JOIN v_hrv_rolling    hr  ON hr.day  = d.day
LEFT JOIN v_rhr_nightly    rhr ON rhr.day = d.day
LEFT JOIN v_training_load  tl  ON tl.day  = d.day
ORDER BY d.day;

-- ─── Active interventions per day (for overlay annotations) ────
CREATE OR REPLACE VIEW v_active_interventions AS
SELECT
  i.id,
  i.name,
  i.category,
  i.start_day,
  COALESCE(i.end_day, CURRENT_DATE) AS end_day,
  i.dose,
  i.notes
FROM intervention i
ORDER BY start_day DESC;

COMMIT;
