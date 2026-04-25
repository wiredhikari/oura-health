"""On-startup migrations.

Apply 04_v2_schema.sql at boot — idempotent, so safe to run every time.
The first deploy bakes it into the DB; subsequent boots no-op.

This exists because Railway's persistent volume means the TimescaleDB
init scripts only ever run on the very first boot.
"""

from __future__ import annotations

import logging
import pathlib

from . import db

log = logging.getLogger("api.migrations")

MIGRATION = """
-- Inlined from sql/04_v2_schema.sql — keep in sync.
CREATE TABLE IF NOT EXISTS food_log (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  day         DATE        NOT NULL,
  meal        TEXT,
  description TEXT NOT NULL,
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
  name        TEXT        NOT NULL,
  dose        TEXT,
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_supp_log_day  ON supplement_log (day DESC);
CREATE INDEX IF NOT EXISTS idx_supp_log_name ON supplement_log (name);

CREATE TABLE IF NOT EXISTS chat_message (
  id          BIGSERIAL PRIMARY KEY,
  session_id  TEXT NOT NULL,
  role        TEXT NOT NULL,
  content     TEXT NOT NULL,
  tokens_in   INTEGER,
  tokens_out  INTEGER,
  model       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_session_created
  ON chat_message (session_id, created_at);

CREATE TABLE IF NOT EXISTS digest (
  id          BIGSERIAL PRIMARY KEY,
  week_start  DATE NOT NULL,
  week_end    DATE NOT NULL,
  markdown    TEXT NOT NULL,
  emailed_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (week_start, week_end)
);
CREATE INDEX IF NOT EXISTS idx_digest_week ON digest (week_start DESC);

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

CREATE TABLE IF NOT EXISTS meta (
  key         TEXT PRIMARY KEY,
  value       JSONB NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def apply() -> None:
    """Run the V2 migration. Safe to call on every boot."""
    log.info("applying V2 schema migration")
    with db.conn() as c, c.cursor() as cur:
        cur.execute(MIGRATION)
    log.info("V2 schema migration done")
