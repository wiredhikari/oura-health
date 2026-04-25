"""Read access to past weekly digests (the digest service writes them)."""

from fastapi import APIRouter, Depends, HTTPException

from .. import queries, db
from ..auth import require_auth

router = APIRouter(
    prefix="/digest", tags=["digest"], dependencies=[Depends(require_auth)]
)


@router.get("/latest")
def get_latest() -> dict:
    row = queries.latest_digest()
    if row is None:
        raise HTTPException(404, "no digests yet — wait for Sunday or trigger /digest/run")
    return row


@router.get("")
def list_digests() -> list[dict]:
    return queries.all_digests()


@router.get("/{did}")
def get_digest(did: int) -> dict:
    row = db.fetch_one(
        """
        SELECT id, week_start, week_end, markdown, emailed_at, created_at
        FROM digest WHERE id = %s
        """,
        (did,),
    )
    if row is None:
        raise HTTPException(404, "no such digest")
    return row
