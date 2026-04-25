"""SQL queries — kept here so the LLM tool layer and the REST routes share them."""

from datetime import date, timedelta
from typing import Any

from . import db


def today_summary() -> dict[str, Any]:
    """Headline numbers for the Today page."""
    row = db.fetch_one(
        """
        WITH latest AS (
          SELECT
            (SELECT vascular_age FROM daily_cva ORDER BY day DESC LIMIT 1)        AS cva,
            (SELECT day          FROM daily_cva ORDER BY day DESC LIMIT 1)        AS cva_day,
            (SELECT score        FROM daily_sleep      ORDER BY day DESC LIMIT 1) AS sleep_score,
            (SELECT score        FROM daily_readiness  ORDER BY day DESC LIMIT 1) AS readiness_score,
            (SELECT score        FROM daily_activity   ORDER BY day DESC LIMIT 1) AS activity_score,
            (SELECT total_sleep  FROM daily_sleep      ORDER BY day DESC LIMIT 1) AS total_sleep_min,
            (SELECT deep_sleep   FROM daily_sleep      ORDER BY day DESC LIMIT 1) AS deep_sleep_min,
            (SELECT rem_sleep    FROM daily_sleep      ORDER BY day DESC LIMIT 1) AS rem_sleep_min,
            (SELECT resting_heart_rate FROM daily_readiness ORDER BY day DESC LIMIT 1) AS rhr,
            (SELECT temperature_deviation FROM daily_readiness ORDER BY day DESC LIMIT 1) AS temp_dev,
            (SELECT steps        FROM daily_activity   ORDER BY day DESC LIMIT 1) AS steps,
            (SELECT active_calories FROM daily_activity ORDER BY day DESC LIMIT 1) AS active_kcal
        )
        SELECT * FROM latest
        """
    )
    return row or {}


def cva_trend(days: int = 90) -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT day, vascular_age,
               AVG(vascular_age) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS cva_7d,
               AVG(vascular_age) OVER (ORDER BY day ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS cva_14d
        FROM daily_cva
        WHERE day >= CURRENT_DATE - %s::int
        ORDER BY day
        """,
        (days,),
    )


def cva_delta_7d() -> float | None:
    row = db.fetch_one(
        """
        WITH t AS (
          SELECT day, vascular_age,
                 AVG(vascular_age) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS cva_7d
          FROM daily_cva
          ORDER BY day DESC
          LIMIT 14
        )
        SELECT (MAX(CASE WHEN row = 1 THEN cva_7d END)
              - MAX(CASE WHEN row = 8 THEN cva_7d END)) AS delta
        FROM (SELECT day, cva_7d, ROW_NUMBER() OVER (ORDER BY day DESC) AS row FROM t) r
        """
    )
    return float(row["delta"]) if row and row.get("delta") is not None else None


def hr_intraday_last_24h() -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT ts, bpm, source
        FROM hr_intraday
        WHERE ts > NOW() - INTERVAL '24 hours'
        ORDER BY ts
        """
    )


def hrv_last_night() -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT ts, rmssd
        FROM hrv_intraday
        WHERE ts > NOW() - INTERVAL '14 hours'
        ORDER BY ts
        """
    )


def daily_join_window(days: int = 30) -> list[dict[str, Any]]:
    """Wide daily join — used to build LLM context."""
    return db.fetch_all(
        """
        SELECT
          c.day,
          c.vascular_age,
          s.score        AS sleep_score,
          s.total_sleep,
          s.deep_sleep,
          s.rem_sleep,
          s.efficiency,
          r.score        AS readiness_score,
          r.resting_heart_rate,
          r.hrv_balance,
          r.temperature_deviation,
          a.score        AS activity_score,
          a.steps,
          a.active_calories,
          stress.stress_high,
          stress.recovery_high,
          rs.level       AS resilience_level
        FROM daily_cva c
        LEFT JOIN daily_sleep      s      ON s.day      = c.day
        LEFT JOIN daily_readiness  r      ON r.day      = c.day
        LEFT JOIN daily_activity   a      ON a.day      = c.day
        LEFT JOIN daily_stress     stress ON stress.day = c.day
        LEFT JOIN daily_resilience rs     ON rs.day     = c.day
        WHERE c.day >= CURRENT_DATE - %s::int
        ORDER BY c.day
        """,
        (days,),
    )


def interventions_active() -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT id, name, category, start_day, end_day, dose, notes
        FROM intervention
        WHERE end_day IS NULL OR end_day >= CURRENT_DATE - 30
        ORDER BY start_day DESC
        """
    )


def recent_food(days: int = 7) -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT id, ts, day, meal, description, calories, protein_g, carbs_g, fat_g, notes
        FROM food_log
        WHERE day >= CURRENT_DATE - %s::int
        ORDER BY ts DESC
        """,
        (days,),
    )


def recent_supplements(days: int = 7) -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT id, ts, day, name, dose, notes
        FROM supplement_log
        WHERE day >= CURRENT_DATE - %s::int
        ORDER BY ts DESC
        """,
        (days,),
    )


def recent_workouts(days: int = 14) -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT id, activity, start_datetime, end_datetime, calories,
               distance, intensity, label, source, day
        FROM workout
        WHERE day >= CURRENT_DATE - %s::int
        ORDER BY start_datetime DESC
        """,
        (days,),
    )


def latest_digest() -> dict[str, Any] | None:
    return db.fetch_one(
        """
        SELECT id, week_start, week_end, markdown, emailed_at, created_at
        FROM digest
        ORDER BY week_start DESC
        LIMIT 1
        """
    )


def all_digests() -> list[dict[str, Any]]:
    return db.fetch_all(
        """
        SELECT id, week_start, week_end, emailed_at, created_at
        FROM digest
        ORDER BY week_start DESC
        """
    )
