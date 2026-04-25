"""Claude wrapper. Centralizes prompt templates and the data-snapshot the LLM sees."""

from __future__ import annotations

from datetime import date
import json
from typing import AsyncIterator

import anthropic

from . import queries
from .config import settings


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings().anthropic_api_key)


def _async_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings().anthropic_api_key)


def _json_default(o):
    if isinstance(o, (date,)):
        return o.isoformat()
    return str(o)


def build_data_snapshot(window_days: int = 30) -> str:
    """Compact JSON snapshot of the user's recent state.

    Designed to fit in well under 8k tokens — the LLM gets the daily wide-table
    plus active interventions, recent food, recent supplements, recent workouts.
    """
    snap = {
        "user": {
            "name": settings().user_name,
            "age": settings().user_age,
            "timezone": settings().user_timezone,
        },
        "today": queries.today_summary(),
        "cva_delta_7d": queries.cva_delta_7d(),
        "daily_last_30d": queries.daily_join_window(window_days),
        "interventions_active": queries.interventions_active(),
        "food_last_7d": queries.recent_food(7),
        "supplements_last_7d": queries.recent_supplements(7),
        "workouts_last_14d": queries.recent_workouts(14),
    }
    return json.dumps(snap, default=_json_default, indent=2)


SYSTEM_PROMPT_CHAT = """You are a thoughtful, evidence-based health analyst built into Atharva's
self-hosted Oura analytics app. The data you have access to is real — it comes
from the user's own ring and their manual logs.

Style:
- Direct, specific, numerate. Cite numbers from the data when you make claims.
- One useful answer beats five generic ones. Don't hedge with "consult a doctor"
  unless the question is genuinely medical.
- When you don't have data for a question, say so plainly.
- Be careful about causation vs correlation; flag confounders out loud.
- Use lowercase metric units the user already sees in the app (ms, bpm, kcal, °C).

You are not a doctor. For diagnostic / prescription questions, recommend a
clinician. For lifestyle / training / sleep / supplement experiments — engage."""


SYSTEM_PROMPT_DIGEST = """You are writing a Sunday morning weekly health digest for Atharva.

Format: short markdown report. Sections:
1. Headline — one sentence. The week's big story.
2. By the numbers — bullets with week-over-week deltas (CVA, sleep score, HRV,
   RHR, training load, total sleep hours).
3. What's working — interventions / behaviours that line up with positive trends.
   Cite the data.
4. What to watch — anomalies, drifts, sleep debt, etc.
5. One experiment to try this week — concrete, single-variable, measurable.

Tone: a brilliant friend who reads the data carefully. No filler, no platitudes.
500–800 words."""


SYSTEM_PROMPT_INSIGHT = """You are writing the "AI insight" that sits at the top of the Today page
in Atharva's Oura app. It's read on a phone in 5 seconds, so:

- 2 to 4 sentences. No headers, no bullets, no markdown.
- Lead with the most actionable observation in the last 24–48 hours.
- Cite at least one specific number.
- If something is going well, name what's likely driving it.
- If something is off, suggest one specific thing to do today.

Output the insight only — no preamble like "Here's your insight:"."""


def build_user_message_with_context(question: str) -> str:
    """Single user message: snapshot + question. Cheaper than a tool loop for now."""
    return (
        f"Here is the user's recent health data as JSON.\n\n"
        f"```json\n{build_data_snapshot()}\n```\n\n"
        f"Question: {question}"
    )


def one_shot_insight() -> str:
    """Generate the Today-page insight. Synchronous, fast, ~150 tokens out."""
    msg = _client().messages.create(
        model=settings().anthropic_model,
        max_tokens=400,
        system=SYSTEM_PROMPT_INSIGHT,
        messages=[
            {
                "role": "user",
                "content": build_user_message_with_context(
                    "Write today's insight."
                ),
            }
        ],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def one_shot_digest(window_days: int = 7) -> str:
    msg = _client().messages.create(
        model=settings().anthropic_model,
        max_tokens=4000,
        system=SYSTEM_PROMPT_DIGEST,
        messages=[
            {
                "role": "user",
                "content": build_user_message_with_context(
                    f"Write the weekly digest covering the last {window_days} days."
                ),
            }
        ],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


async def chat_stream(
    history: list[dict],
    question: str,
) -> AsyncIterator[str]:
    """Stream a chat response. `history` is prior turns: [{role, content}, …]."""
    messages = list(history)
    messages.append(
        {"role": "user", "content": build_user_message_with_context(question)}
    )

    async with _async_client().messages.stream(
        model=settings().anthropic_model,
        max_tokens=2000,
        system=SYSTEM_PROMPT_CHAT,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
