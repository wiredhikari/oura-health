-- Oura → TimescaleDB · V2 schema additions
-- Adds: manual food / supplement logging, AI chat history,
--       weather (Phase 2), and a meta key/value table.
-- Idempotent: safe to re-run.

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- Manual logging — what you put in your body
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS food_log (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  day         DATE        NOT NULL,
  meal        TEXT,                       -- 'breakfast'|'lunch'|'dinner'|'snack'|null
  description TEXT NOT NULL,              -- free-form ("oats + banana + 30g whey")
  calories    INTEGER,
  protein_g   NUMERIC,
  carbs_g     NUMERIC,
  fat_g       NUMERIC,
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_food_log_day ON food_log (day DESC);
CREATE INDEX IF NOT EXISTS idx_food_log_ts  ON food_log (ts DESC);

CREATE TABLE IF NOT EXISTS supplement_log (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  day         DATE        NOT NULL,
  name        TEXT        NOT NULL,        -- 'magnesium glycinate', 'creatine', etc.
  dose        TEXT,                        -- '400 mg', '5 g'
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_supp_log_day  ON supplement_log (day DESC);
CREATE INDEX IF NOT EXISTS idx_supp_log_name ON supplement_log (name);

-- ─────────────────────────────────────────────────────────────
-- AI assistant — chat history (so the assistant has context across sessions)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS chat_message (
  id          BIGSERIAL PRIMARY KEY,
  session_id  TEXT        NOT NULL,        -- groups a conversation
  role        TEXT        NOT NULL,        -- 'user' | 'assistant' | 'system'
  content     TEXT        NOT NULL,
  tokens_in   INTEGER,
  tokens_out  INTEGER,
  model       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_session_created
  ON chat_message (session_id, created_at);

-- One row per generated weekly digest, kept for audit + re-display in the UI.
CREATE TABLE IF NOT EXISTS digest (
  id          BIGSERIAL PRIMARY KEY,
  week_start  DATE        NOT NULL,
  week_end    DATE        NOT NULL,
  markdown    TEXT        NOT NULL,
  emailed_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (week_start, week_end)
);
CREATE INDEX IF NOT EXISTS idx_digest_week ON digest (week_start DESC);

-- ─────────────────────────────────────────────────────────────
-- Weather / AQI (populated in Phase 2 by a weather sync job)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS weather_daily (
  day              DATE PRIMARY KEY,
  temp_min_c       NUMERIC,
  temp_max_c       NUMERIC,
  humidity_avg     NUMERIC,
  pressure_avg     NUMERIC,
  wind_max_kmh     NUMERIC,
  precip_mm        NUMERIC,
  aqi_avg          INTEGER,
  pm25_avg         NUMERIC,
  pm10_avg         NUMERIC,
  source           TEXT,
  ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- Generic key/value bag — used for things like "last digest sent"
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS meta (
  key         TEXT PRIMARY KEY,
  value       JSONB NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- Convenience view — daily intake summary, for the LLM prompt
-- ─────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW v_daily_intake AS
SELECT
  d.day,
  COALESCE(SUM(f.calories), 0)                    AS calories_total,
  COALESCE(SUM(f.protein_g), 0)                   AS protein_g_total,
  COALESCE(SUM(f.carbs_g), 0)                     AS carbs_g_total,
  COALESCE(SUM(f.fat_g), 0)                       AS fat_g_total,
  COUNT(DISTINCT f.id)                            AS meals_logged,
  ARRAY_AGG(DISTINCT s.name) FILTER (WHERE s.name IS NOT NULL) AS supplements
FROM (
  SELECT day FROM food_log
  UNION
  SELECT day FROM supplement_log
) d
LEFT JOIN food_log       f ON f.day = d.day
LEFT JOIN supplement_log s ON s.day = d.day
GROUP BY d.day
ORDER BY d.day DESC;

COMMIT;
