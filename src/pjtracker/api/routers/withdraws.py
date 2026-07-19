"""Manual BRL withdrawals per fiscal month."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from pjtracker.api.schemas.common import FISCAL_MES_REGEX
from pjtracker.api.services.withdraws import compute_withdraw_summary
from pjtracker.app import (
    delete_withdraw,
    get_withdraw_by_id,
    get_withdraws,
    save_withdraw,
    update_withdraw,
)

router = APIRouter(prefix="/withdraws", tags=["withdraws"])


class CreateWithdrawRequest(BaseModel):
    fiscal_mes: str = Field(description="YYYY-MM")
    amount_brl: float = Field(gt=0)
    withdraw_date: str | None = Field(default=None)
    notes: str | None = Field(default=None)

    @field_validator("fiscal_mes", mode="before")
    @classmethod
    def normalize_fiscal_mes(cls, value: str) -> str:
        s = str(value).strip()
        if not FISCAL_MES_REGEX.match(s):
            raise ValueError("fiscal_mes must be YYYY-MM")
        return s

    @field_validator("withdraw_date", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return str(value).strip()


class PatchWithdrawRequest(BaseModel):
    fiscal_mes: str | None = Field(default=None)
    amount_brl: float | None = Field(default=None, gt=0)
    withdraw_date: str | None = Field(default=None)
    notes: str | None = Field(default=None)

    @field_validator("fiscal_mes", mode="before")
    @classmethod
    def normalize_fiscal_mes(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        s = str(value).strip()
        if not FISCAL_MES_REGEX.match(s):
            raise ValueError("fiscal_mes must be YYYY-MM")
        return s

    @field_validator("withdraw_date", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return str(value).strip()


def _serialize_withdraw(row: dict) -> dict:
    return {
        "id": row["id"],
        "fiscal_mes": row["fiscal_mes"],
        "amount_brl": row["amount_brl"],
        "withdraw_date": row.get("withdraw_date"),
        "notes": row.get("notes"),
        "created_at": row["created_at"],
    }


@router.get("")
def list_withdraws(
    fiscal_mes: str = Query(..., description="YYYY-MM"),
) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")
    items = get_withdraws(fiscal_mes=fm)
    return {
        "items": [_serialize_withdraw(row) for row in items],
        "summary": compute_withdraw_summary(items, fiscal_mes=fm),
    }


@router.post("")
def create_withdraw(payload: CreateWithdrawRequest) -> dict:
    withdraw_id = save_withdraw(
        fiscal_mes=payload.fiscal_mes,
        amount_brl=payload.amount_brl,
        withdraw_date=payload.withdraw_date,
        notes=payload.notes,
    )
    row = get_withdraw_by_id(withdraw_id)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create withdrawal")
    return _serialize_withdraw(row)


@router.patch("/{withdraw_id}")
def patch_withdraw(withdraw_id: int, payload: PatchWithdrawRequest) -> dict:
    fields_set = payload.model_fields_set
    if not fields_set:
        raise HTTPException(status_code=422, detail="No fields to update")

    clear_withdraw_date = "withdraw_date" in fields_set and payload.withdraw_date is None
    clear_notes = "notes" in fields_set and payload.notes is None

    updated = update_withdraw(
        withdraw_id,
        fiscal_mes=payload.fiscal_mes if "fiscal_mes" in fields_set else None,
        amount_brl=payload.amount_brl if "amount_brl" in fields_set else None,
        withdraw_date=payload.withdraw_date if "withdraw_date" in fields_set else None,
        notes=payload.notes if "notes" in fields_set else None,
        clear_withdraw_date=clear_withdraw_date,
        clear_notes=clear_notes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    row = get_withdraw_by_id(withdraw_id)
    if not row:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    return _serialize_withdraw(row)


@router.delete("/{withdraw_id}")
def remove_withdraw(withdraw_id: int) -> dict:
    deleted = delete_withdraw(withdraw_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    return {"deleted": True}
