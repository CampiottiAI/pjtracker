"""Fluxo home aggregation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from pjtracker.api.schemas.common import FISCAL_MES_REGEX
from pjtracker.api.services.fiscal_months import collect_fiscal_months
from pjtracker.api.services.fluxo import build_fluxo, fluxo_series_months

router = APIRouter(prefix="/fluxo", tags=["fluxo"])


@router.get("")
def get_fluxo(fiscal_mes: str = Query(..., description="YYYY-MM")) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")
    return build_fluxo(fm)


@router.get("/series")
def get_fluxo_series() -> dict:
    months = collect_fiscal_months()
    return {"points": fluxo_series_months(months)}
