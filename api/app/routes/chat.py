"""LLM chat (streaming) + one-shot insight."""

import json
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import db, llm
from ..auth import require_auth

router = APIRouter(tags=["llm"], dependencies=[Depends(require_auth)])


# ── Today insight ─────────────────────────────────────────────────────────


@router.get("/insight/today")
def insight_today() -> dict:
    text = llm.one_shot_insight()
    return {"text": text}


# ── Streaming chat ────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


def _load_history(session_id: str, limit: int = 20) -> list[dict]:
    rows = db.fetch_all(
        """
        SELECT role, content
        FROM chat_message
        WHERE session_id = %s AND role IN ('user', 'assistant')
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (session_id, limit),
    )
    rows.reverse()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def _save_message(session_id: str, role: str, content: str, model: str | None = None) -> None:
    db.execute(
        """
        INSERT INTO chat_message (session_id, role, content, model)
        VALUES (%s, %s, %s, %s)
        """,
        (session_id, role, content, model),
    )


@router.post("/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    session_id = body.session_id or secrets.token_urlsafe(8)
    history = _load_history(session_id)

    _save_message(session_id, "user", body.question)

    async def stream():
        # First chunk is the session_id, so the UI can persist it.
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

        full = []
        try:
            async for chunk in llm.chat_stream(history, body.question):
                full.append(chunk)
                yield f"event: token\ndata: {json.dumps({'t': chunk})}\n\n"
        except Exception as e:  # surface upstream error to the client
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            return
        finally:
            text = "".join(full)
            if text:
                _save_message(session_id, "assistant", text, model=None)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Conversation history ──────────────────────────────────────────────────


@router.get("/chat/sessions")
def list_sessions() -> list[dict]:
    return db.fetch_all(
        """
        SELECT session_id,
               MIN(created_at) AS started_at,
               MAX(created_at) AS last_message_at,
               COUNT(*) FILTER (WHERE role = 'user') AS user_messages
        FROM chat_message
        GROUP BY session_id
        ORDER BY last_message_at DESC
        LIMIT 50
        """
    )


@router.get("/chat/sessions/{session_id}")
def get_session(session_id: str) -> list[dict]:
    return db.fetch_all(
        """
        SELECT id, role, content, created_at
        FROM chat_message
        WHERE session_id = %s
        ORDER BY created_at
        """,
        (session_id,),
    )


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    db.execute("DELETE FROM chat_message WHERE session_id = %s", (session_id,))
    return {"deleted": session_id}
