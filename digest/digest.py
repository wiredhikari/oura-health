"""Weekly health digest job.

Schedule: Sunday 9am local (Railway cron schedule '0 9 * * 0' is UTC; adjust if you
want a different local time).

Steps:
  1. Pull last 7 days of wide daily data + interventions + food + supplements.
  2. Build a JSON snapshot.
  3. Ask Claude for a markdown weekly report.
  4. INSERT into `digest`.
  5. Email it via Resend if RESEND_API_KEY + DIGEST_EMAIL_TO are set.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import date, timedelta

import anthropic
import httpx
import psycopg
from psycopg.rows import dict_row


# ── Config ─────────────────────────────────────────────────────────────────

DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")

RESEND_API_KEY    = os.environ.get("RESEND_API_KEY", "")
DIGEST_EMAIL_FROM = os.environ.get("DIGEST_EMAIL_FROM", "digest@oura-health.local")
DIGEST_EMAIL_TO   = os.environ.get("DIGEST_EMAIL_TO", "")
USER_NAME         = os.environ.get("USER_NAME", "you")


# ── DB helpers ─────────────────────────────────────────────────────────────

@contextmanager
def conn():
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as c:
        yield c


def fetch_all(sql: str, params=()) -> list[dict]:
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def execute(sql: str, params=()) -> dict | None:
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        if cur.description:
            return cur.fetchone()
    return None


# ── Snapshot ───────────────────────────────────────────────────────────────

def snapshot(week_start: date, week_end: date) -> dict:
    return {
        "week_start": week_start.isoformat(),
        "week_end":   week_end.isoformat(),
        "user_name":  USER_NAME,
        "daily": fetch_all(
            """
            SELECT c.day, c.vascular_age,
                   s.score AS sleep_score, s.total_sleep, s.efficiency,
                   r.score AS readiness_score, r.resting_heart_rate,
                   r.hrv_balance, r.temperature_deviation,
                   a.score AS activity_score, a.steps, a.active_calories
            FROM daily_cva c
            LEFT JOIN daily_sleep      s ON s.day = c.day
            LEFT JOIN daily_readiness  r ON r.day = c.day
            LEFT JOIN daily_activity   a ON a.day = c.day
            WHERE c.day BETWEEN %s AND %s
            ORDER BY c.day
            """,
            (week_start, week_end),
        ),
        "interventions": fetch_all(
            """
            SELECT name, category, start_day, end_day, dose, notes
            FROM intervention
            WHERE end_day IS NULL
               OR end_day >= %s - INTERVAL '14 days'
            ORDER BY start_day DESC
            """,
            (week_start,),
        ),
        "food": fetch_all(
            """
            SELECT day, meal, description, calories
            FROM food_log
            WHERE day BETWEEN %s AND %s
            ORDER BY ts
            """,
            (week_start, week_end),
        ),
        "supplements": fetch_all(
            """
            SELECT day, name, dose
            FROM supplement_log
            WHERE day BETWEEN %s AND %s
            ORDER BY ts
            """,
            (week_start, week_end),
        ),
        "workouts": fetch_all(
            """
            SELECT day, activity, intensity, calories, distance,
                   start_datetime, end_datetime
            FROM workout
            WHERE day BETWEEN %s AND %s
            ORDER BY start_datetime
            """,
            (week_start, week_end),
        ),
    }


SYSTEM = """You are writing a Sunday morning weekly health digest.

Format: short markdown report. Sections:
1. **Headline** — one sentence. The week's big story.
2. **By the numbers** — bullets with week-over-week deltas
   (CVA, sleep score, HRV/RHR, training load, total sleep hours).
3. **What's working** — interventions / behaviours that line up with
   positive trends. Cite the data.
4. **What to watch** — anomalies, drifts, sleep debt, etc.
5. **One experiment to try this week** — concrete, single-variable, measurable.

Tone: a brilliant friend who reads the data carefully. No filler, no platitudes.
500–800 words. Numbers must be cited from the data."""


def _json_default(o):
    if isinstance(o, date):
        return o.isoformat()
    return str(o)


def generate_markdown(snap: dict) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    user = (
        "Here is the user's last 7 days of health data, plus prior context.\n\n"
        f"```json\n{json.dumps(snap, default=_json_default, indent=2)}\n```\n\n"
        "Write the weekly digest."
    )
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


# ── Email ──────────────────────────────────────────────────────────────────

def email_via_resend(markdown: str, week_start: date, week_end: date) -> bool:
    if not (RESEND_API_KEY and DIGEST_EMAIL_TO):
        print("(skipping email — RESEND_API_KEY or DIGEST_EMAIL_TO not set)")
        return False

    subject = f"Weekly digest · {week_start} → {week_end}"
    html = (
        "<div style='font-family:-apple-system,Segoe UI,sans-serif;"
        "max-width:640px;margin:0 auto;padding:24px;color:#0e1116;'>"
        f"{_md_to_simple_html(markdown)}"
        "<hr style='margin:24px 0;border:0;border-top:1px solid #ddd;' />"
        "<p style='color:#666;font-size:12px;'>Generated by your oura-health stack.</p>"
        "</div>"
    )

    r = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "from":    DIGEST_EMAIL_FROM,
            "to":      [DIGEST_EMAIL_TO],
            "subject": subject,
            "html":    html,
            "text":    markdown,
        },
        timeout=30,
    )
    if r.status_code >= 300:
        print(f"resend send failed: {r.status_code} {r.text}")
        return False
    print(f"emailed digest to {DIGEST_EMAIL_TO} (id={r.json().get('id')})")
    return True


def _md_to_simple_html(md: str) -> str:
    """Tiny markdown → HTML converter — good enough for digests, no deps."""
    lines = md.split("\n")
    out: list[str] = []
    in_ul = False
    for ln in lines:
        s = ln.rstrip()
        if not s:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append("<br />")
            continue
        if s.startswith("# "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<h2 style='margin:16px 0 6px;'>{s[2:]}</h2>")
        elif s.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<h3 style='margin:14px 0 6px;'>{s[3:]}</h3>")
        elif s.startswith("- ") or s.startswith("* "):
            if not in_ul: out.append("<ul style='padding-left:18px;'>"); in_ul = True
            out.append(f"<li style='margin:4px 0;'>{_inline(s[2:])}</li>")
        else:
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<p style='margin:8px 0;line-height:1.55;'>{_inline(s)}</p>")
    if in_ul: out.append("</ul>")
    return "\n".join(out)


def _inline(s: str) -> str:
    # Very small inline pass: **bold** and `code`.
    import re
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    today = date.today()
    week_end   = today - timedelta(days=1)            # last full day
    week_start = week_end - timedelta(days=6)         # 7-day window

    # If we already have one for this week, skip (idempotent).
    existing = fetch_all(
        "SELECT id FROM digest WHERE week_start = %s AND week_end = %s",
        (week_start, week_end),
    )
    if existing:
        print(f"digest for {week_start}..{week_end} already exists — skipping")
        return 0

    snap = snapshot(week_start, week_end)
    if not snap["daily"]:
        print(f"no daily data in window {week_start}..{week_end} — skipping")
        return 0

    print(f"generating digest for {week_start}..{week_end}")
    markdown = generate_markdown(snap)

    row = execute(
        """
        INSERT INTO digest (week_start, week_end, markdown)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (week_start, week_end, markdown),
    )
    digest_id = row["id"] if row else None
    print(f"saved digest id={digest_id}")

    sent = email_via_resend(markdown, week_start, week_end)
    if sent and digest_id is not None:
        execute(
            "UPDATE digest SET emailed_at = NOW() WHERE id = %s",
            (digest_id,),
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
