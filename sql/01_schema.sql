-- Oura → TimescaleDB schema
-- Tested against Postgres 16 + TimescaleDB 2.14+ + pgvector 0.7+
-- Run as:  psql -f 01_schema.sql
-- Idempotent: safe to re-run.

BEGIN;

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgvector;

-- ─────────────────────────────────────────────────────────────
-- Daily summary tables (one row per UTC day, no hypertable needed)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_cva (
  day             DATE PRIMARY KEY,
  vascular_age    NUMERIC,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_sleep (
  day             DATE PRIMARY KEY,
  score           INTEGER,
  deep_sleep      INTEGER,
  efficiency      INTEGER,
  latency         INTEGER,
  rem_sleep       INTEGER,
  restfulness     INTEGER,
  timing          INTEGER,
  total_sleep     INTEGER,
  day_timestamp   TIMESTAMPTZ,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_readiness (
  day                         DATE PRIMARY KEY,
  score                       INTEGER,
  temperature_deviation       NUMERIC,
  temperature_trend_deviation NUMERIC,
  activity_balance            INTEGER,
  body_temperature            INTEGER,
  hrv_balance                 INTEGER,
  previous_day_activity       INTEGER,
  previous_night              INTEGER,
  recovery_index              INTEGER,
  resting_heart_rate          INTEGER,
  sleep_balance               INTEGER,
  day_timestamp               TIMESTAMPTZ,
  ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_activity (
  day                           DATE PRIMARY KEY,
  score                         INTEGER,
  active_calories               INTEGER,
  total_calories                INTEGER,
  steps                         INTEGER,
  equivalent_walking_distance   INTEGER,
  target_calories               INTEGER,
  target_meters                 INTEGER,
  high_activity_met_minutes     INTEGER,
  medium_activity_met_minutes   INTEGER,
  low_activity_met_minutes      INTEGER,
  sedentary_met_minutes         INTEGER,
  non_wear_time                 INTEGER,
  inactivity_alerts             INTEGER,
  resting_time                  INTEGER,
  day_timestamp                 TIMESTAMPTZ,
  ingested_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_stress (
  day                   DATE PRIMARY KEY,
  stress_high           INTEGER,
  recovery_high         INTEGER,
  day_summary           TEXT,
  ingested_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_resilience (
  day               DATE PRIMARY KEY,
  level             TEXT,
  sleep_recovery    NUMERIC,
  daytime_recovery  NUMERIC,
  stress            NUMERIC,
  ingested_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_spo2 (
  day                             DATE PRIMARY KEY,
  average                         NUMERIC,
  breathing_disturbance_index     NUMERIC,
  ingested_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vo2_max (
  day             DATE PRIMARY KEY,
  vo2_max         NUMERIC,
  measurement_ts  TIMESTAMPTZ,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- Sleep session detail
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sleep_session (
  id                        TEXT PRIMARY KEY,
  day                       DATE NOT NULL,
  type                      TEXT,
  bedtime_start             TIMESTAMPTZ NOT NULL,
  bedtime_end               TIMESTAMPTZ NOT NULL,
  time_in_bed               INTEGER,     -- seconds
  total_sleep_duration      INTEGER,
  awake_time                INTEGER,
  deep_sleep_duration       INTEGER,
  light_sleep_duration      INTEGER,
  rem_sleep_duration        INTEGER,
  latency                   INTEGER,
  efficiency                INTEGER,
  average_heart_rate        NUMERIC,
  lowest_heart_rate         INTEGER,
  average_hrv               NUMERIC,
  average_breath            NUMERIC,
  sleep_phase_5_min         TEXT,        -- encoded as '1'=deep, '2'=light, '3'=rem, '4'=awake
  ingested_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sleep_session_day ON sleep_session (day DESC);

-- ─────────────────────────────────────────────────────────────
-- Hypertables: intraday time-series
-- ─────────────────────────────────────────────────────────────

-- Heart rate, 5-minute aggregates from Oura (sleep + daytime)
CREATE TABLE IF NOT EXISTS hr_intraday (
  ts        TIMESTAMPTZ NOT NULL,
  bpm       SMALLINT    NOT NULL,
  source    TEXT        NOT NULL     -- 'sleep'|'awake'|'workout'|'session'|'rest_mode'
);
SELECT create_hypertable('hr_intraday', 'ts',
                         chunk_time_interval => INTERVAL '7 days',
                         if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_hr_source_ts ON hr_intraday (source, ts DESC);

-- HRV (RMSSD), 5-minute during sleep
CREATE TABLE IF NOT EXISTS hrv_intraday (
  ts          TIMESTAMPTZ NOT NULL,
  rmssd       SMALLINT    NOT NULL,
  session_id  TEXT
);
SELECT create_hypertable('hrv_intraday', 'ts',
                         chunk_time_interval => INTERVAL '7 days',
                         if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_hrv_session ON hrv_intraday (session_id, ts);

-- Per-minute MET values
CREATE TABLE IF NOT EXISTS activity_met (
  ts    TIMESTAMPTZ NOT NULL,
  met   NUMERIC     NOT NULL,
  day   DATE        NOT NULL
);
SELECT create_hypertable('activity_met', 'ts',
                         chunk_time_interval => INTERVAL '14 days',
                         if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_met_day ON activity_met (day);

-- ─────────────────────────────────────────────────────────────
-- Workouts & tags
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS workout (
  id              TEXT PRIMARY KEY,
  activity        TEXT,
  start_datetime  TIMESTAMPTZ NOT NULL,
  end_datetime    TIMESTAMPTZ NOT NULL,
  calories        NUMERIC,
  distance        NUMERIC,
  intensity       TEXT,            -- 'easy'|'moderate'|'hard'
  label           TEXT,
  source          TEXT,            -- 'manual'|'autodetected'|'confirmed'|'workout_heart_rate'
  day             DATE NOT NULL,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_workout_day ON workout (day DESC);
CREATE INDEX IF NOT EXISTS idx_workout_start ON workout (start_datetime DESC);

-- Enhanced tags (replacement for deprecated /tag)
CREATE TABLE IF NOT EXISTS enhanced_tag (
  id              TEXT PRIMARY KEY,
  tag_type_code   TEXT,
  start_day       DATE,
  end_day         DATE,
  start_time      TIMESTAMPTZ,
  end_time        TIMESTAMPTZ,
  comment         TEXT,
  custom_name     TEXT,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tag_start ON enhanced_tag (start_day DESC);
CREATE INDEX IF NOT EXISTS idx_tag_code ON enhanced_tag (tag_type_code);

-- ─────────────────────────────────────────────────────────────
-- User-managed experiment log (populated by you, not by Oura)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS intervention (
  id          BIGSERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  category    TEXT,              -- 'supplement'|'training'|'sleep'|'diet'|'environmental'
  start_day   DATE NOT NULL,
  end_day     DATE,              -- NULL = still active
  dose        TEXT,
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_intervention_start ON intervention (start_day DESC);

COMMIT;
