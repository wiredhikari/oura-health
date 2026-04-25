from fastapi import APIRouter, Depends

from .. import queries
from ..auth import require_auth

router = APIRouter(
    prefix="/health", tags=["health"], dependencies=[Depends(require_auth)]
)


@router.get("/today")
def get_today() -> dict:
    summary = queries.today_summary()
    summary["cva_delta_7d"] = queries.cva_delta_7d()
    return summary


@router.get("/cva")
def get_cva(days: int = 90) -> list[dict]:
    return queries.cva_trend(days=days)


@router.get("/hr/intraday")
def get_hr_intraday() -> list[dict]:
    return queries.hr_intraday_last_24h()


@router.get("/hrv/last-night")
def get_hrv_last_night() -> list[dict]:
    return queries.hrv_last_night()


@router.get("/daily")
def get_daily(days: int = 30) -> list[dict]:
    return queries.daily_join_window(days=days)
