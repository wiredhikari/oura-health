-- TimescaleDB continuous aggregates for fast dashboard queries
-- Requires 01_schema.sql to have been applied.

BEGIN;

-- ─── Hourly HR rollup ──────────────────────────────────────────
DROP MATERIALIZED VIEW IF EXISTS hr_hourly CASCADE;

CREATE MATERIALIZED VIEW hr_hourly
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', ts) AS hour,
  source,
  AVG(bpm)::INT   AS avg_bpm,
  MIN(bpm)        AS min_bpm,
  MAX(bpm)        AS max_bpm,
  COUNT(*)        AS samples
FROM hr_intraday
GROUP BY 1, 2
WITH NO DATA;

SELECT add_continuous_aggregate_policy('hr_hourly',
  start_offset => INTERVAL '90 days',
  end_offset   => INTERVAL '1 hour',
  schedule_interval => INTERVAL '30 minutes',
  if_not_exists => TRUE);

-- ─── Daily HRV summary (sleep-only HRV) ────────────────────────
DROP MATERIALIZED VIEW IF EXISTS hrv_daily CASCADE;

CREATE MATERIALIZED VIEW hrv_daily
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 day', ts) AS day,
  AVG(rmssd)::NUMERIC(6,1) AS avg_hrv,
  MIN(rmssd)               AS min_hrv,
  MAX(rmssd)               AS max_hrv,
  COUNT(*)                 AS samples
FROM hrv_intraday
GROUP BY 1
WITH NO DATA;

SELECT add_continuous_aggregate_policy('hrv_daily',
  start_offset => INTERVAL '180 days',
  end_offset   => INTERVAL '12 hours',
  schedule_interval => INTERVAL '1 hour',
  if_not_exists => TRUE);

-- ─── Daily MET-minute summary by intensity ─────────────────────
-- Oura classification: sedentary <1.5, low 1.5-3, medium 3-6, high ≥6
DROP MATERIALIZED VIEW IF EXISTS met_daily CASCADE;

CREATE MATERIALIZED VIEW met_daily
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 day', ts) AS day,
  SUM(CASE WHEN met >= 6    THEN 1 ELSE 0 END) AS high_min,
  SUM(CASE WHEN met >= 3 AND met < 6 THEN 1 ELSE 0 END) AS medium_min,
  SUM(CASE WHEN met >= 1.5 AND met < 3 THEN 1 ELSE 0 END) AS low_min,
  SUM(CASE WHEN met < 1.5   THEN 1 ELSE 0 END) AS sedentary_min,
  AVG(met)::NUMERIC(4,2)                        AS avg_met,
  COUNT(*)                                      AS samples
FROM activity_met
GROUP BY 1
WITH NO DATA;

SELECT add_continuous_aggregate_policy('met_daily',
  start_offset => INTERVAL '180 days',
  end_offset   => INTERVAL '12 hours',
  schedule_interval => INTERVAL '1 hour',
  if_not_exists => TRUE);

COMMIT;

-- Initial refresh — run after schema is loaded and data is ingested.
-- CALL refresh_continuous_aggregate('hr_hourly', NULL, NULL);
-- CALL refresh_continuous_aggregate('hrv_daily', NULL, NULL);
-- CALL refresh_continuous_aggregate('met_daily', NULL, NULL);
