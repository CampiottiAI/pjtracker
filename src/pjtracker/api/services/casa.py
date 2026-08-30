"""Casa API helpers."""

from __future__ import annotations

from pjtracker.casa.bills_logic import compute_split_n
from pjtracker.casa.storage import (
    CreditCard,
    ExpenseItem,
    FixedBill,
    Person,
    compute_amounts_from_inputs,
    get_month,
    load_fixed_bills,
    load_people,
    normalize_cards,
    normalize_expense,
    normalize_month_record,
    nubank_from_cards,
    primary_pay_now,
    primary_assigned_brl,
    PRIMARY_PERSON_ID,
)


def default_pcts_for_people(people: list[Person]) -> list[float]:
    ids = [p["id"] for p in people]
    n = len(people)
    if n == 0:
        return []
    if ids == ["rael", "fer"]:
        return [0.6, 0.4]
    return [1.0 / n] * n


def build_split_payload(
    people: list[Person],
    fixed_bills: list[FixedBill],
    other_expenses: list[ExpenseItem],
    person_ids: list[str],
    pcts: list[float],
    nubank: float,
    cc_reserved_amount: float = 0.0,
    cc_reserved_person_id: str | None = None,
    cards: list[CreditCard] | None = None,
) -> dict:
    cards = normalize_cards(cards, nubank)
    nubank = nubank_from_cards(cards)
    other_expenses = [normalize_expense(e) for e in other_expenses]
    amounts = compute_amounts_from_inputs(people, fixed_bills, other_expenses)
    cc_ix: int | None = None
    if cc_reserved_amount > 1e-9 and cc_reserved_person_id:
        for i, pid in enumerate(person_ids):
            if pid == cc_reserved_person_id:
                cc_ix = i
                break
    split = compute_split_n(
        amounts,
        nubank,
        pcts,
        cc_reserved_amount=cc_reserved_amount,
        cc_reserved_person_index=cc_ix,
    )
    people_by_id = {p["id"]: p["name"] for p in people}
    return {
        "person_ids": person_ids,
        "person_names": [people_by_id.get(pid, pid) for pid in person_ids],
        "amounts": amounts,
        "other_expenses": [dict(e) for e in other_expenses],
        "fixed_bills": [dict(b) for b in fixed_bills],
        "nubank": nubank,
        "cards": [dict(c) for c in cards],
        "pcts": pcts,
        "total": split["total"],
        "nubank_per_person": split["nubank_per_person"],
        "reimbursements": split["reimbursements"],
        "cc_reserved_amount": split["cc_reserved_amount"],
        "cc_reserved_person_id": cc_reserved_person_id,
        "primary_person_id": PRIMARY_PERSON_ID,
        "primary_share_brl": primary_assigned_brl(
            person_ids,
            amounts,
            other_expenses,
            split["nubank_per_person"],
        ),
        "primary_pay_now_brl": primary_pay_now(
            split["nubank_per_person"],
            split["reimbursements"],
            people,
            person_ids,
        ),
        "split_result": split,
    }


def get_casa_summary_for_month(fiscal_mes: str) -> dict:
    people = load_people()
    record = get_month(fiscal_mes)
    if record:
        normalized = normalize_month_record(record, people)
        pcts = normalized["pcts"]
        total = normalized["total"]
        person_ids = normalized["person_ids"]
        assigned = primary_assigned_brl(
            person_ids,
            normalized["amounts"],
            normalized["other_expenses"],
            normalized["nubank_per_person"],
        )
        return {
            "saved": True,
            "estimated": False,
            "fiscal_mes": fiscal_mes,
            "total_brl": total,
            "household_total_brl": total,
            "primary_share_brl": assigned,
            "primary_pay_now_brl": primary_pay_now(
                normalized["nubank_per_person"],
                normalized["reimbursements"],
                people,
                person_ids,
            ),
            "person_ids": person_ids,
            "person_names": [
                next((p["name"] for p in people if p["id"] == pid), pid)
                for pid in person_ids
            ],
            "nubank_per_person": normalized["nubank_per_person"],
            "reimbursements": normalized["reimbursements"],
            "pcts": pcts,
            "nubank": normalized["nubank"],
            "cards": normalized["cards"],
        }

    fixed_bills = load_fixed_bills()
    pcts = default_pcts_for_people(people)
    person_ids = [p["id"] for p in people]
    estimated = build_split_payload(
        people,
        fixed_bills,
        [],
        person_ids,
        pcts,
        0.0,
    )
    return {
        "saved": False,
        "estimated": True,
        "fiscal_mes": fiscal_mes,
        "total_brl": round(estimated["total"], 2),
        "household_total_brl": round(estimated["total"], 2),
        "primary_share_brl": estimated["primary_share_brl"],
        "primary_pay_now_brl": estimated["primary_pay_now_brl"],
        "person_ids": person_ids,
        "person_names": [p["name"] for p in people],
        "nubank_per_person": estimated["nubank_per_person"],
        "reimbursements": estimated["reimbursements"],
        "pcts": pcts,
        "nubank": 0.0,
        "cards": [],
    }


def get_workspace(fiscal_mes: str) -> dict:
    people = load_people()
    record = get_month(fiscal_mes)
    saved = record is not None
    if saved and record:
        normalized = normalize_month_record(record, people)
        return {
            "fiscal_mes": fiscal_mes,
            "saved": True,
            "people": people,
            "fixed_bills": normalized["fixed_bills"],
            "other_expenses": normalized["other_expenses"],
            "nubank": normalized["nubank"],
            "cards": normalized["cards"],
            "person_ids": normalized["person_ids"],
            "pcts": normalized["pcts"],
            "cc_reserved_amount": normalized["cc_reserved_amount"],
            "cc_reserved_person_id": normalized["cc_reserved_person_id"],
            "split": build_split_payload(
                people,
                normalized["fixed_bills"],
                normalized["other_expenses"],
                normalized["person_ids"],
                normalized["pcts"],
                normalized["nubank"],
                cc_reserved_amount=normalized["cc_reserved_amount"],
                cc_reserved_person_id=normalized["cc_reserved_person_id"],
                cards=normalized["cards"],
            ),
        }

    fixed_bills = load_fixed_bills()
    person_ids = [p["id"] for p in people]
    pcts = default_pcts_for_people(people)
    other_expenses: list[ExpenseItem] = []
    return {
        "fiscal_mes": fiscal_mes,
        "saved": False,
        "people": people,
        "fixed_bills": fixed_bills,
        "other_expenses": other_expenses,
        "nubank": 0.0,
        "cards": [],
        "person_ids": person_ids,
        "pcts": pcts,
        "cc_reserved_amount": 0.0,
        "cc_reserved_person_id": None,
        "split": build_split_payload(
            people,
            fixed_bills,
            other_expenses,
            person_ids,
            pcts,
            0.0,
        ),
    }
