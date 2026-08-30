"""Household bill split API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from pjtracker.api.schemas.common import FISCAL_MES_REGEX
from pjtracker.api.services.casa import build_split_payload, get_workspace
from pjtracker.casa.bills_logic import compute_split_n
from pjtracker.casa.storage import (
    add_person,
    compute_amounts_from_inputs,
    list_saved_fiscal_meses,
    load_fixed_bills,
    load_people,
    normalize_cards,
    normalize_expense,
    nubank_from_cards,
    person_used_in_fixed_bills,
    person_used_in_history,
    remove_person,
    save_fixed_bills,
    save_month_record,
    slug_from_name,
)

router = APIRouter(prefix="/casa", tags=["casa"])


class PersonCreate(BaseModel):
    name: str = Field(min_length=1)
    id: str | None = None


class FixedBillInput(BaseModel):
    name: str = Field(min_length=1)
    value: float = Field(ge=0)
    paid_by: str = Field(min_length=1)


class ExpenseItemInput(BaseModel):
    description: str = ""
    amount: float = Field(gt=0)
    paid_by: str = Field(min_length=1)
    split: bool = True


class CreditCardInput(BaseModel):
    name: str = Field(min_length=1)
    value: float = Field(ge=0)


class ComputeSplitRequest(BaseModel):
    fiscal_mes: str
    person_ids: list[str] = Field(min_length=1)
    pcts: list[float] = Field(min_length=1)
    nubank: float = Field(default=0.0, ge=0)
    cards: list[CreditCardInput] = Field(default_factory=list)
    fixed_bills: list[FixedBillInput] = Field(default_factory=list)
    other_expenses: list[ExpenseItemInput] = Field(default_factory=list)
    cc_reserved_amount: float = Field(default=0.0, ge=0)
    cc_reserved_person_id: str | None = None

    @field_validator("fiscal_mes", mode="before")
    @classmethod
    def normalize_fiscal_mes(cls, value: str) -> str:
        s = str(value).strip()
        if not FISCAL_MES_REGEX.match(s):
            raise ValueError("fiscal_mes must be YYYY-MM")
        return s


class SaveMonthRequest(ComputeSplitRequest):
    pass


class FixedBillsUpdate(BaseModel):
    items: list[FixedBillInput]


def _expenses_from_payload(payload: ComputeSplitRequest) -> list[dict]:
    return [
        dict(
            normalize_expense(
                {
                    "description": e.description.strip(),
                    "amount": e.amount,
                    "paid_by": e.paid_by.strip(),
                    "split": e.split,
                }
            )
        )
        for e in payload.other_expenses
    ]


def _cards_from_payload(payload: ComputeSplitRequest) -> list[dict]:
    return normalize_cards(
        [{"name": c.name.strip(), "value": c.value} for c in payload.cards],
        payload.nubank,
    )


@router.get("/people")
def list_people() -> dict:
    people = load_people()
    return {"items": people}


@router.post("/people")
def create_person(payload: PersonCreate) -> dict:
    name = payload.name.strip()
    pid = (payload.id or "").strip() or slug_from_name(name)
    if not pid:
        pid = "person"
    try:
        person = add_person(pid, name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return person


@router.delete("/people/{person_id}")
def delete_person(person_id: str) -> dict:
    people = load_people()
    if len(people) <= 2:
        raise HTTPException(status_code=422, detail="At least two people required")
    if person_used_in_fixed_bills(person_id) or person_used_in_history(person_id):
        raise HTTPException(
            status_code=422,
            detail="Person is used in fixed bills or history and cannot be removed",
        )
    try:
        remove_person(person_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"deleted": True, "id": person_id}


@router.get("/fixed-bills")
def get_fixed_bills() -> dict:
    return {"items": load_fixed_bills()}


@router.put("/fixed-bills")
def put_fixed_bills(payload: FixedBillsUpdate) -> dict:
    items = [
        {"name": b.name.strip(), "value": b.value, "paid_by": b.paid_by.strip()}
        for b in payload.items
    ]
    save_fixed_bills(items)
    return {"items": items}


@router.get("/months")
def list_months() -> dict:
    return {"months": list_saved_fiscal_meses()}


@router.get("/workspace")
def workspace(fiscal_mes: str = Query(..., description="YYYY-MM")) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")
    return get_workspace(fm)


@router.post("/compute-split")
def compute_split_endpoint(payload: ComputeSplitRequest) -> dict:
    people = load_people()
    if abs(sum(payload.pcts) - 1.0) > 1e-9:
        raise HTTPException(status_code=422, detail="pcts must sum to 1.0")
    fixed = [
        {"name": b.name.strip(), "value": b.value, "paid_by": b.paid_by.strip()}
        for b in payload.fixed_bills
    ]
    expenses = _expenses_from_payload(payload)
    try:
        return build_split_payload(
            people,
            fixed,
            expenses,
            payload.person_ids,
            payload.pcts,
            payload.nubank,
            cc_reserved_amount=payload.cc_reserved_amount,
            cc_reserved_person_id=payload.cc_reserved_person_id,
            cards=_cards_from_payload(payload),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.put("/months/{fiscal_mes}")
def save_month(fiscal_mes: str, payload: SaveMonthRequest) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")
    if fm != payload.fiscal_mes:
        raise HTTPException(status_code=422, detail="fiscal_mes path and body must match")
    people = load_people()
    if abs(sum(payload.pcts) - 1.0) > 1e-9:
        raise HTTPException(status_code=422, detail="pcts must sum to 1.0")
    fixed = [
        {"name": b.name.strip(), "value": b.value, "paid_by": b.paid_by.strip()}
        for b in payload.fixed_bills
    ]
    expenses = _expenses_from_payload(payload)
    amounts = compute_amounts_from_inputs(people, fixed, expenses)
    cards = _cards_from_payload(payload)
    nubank = nubank_from_cards(cards)
    cc_ix: int | None = None
    if payload.cc_reserved_amount > 1e-9 and payload.cc_reserved_person_id:
        for i, pid in enumerate(payload.person_ids):
            if pid == payload.cc_reserved_person_id:
                cc_ix = i
                break
    try:
        split = compute_split_n(
            amounts,
            nubank,
            payload.pcts,
            cc_reserved_amount=payload.cc_reserved_amount,
            cc_reserved_person_index=cc_ix,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    saved = save_month_record(
        fm,
        payload.person_ids,
        amounts,
        expenses,
        payload.pcts,
        nubank,
        cards=cards,
        fixed_bills=fixed,
        split_result=split,
    )
    return saved
