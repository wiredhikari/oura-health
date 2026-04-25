"""
Minimal Oura → TimescaleDB sync.

Pulls:
  - daily_cardiovascular_age, daily_sleep, daily_readiness, daily_activity,
    daily_stress, daily_resilience, daily_spo2, vo2_max
  - sleep sessions + their intraday HR/HRV arrays
  - workouts, enhanced_tags
  - daytime HR (/heartrate, 5-min aggregates)

Env vars required:
  OURA_PAT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
  POSTGRES_HOST (default: timescaledb), POSTGRES_PORT (default: 5432),
  BACKFILL_DAYS (default: 730 on first run, 7 thereafter)

Idempotent. Uses ON CONFLICT upserts.
"""

from __future__ import annotations
import os, sys, json, time, logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import requests
import psycopg
from psycopg.types.json import Json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("oura-sync")

OURA_BASE = "https://api.ouraring.com/v2/usercollection"
TOKEN = os.environ["OURA_PAT"]

def db():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "timescaledb"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )

def oura_get(path: str, params: dict | None = None) -> Iterable[dict]:
    """Yield all records from a paginated Oura v2 endpoint."""
    url = f"{OURA_BASE}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    params = dict(params or {})
    backoff = 1.0
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 429:
            log.warning("rate-limited, sleeping %.1fs", backoff)
            time.sleep(backoff); backoff = min(backoff * 2, 60); continue
        r.raise_for_status()
        body = r.json()
        for item in body.get("data", []):
            yield item
        nxt = body.get("next_token")
        if not nxt:
            return
        params["next_token"] = nxt

def upsert(cur, sql: str, rows: list[tuple]):
    if not rows: return
    cur.executemany(sql, rows)
    log.info("  ↳ upserted %d rows", len(rows))

# ─── Daily collections ──────────────────────────────────────────────
def sync_daily_cva(cur, start: date, end: date):
    log.info("daily_cardiovascular_age %s → %s", start, end)
    rows = []
    for it in oura_get("/daily_cardiovascular_age",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        rows.append((it["day"], it.get("vascular_age")))
    upsert(cur,
        "INSERT INTO daily_cva (day, vascular_age) VALUES (%s, %s) "
        "ON CONFLICT (day) DO UPDATE SET vascular_age=EXCLUDED.vascular_age, ingested_at=NOW()",
        rows)

def sync_daily_sleep(cur, start, end):
    log.info("daily_sleep %s → %s", start, end)
    rows = []
    for it in oura_get("/daily_sleep",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        c = it.get("contributors") or {}
        rows.append((it["day"], it.get("score"),
                     c.get("deep_sleep"), c.get("efficiency"), c.get("latency"),
                     c.get("rem_sleep"), c.get("restfulness"), c.get("timing"),
                     c.get("total_sleep"), it.get("timestamp")))
    upsert(cur,
        """INSERT INTO daily_sleep
           (day, score, deep_sleep, efficiency, latency, rem_sleep,
            restfulness, timing, total_sleep, day_timestamp)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET
             score=EXCLUDED.score, deep_sleep=EXCLUDED.deep_sleep,
             efficiency=EXCLUDED.efficiency, latency=EXCLUDED.latency,
             rem_sleep=EXCLUDED.rem_sleep, restfulness=EXCLUDED.restfulness,
             timing=EXCLUDED.timing, total_sleep=EXCLUDED.total_sleep,
             day_timestamp=EXCLUDED.day_timestamp, ingested_at=NOW()""",
        rows)

def sync_daily_readiness(cur, start, end):
    log.info("daily_readiness %s → %s", start, end)
    rows = []
    for it in oura_get("/daily_readiness",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        c = it.get("contributors") or {}
        rows.append((it["day"], it.get("score"),
                     it.get("temperature_deviation"),
                     it.get("temperature_trend_deviation"),
                     c.get("activity_balance"), c.get("body_temperature"),
                     c.get("hrv_balance"), c.get("previous_day_activity"),
                     c.get("previous_night"), c.get("recovery_index"),
                     c.get("resting_heart_rate"), c.get("sleep_balance"),
                     it.get("timestamp")))
    upsert(cur,
        """INSERT INTO daily_readiness
           (day, score, temperature_deviation, temperature_trend_deviation,
            activity_balance, body_temperature, hrv_balance,
            previous_day_activity, previous_night, recovery_index,
            resting_heart_rate, sleep_balance, day_timestamp)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET
             score=EXCLUDED.score,
             temperature_deviation=EXCLUDED.temperature_deviation,
             temperature_trend_deviation=EXCLUDED.temperature_trend_deviation,
             activity_balance=EXCLUDED.activity_balance,
             body_temperature=EXCLUDED.body_temperature,
             hrv_balance=EXCLUDED.hrv_balance,
             previous_day_activity=EXCLUDED.previous_day_activity,
             previous_night=EXCLUDED.previous_night,
             recovery_index=EXCLUDED.recovery_index,
             resting_heart_rate=EXCLUDED.resting_heart_rate,
             sleep_balance=EXCLUDED.sleep_balance,
             day_timestamp=EXCLUDED.day_timestamp,
             ingested_at=NOW()""",
        rows)

def sync_daily_activity(cur, start, end):
    log.info("daily_activity %s → %s", start, end)
    act_rows, met_rows = [], []
    for it in oura_get("/daily_activity",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        act_rows.append((it["day"], it.get("score"),
                         it.get("active_calories"), it.get("total_calories"),
                         it.get("steps"), it.get("equivalent_walking_distance"),
                         it.get("target_calories"), it.get("target_meters"),
                         it.get("high_activity_met_minutes"),
                         it.get("medium_activity_met_minutes"),
                         it.get("low_activity_met_minutes"),
                         it.get("sedentary_met_minutes"),
                         it.get("non_wear_time"), it.get("inactivity_alerts"),
                         it.get("resting_time"), it.get("timestamp")))
        # per-minute MET array
        met = (it.get("met") or {})
        items, interval, start_ts = met.get("items"), met.get("interval"), met.get("timestamp")
        if items and interval and start_ts:
            t0 = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
            for i, v in enumerate(items):
                if v is None: continue
                met_rows.append((t0 + timedelta(seconds=i * interval), float(v), it["day"]))

    upsert(cur,
        """INSERT INTO daily_activity
           (day, score, active_calories, total_calories, steps,
            equivalent_walking_distance, target_calories, target_meters,
            high_activity_met_minutes, medium_activity_met_minutes,
            low_activity_met_minutes, sedentary_met_minutes,
            non_wear_time, inactivity_alerts, resting_time, day_timestamp)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET
             score=EXCLUDED.score, active_calories=EXCLUDED.active_calories,
             total_calories=EXCLUDED.total_calories, steps=EXCLUDED.steps,
             equivalent_walking_distance=EXCLUDED.equivalent_walking_distance,
             target_calories=EXCLUDED.target_calories,
             target_meters=EXCLUDED.target_meters,
             high_activity_met_minutes=EXCLUDED.high_activity_met_minutes,
             medium_activity_met_minutes=EXCLUDED.medium_activity_met_minutes,
             low_activity_met_minutes=EXCLUDED.low_activity_met_minutes,
             sedentary_met_minutes=EXCLUDED.sedentary_met_minutes,
             non_wear_time=EXCLUDED.non_wear_time,
             inactivity_alerts=EXCLUDED.inactivity_alerts,
             resting_time=EXCLUDED.resting_time,
             day_timestamp=EXCLUDED.day_timestamp,
             ingested_at=NOW()""",
        act_rows)
    # MET: insert, tolerate duplicates silently (intraday hypertable, no PK)
    if met_rows:
        # Delete the days we're re-inserting so we don't duplicate
        days = sorted({r[2] for r in met_rows})
        cur.execute("DELETE FROM activity_met WHERE day = ANY(%s)", (days,))
        cur.executemany(
            "INSERT INTO activity_met (ts, met, day) VALUES (%s, %s, %s)",
            met_rows)
        log.info("  ↳ inserted %d MET minute samples", len(met_rows))

def sync_daily_stress(cur, start, end):
    log.info("daily_stress %s → %s", start, end)
    rows = []
    for it in oura_get("/daily_stress",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        rows.append((it["day"], it.get("stress_high"), it.get("recovery_high"),
                     it.get("day_summary")))
    upsert(cur,
        """INSERT INTO daily_stress (day, stress_high, recovery_high, day_summary)
           VALUES (%s,%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET
             stress_high=EXCLUDED.stress_high,
             recovery_high=EXCLUDED.recovery_high,
             day_summary=EXCLUDED.day_summary, ingested_at=NOW()""",
        rows)

def sync_daily_resilience(cur, start, end):
    log.info("daily_resilience %s → %s", start, end)
    rows = []
    for it in oura_get("/daily_resilience",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        c = it.get("contributors") or {}
        rows.append((it["day"], it.get("level"),
                     c.get("sleep_recovery"), c.get("daytime_recovery"),
                     c.get("stress")))
    upsert(cur,
        """INSERT INTO daily_resilience
           (day, level, sleep_recovery, daytime_recovery, stress)
           VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET
             level=EXCLUDED.level,
             sleep_recovery=EXCLUDED.sleep_recovery,
             daytime_recovery=EXCLUDED.daytime_recovery,
             stress=EXCLUDED.stress, ingested_at=NOW()""",
        rows)

def sync_daily_spo2(cur, start, end):
    log.info("daily_spo2 %s → %s", start, end)
    rows = []
    for it in oura_get("/daily_spo2",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        avg = (it.get("spo2_percentage") or {}).get("average")
        rows.append((it["day"], avg, it.get("breathing_disturbance_index")))
    upsert(cur,
        """INSERT INTO daily_spo2 (day, average, breathing_disturbance_index)
           VALUES (%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET
             average=EXCLUDED.average,
             breathing_disturbance_index=EXCLUDED.breathing_disturbance_index,
             ingested_at=NOW()""",
        rows)

def sync_vo2_max(cur, start, end):
    log.info("vo2_max %s → %s", start, end)
    rows = []
    for it in oura_get("/vO2_max",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        rows.append((it["day"], it.get("vo2_max"), it.get("timestamp")))
    upsert(cur,
        """INSERT INTO vo2_max (day, vo2_max, measurement_ts)
           VALUES (%s,%s,%s)
           ON CONFLICT (day) DO UPDATE SET
             vo2_max=EXCLUDED.vo2_max,
             measurement_ts=EXCLUDED.measurement_ts, ingested_at=NOW()""",
        rows)

# ─── Sleep sessions + their intraday arrays ────────────────────────
def sync_sleep_sessions(cur, start, end):
    log.info("sleep (sessions + intraday) %s → %s", start, end)
    sess_rows, hr_rows, hrv_rows = [], [], []
    for it in oura_get("/sleep",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        sid = it["id"]
        sess_rows.append((sid, it["day"], it.get("type"),
                          it["bedtime_start"], it["bedtime_end"],
                          it.get("time_in_bed"), it.get("total_sleep_duration"),
                          it.get("awake_time"), it.get("deep_sleep_duration"),
                          it.get("light_sleep_duration"),
                          it.get("rem_sleep_duration"),
                          it.get("latency"), it.get("efficiency"),
                          it.get("average_heart_rate"),
                          it.get("lowest_heart_rate"),
                          it.get("average_hrv"),
                          it.get("average_breath"),
                          it.get("sleep_phase_5_min")))
        # HR intraday
        hr = it.get("heart_rate") or {}
        if hr.get("items") and hr.get("timestamp") and hr.get("interval"):
            t0 = datetime.fromisoformat(hr["timestamp"].replace("Z", "+00:00"))
            for i, v in enumerate(hr["items"]):
                if v is None: continue
                hr_rows.append((t0 + timedelta(seconds=i * hr["interval"]),
                               int(v), "sleep"))
        # HRV intraday
        hv = it.get("hrv") or {}
        if hv.get("items") and hv.get("timestamp") and hv.get("interval"):
            t0 = datetime.fromisoformat(hv["timestamp"].replace("Z", "+00:00"))
            for i, v in enumerate(hv["items"]):
                if v is None: continue
                hrv_rows.append((t0 + timedelta(seconds=i * hv["interval"]),
                                int(v), sid))

    upsert(cur,
        """INSERT INTO sleep_session
           (id, day, type, bedtime_start, bedtime_end,
            time_in_bed, total_sleep_duration, awake_time,
            deep_sleep_duration, light_sleep_duration, rem_sleep_duration,
            latency, efficiency, average_heart_rate, lowest_heart_rate,
            average_hrv, average_breath, sleep_phase_5_min)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (id) DO UPDATE SET
             day=EXCLUDED.day, type=EXCLUDED.type,
             bedtime_start=EXCLUDED.bedtime_start, bedtime_end=EXCLUDED.bedtime_end,
             time_in_bed=EXCLUDED.time_in_bed,
             total_sleep_duration=EXCLUDED.total_sleep_duration,
             awake_time=EXCLUDED.awake_time,
             deep_sleep_duration=EXCLUDED.deep_sleep_duration,
             light_sleep_duration=EXCLUDED.light_sleep_duration,
             rem_sleep_duration=EXCLUDED.rem_sleep_duration,
             latency=EXCLUDED.latency, efficiency=EXCLUDED.efficiency,
             average_heart_rate=EXCLUDED.average_heart_rate,
             lowest_heart_rate=EXCLUDED.lowest_heart_rate,
             average_hrv=EXCLUDED.average_hrv,
             average_breath=EXCLUDED.average_breath,
             sleep_phase_5_min=EXCLUDED.sleep_phase_5_min,
             ingested_at=NOW()""",
        sess_rows)
    if hr_rows:
        # purge overlapping sleep-source rows to avoid dupes on re-sync
        ts_min = min(r[0] for r in hr_rows); ts_max = max(r[0] for r in hr_rows)
        cur.execute("DELETE FROM hr_intraday WHERE source='sleep' AND ts BETWEEN %s AND %s",
                    (ts_min, ts_max))
        cur.executemany("INSERT INTO hr_intraday (ts, bpm, source) VALUES (%s,%s,%s)", hr_rows)
        log.info("  ↳ inserted %d sleep HR samples", len(hr_rows))
    if hrv_rows:
        ts_min = min(r[0] for r in hrv_rows); ts_max = max(r[0] for r in hrv_rows)
        cur.execute("DELETE FROM hrv_intraday WHERE ts BETWEEN %s AND %s", (ts_min, ts_max))
        cur.executemany("INSERT INTO hrv_intraday (ts, rmssd, session_id) VALUES (%s,%s,%s)", hrv_rows)
        log.info("  ↳ inserted %d HRV samples", len(hrv_rows))

# ─── Daytime HR (5-min) ────────────────────────────────────────────
def sync_daytime_hr(cur, start, end):
    log.info("heartrate (daytime) %s → %s", start, end)
    rows = []
    start_ts = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    end_ts   = datetime.combine(end,   datetime.max.time(), tzinfo=timezone.utc).isoformat()
    for it in oura_get("/heartrate",
                        {"start_datetime": start_ts, "end_datetime": end_ts}):
        rows.append((it["timestamp"], int(it["bpm"]), it.get("source", "awake")))
    if rows:
        ts_min = min(r[0] for r in rows); ts_max = max(r[0] for r in rows)
        cur.execute("DELETE FROM hr_intraday WHERE source != 'sleep' AND ts BETWEEN %s AND %s",
                    (ts_min, ts_max))
        cur.executemany("INSERT INTO hr_intraday (ts, bpm, source) VALUES (%s,%s,%s)", rows)
        log.info("  ↳ inserted %d daytime HR samples", len(rows))

# ─── Workouts + tags ───────────────────────────────────────────────
def sync_workouts(cur, start, end):
    log.info("workout %s → %s", start, end)
    rows = []
    for it in oura_get("/workout",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        rows.append((it["id"], it.get("activity"),
                     it["start_datetime"], it["end_datetime"],
                     it.get("calories"), it.get("distance"),
                     it.get("intensity"), it.get("label"),
                     it.get("source"), it["day"]))
    upsert(cur,
        """INSERT INTO workout (id, activity, start_datetime, end_datetime,
                                calories, distance, intensity, label, source, day)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (id) DO UPDATE SET
             activity=EXCLUDED.activity,
             start_datetime=EXCLUDED.start_datetime,
             end_datetime=EXCLUDED.end_datetime,
             calories=EXCLUDED.calories, distance=EXCLUDED.distance,
             intensity=EXCLUDED.intensity, label=EXCLUDED.label,
             source=EXCLUDED.source, day=EXCLUDED.day, ingested_at=NOW()""",
        rows)

def sync_tags(cur, start, end):
    log.info("enhanced_tag %s → %s", start, end)
    rows = []
    for it in oura_get("/enhanced_tag",
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}):
        rows.append((it["id"], it.get("tag_type_code"),
                     it.get("start_day"), it.get("end_day"),
                     it.get("start_time"), it.get("end_time"),
                     it.get("comment"), it.get("custom_name")))
    upsert(cur,
        """INSERT INTO enhanced_tag (id, tag_type_code, start_day, end_day,
                                     start_time, end_time, comment, custom_name)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (id) DO UPDATE SET
             tag_type_code=EXCLUDED.tag_type_code,
             start_day=EXCLUDED.start_day, end_day=EXCLUDED.end_day,
             start_time=EXCLUDED.start_time, end_time=EXCLUDED.end_time,
             comment=EXCLUDED.comment, custom_name=EXCLUDED.custom_name,
             ingested_at=NOW()""",
        rows)

# ─── Main ──────────────────────────────────────────────────────────
def window(conn) -> tuple[date, date]:
    """Decide the date window: full backfill on cold DB, otherwise 7-day reconciliation."""
    with conn.cursor() as c:
        c.execute("SELECT MAX(day) FROM daily_sleep")
        last = c.fetchone()[0]
    today = date.today()
    if last is None:
        days = int(os.getenv("BACKFILL_DAYS", 730))
        return today - timedelta(days=days), today
    # Overlap 7 days to catch post-hoc Oura revisions
    return max(last - timedelta(days=7), today - timedelta(days=14)), today

def main():
    log.info("──── oura sync starting ────")
    with db() as conn:
        start, end = window(conn)
        log.info("window: %s → %s", start, end)
        with conn.cursor() as cur:
            for fn in (sync_daily_cva, sync_daily_sleep, sync_daily_readiness,
                       sync_daily_activity, sync_daily_stress, sync_daily_resilience,
                       sync_daily_spo2, sync_vo2_max,
                       sync_sleep_sessions, sync_daytime_hr,
                       sync_workouts, sync_tags):
                try:
                    fn(cur, start, end)
                    conn.commit()
                except requests.HTTPError as e:
                    log.error("  ↳ %s failed: %s", fn.__name__, e)
                    conn.rollback()
                except Exception as e:
                    log.exception("  ↳ %s errored: %s", fn.__name__, e)
                    conn.rollback()
        # Refresh continuous aggregates
        with conn.cursor() as cur:
            for ca in ("hr_hourly", "hrv_daily", "met_daily"):
                try:
                    cur.execute(
                        f"CALL refresh_continuous_aggregate('{ca}', NULL, NULL)")
                    conn.commit()
                except Exception as e:
                    log.warning("refresh %s: %s", ca, e); conn.rollback()
    log.info("──── oura sync done ────")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("fatal")
        sys.exit(1)
