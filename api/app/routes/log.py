"""User-managed logs: interventions, food, supplements."""

from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, queries
from ..auth import require_auth

router = APIRouter(
    prefix="/log", tags=["log"], dependencies=[Depends(require_auth)]
)


# ── Interventions ──────────────────────────────────────────────────────────


class InterventionIn(BaseModel):
    name: str
    category: Optional[str] = None
    start_day: date
    end_day: Optional[date] = None
    dose: Optional[str] = None
    notes: Optional[str] = None


class InterventionOut(InterventionIn):
    id: int


@router.get("/interventions", response_model=list[dict])
def list_interventions() -> list[dict]:
    return queries.interventions_active()


@router.post("/interventions", response_model=dict)
def add_intervention(body: InterventionIn) -> dict:
    row = db.fetch_one(
        """
        INSERT INTO intervention (name, category, start_day, end_day, dose, notes)
        VALUES (%(name)s, %(category)s, %(start_day)s, %(end_day)s, %(dose)s, %(notes)s)
        RETURNING id, name, category, start_day, end_day, dose, notes
        """,
        body.model_dump(),
    )
    if row is None:
        raise HTTPException(500, "insert failed")
    return row


@router.delete("/interventions/{iid}")
def delete_intervention(iid: int) -> dict:
    db.execute("DELETE FROM intervention WHERE id = %s", (iid,))
    return {"deleted": iid}


@router.patch("/interventions/{iid}/end")
def end_intervention(iid: int, end_day: Optional[date] = None) -> dict:
    end = end_day or date.today()
    db.execute(
        "UPDATE intervention SET end_day = %s WHERE id = %s", (end, iid)
    )
    return {"id": iid, "end_day": end.isoformat()}


# ── Food ───────────────────────────────────────────────────────────────────


class FoodIn(BaseModel):
    description: str
    meal: Optional[str] = None
    day: Optional[date] = None
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    notes: Optional[str] = None


@router.get("/food")
def list_food(days: int = 7) -> list[dict]:
    return queries.recent_food(days=days)


@router.post("/food")
def add_food(body: FoodIn) -> dict:
    payload = body.model_dump()
    if payload.get("day") is None:
        payload["day"] = date.today()
    row = db.fetch_one(
        """
        INSERT INTO food_log (day, meal, description, calories, protein_g, carbs_g, fat_g, notes)
        VALUES (%(day)s, %(meal)s, %(description)s, %(calories)s, %(protein_g)s, %(carbs_g)s, %(fat_g)s, %(notes)s)
        RETURNING id, ts, day, meal, description, calories, protein_g, carbs_g, fat_g, notes
        """,
        payload,
    )
    return row or {}


@router.delete("/food/{fid}")
def delete_food(fid: int) -> dict:
    db.execute("DELETE FROM food_log WHERE id = %s", (fid,))
    return {"deleted": fid}


# ── Supplements ────────────────────────────────────────────────────────────


class SupplementIn(BaseModel):
    name: str
    dose: Optional[str] = None
    day: Optional[date] = None
    notes: Optional[str] = None


@router.get("/supplements")
def list_supplements(days: int = 7) -> list[dict]:
    return queries.recent_supplements(days=days)


@router.post("/supplements")
def add_supplement(body: SupplementIn) -> dict:
    payload = body.model_dump()
    if payload.get("day") is None:
        payload["day"] = date.today()
    row = db.fetch_one(
        """
        INSERT INTO supplement_log (day, name, dose, notes)
        VALUES (%(day)s, %(name)s, %(dose)s, %(notes)s)
        RETURNING id, ts, day, name, dose, notes
        """,
        payload,
    )
    return row or {}


@router.delete("/supplements/{sid}")
def delete_supplement(sid: int) -> dict:
    db.execute("DELETE FROM supplement_log WHERE id = %s", (sid,))
    return {"deleted": sid}
