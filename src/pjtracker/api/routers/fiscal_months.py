"""Fiscal month listing, creation, and completeness."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pjtracker.api.schemas.common import (
    CreateFiscalMonthRequest,
    FISCAL_MES_REGEX,
    FiscalMonthResponse,
)
from pjtracker.api.services.fiscal_months import collect_fiscal_months, month_completeness
from pjtracker.app import save_fiscal_month

router = APIRouter(prefix="/fiscal-months", tags=["fiscal-months"])


@router.get("")
def list_fiscal_months() -> dict[str, list[str]]:
    return {"months": collect_fiscal_months()}


@router.post("")
def create_fiscal_month(payload: CreateFiscalMonthRequest) -> FiscalMonthResponse:
    created = save_fiscal_month(payload.fiscal_mes)
    return FiscalMonthResponse(fiscal_mes=payload.fiscal_mes, created=created)


@router.get("/{fiscal_mes}/completeness")
def fiscal_month_completeness(fiscal_mes: str) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")
    return month_completeness(fm)
