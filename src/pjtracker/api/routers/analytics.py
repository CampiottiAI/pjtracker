"""Analytics endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from pjtracker.api.services.analytics import nf_series_points

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/nf-series")
def nf_series(
    date_from: date = Query(..., description="Start date (inclusive)"),
    date_to: date = Query(..., description="End date (inclusive)"),
) -> dict:
    if date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to",
        )
    return {"points": nf_series_points(date_from, date_to)}
