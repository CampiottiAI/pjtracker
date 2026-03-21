"""Fiscal month listing and completeness."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from src.api.services.fiscal_months import collect_fiscal_months, month_completeness

router = APIRouter(prefix="/fiscal-months", tags=["fiscal-months"])

YYYY_MM = re.compile(r"^\d{4}-\d{2}$")


@router.get("")
def list_fiscal_months() -> dict[str, list[str]]:
    return {"months": collect_fiscal_months()}


@router.get("/{fiscal_mes}/completeness")
def fiscal_month_completeness(fiscal_mes: str) -> dict:
    fm = fiscal_mes.strip()
    if not YYYY_MM.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")
    return month_completeness(fm)
