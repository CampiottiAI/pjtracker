"""JSON persistence for household bill split (casa)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NotRequired, TypedDict

from pjtracker.app import PROJECT_ROOT

CASA_DATA_DIR = PROJECT_ROOT / "data" / "casa"
HISTORY_PATH = CASA_DATA_DIR / "bills_history.json"
FIXED_BILLS_PATH = CASA_DATA_DIR / "fixed_bills.json"
PEOPLE_PATH = CASA_DATA_DIR / "people.json"

DEFAULT_PEOPLE = [
    {"id": "rael", "name": "Rael"},
    {"id": "fer", "name": "Fer"},
]

PRIMARY_PERSON_ID = "rael"


class Person(TypedDict):
    id: str
    name: str


class FixedBill(TypedDict):
    name: str
    value: float
    paid_by: str


class ExpenseItem(TypedDict):
    description: str
    amount: float
    paid_by: str


class MonthRecord(TypedDict):
    year: int
    month: int
    nubank: float
    fixed_bills: NotRequired[list[FixedBill]]
    person_ids: NotRequired[list[str]]
    amounts: NotRequired[list[float]]
    other_expenses: NotRequired[list[ExpenseItem]]
    items: NotRequired[dict[str, list[float]]]
    pcts: NotRequired[list[float]]
    total: NotRequired[float]
    nubank_per_person: NotRequired[list[float]]
    reimbursements: NotRequired[list[float]]
    cc_reserved_amount: NotRequired[float]
    cc_reserved_person_id: NotRequired[str | None]
    # Legacy two-person keys
    rael: NotRequired[float]
    fer: NotRequired[float]
    rael_items: NotRequired[list[float]]
    fer_items: NotRequired[list[float]]


def fiscal_mes_to_year_month(fiscal_mes: str) -> tuple[int, int]:
    year_str, month_str = fiscal_mes.strip().split("-", 1)
    return int(year_str), int(month_str)


def year_month_to_fiscal_mes(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def slug_from_name(name: str) -> str:
    s = name.strip().lower()
    for old, new in [
        ("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"),
        ("é", "e"), ("ê", "e"), ("í", "i"),
        ("ó", "o"), ("ô", "o"), ("õ", "o"),
        ("ú", "u"), ("ç", "c"),
    ]:
        s = s.replace(old, new)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s or "person"


def _ensure_data_dir() -> None:
    CASA_DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_history() -> list[MonthRecord]:
    _ensure_data_dir()
    if not HISTORY_PATH.exists():
        return []
    raw = HISTORY_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    records = [MonthRecord(r) for r in data]
    records.sort(key=lambda r: (r["year"], r["month"]), reverse=True)
    return records


def list_saved_fiscal_meses() -> list[str]:
    return [
        year_month_to_fiscal_mes(r["year"], r["month"])
        for r in load_history()
    ]


def _normalize_other_expenses(
    record: MonthRecord,
    person_ids: list[str],
) -> list[ExpenseItem]:
    if record.get("other_expenses"):
        return [ExpenseItem(e) for e in record["other_expenses"]]
    items = record.get("items") or {}
    out: list[ExpenseItem] = []
    for pid in person_ids:
        for val in items.get(pid, []):
            out.append(
                ExpenseItem({"description": "", "amount": float(val), "paid_by": pid})
            )
    legacy_map = {
        "rael": record.get("rael_items") or [],
        "fer": record.get("fer_items") or [],
    }
    for pid, vals in legacy_map.items():
        if pid in person_ids:
            continue
        for val in vals:
            out.append(
                ExpenseItem({"description": "", "amount": float(val), "paid_by": pid})
            )
    return out


def normalize_month_record(r: MonthRecord, people: list[Person]) -> dict:
    year = r["year"]
    month = r["month"]
    nubank = r["nubank"]
    fixed_bills = r.get("fixed_bills") or []

    if "person_ids" in r and r["person_ids"]:
        person_ids = list(r["person_ids"])
        other_expenses = _normalize_other_expenses(r, person_ids)
        return {
            "fiscal_mes": year_month_to_fiscal_mes(year, month),
            "year": year,
            "month": month,
            "nubank": nubank,
            "fixed_bills": fixed_bills,
            "person_ids": person_ids,
            "amounts": r.get("amounts") or [],
            "other_expenses": other_expenses,
            "pcts": r.get("pcts") or [],
            "total": r.get("total") or 0.0,
            "nubank_per_person": r.get("nubank_per_person") or [],
            "reimbursements": r.get("reimbursements") or [],
            "cc_reserved_amount": float(r.get("cc_reserved_amount") or 0.0),
            "cc_reserved_person_id": r.get("cc_reserved_person_id"),
            "saved": True,
        }

    # Legacy rael/fer
    rael = r.get("rael") or 0.0
    fer = r.get("fer") or 0.0
    total = r.get("total") or (rael + fer + nubank)
    rael_pct = r.get("rael_pct") if "rael_pct" in r else 0.6
    fer_pct = r.get("fer_pct") if "fer_pct" in r else 0.4
    person_ids = ["rael", "fer"]
    other_expenses = _normalize_other_expenses(r, person_ids)
    rael_nubank = r.get("rael_nubank")
    if rael_nubank is None:
        rael_nubank = rael_pct * total - rael
    fer_nubank = r.get("fer_nubank")
    if fer_nubank is None:
        fer_nubank = fer_pct * total - fer
    return {
        "fiscal_mes": year_month_to_fiscal_mes(year, month),
        "year": year,
        "month": month,
        "nubank": nubank,
        "fixed_bills": fixed_bills,
        "person_ids": person_ids,
        "amounts": [rael, fer],
        "other_expenses": other_expenses,
        "pcts": [rael_pct, fer_pct],
        "total": total,
        "nubank_per_person": [rael_nubank, fer_nubank],
        "reimbursements": [
            r.get("rael_reimbursement") or 0.0,
            r.get("fer_reimbursement") or 0.0,
        ],
        "cc_reserved_amount": float(r.get("cc_reserved_amount") or 0.0),
        "cc_reserved_person_id": r.get("cc_reserved_person_id"),
        "saved": True,
    }


def save_month_record(
    fiscal_mes: str,
    person_ids: list[str],
    amounts: list[float],
    other_expenses: list[ExpenseItem],
    pcts: list[float],
    nubank: float,
    *,
    fixed_bills: list[FixedBill] | None = None,
    split_result: dict | None = None,
) -> dict:
    year, month = fiscal_mes_to_year_month(fiscal_mes)
    _ensure_data_dir()
    records = load_history()
    key = (year, month)
    records = [r for r in records if (r["year"], r["month"]) != key]

    total = split_result["total"] if split_result else (sum(amounts) + nubank)
    nubank_per_person = split_result["nubank_per_person"] if split_result else []
    reimbursements = split_result["reimbursements"] if split_result else []

    cr_amt = 0.0
    cr_pid: str | None = None
    if split_result:
        cr_amt = float(split_result.get("cc_reserved_amount") or 0.0)
        ix_cc = split_result.get("cc_reserved_person_index")
        if cr_amt > 1e-9 and ix_cc is not None and 0 <= ix_cc < len(person_ids):
            cr_pid = person_ids[ix_cc]

    record: MonthRecord = {
        "year": year,
        "month": month,
        "nubank": nubank,
        "person_ids": list(person_ids),
        "amounts": list(amounts),
        "other_expenses": [dict(e) for e in other_expenses],
        "pcts": list(pcts),
        "total": total,
        "nubank_per_person": list(nubank_per_person),
        "reimbursements": list(reimbursements),
        "cc_reserved_amount": cr_amt,
        "cc_reserved_person_id": cr_pid,
    }
    if fixed_bills is not None:
        record["fixed_bills"] = [dict(b) for b in fixed_bills]

    records.append(record)
    records.sort(key=lambda r: (r["year"], r["month"]), reverse=True)
    HISTORY_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    people = load_people()
    return normalize_month_record(record, people)


def get_month(fiscal_mes: str) -> MonthRecord | None:
    year, month = fiscal_mes_to_year_month(fiscal_mes)
    for r in load_history():
        if r["year"] == year and r["month"] == month:
            return r
    return None


def load_fixed_bills() -> list[FixedBill]:
    _ensure_data_dir()
    if not FIXED_BILLS_PATH.exists():
        return []
    raw = FIXED_BILLS_PATH.read_text(encoding="utf-8")
    return [FixedBill(r) for r in json.loads(raw)]


def save_fixed_bills(items: list[FixedBill]) -> None:
    _ensure_data_dir()
    FIXED_BILLS_PATH.write_text(
        json.dumps([dict(b) for b in items], indent=2), encoding="utf-8"
    )


def load_people() -> list[Person]:
    _ensure_data_dir()
    if not PEOPLE_PATH.exists():
        people = [Person(p) for p in DEFAULT_PEOPLE]
        save_people(people)
        return people
    raw = PEOPLE_PATH.read_text(encoding="utf-8")
    return [Person(p) for p in json.loads(raw)]


def save_people(people: list[Person]) -> None:
    _ensure_data_dir()
    PEOPLE_PATH.write_text(
        json.dumps([dict(p) for p in people], indent=2), encoding="utf-8"
    )


def add_person(person_id: str, name: str) -> Person:
    people = load_people()
    if any(p["id"] == person_id for p in people):
        raise ValueError(f"Person id already exists: {person_id}")
    person = Person({"id": person_id, "name": name})
    people.append(person)
    save_people(people)
    return person


def remove_person(person_id: str) -> None:
    people = load_people()
    original_count = len(people)
    people = [p for p in people if p["id"] != person_id]
    if len(people) == original_count:
        raise ValueError(f"Person not found: {person_id}")
    save_people(people)


def person_used_in_fixed_bills(person_id: str) -> bool:
    return any(b["paid_by"] == person_id for b in load_fixed_bills())


def person_used_in_history(person_id: str) -> bool:
    for r in load_history():
        if "person_ids" in r and person_id in r["person_ids"]:
            return True
        if person_id in ("rael", "fer") and person_id in r:
            return True
    return False


def compute_amounts_from_inputs(
    people: list[Person],
    fixed_bills: list[FixedBill],
    other_expenses: list[ExpenseItem],
) -> list[float]:
    amounts: list[float] = []
    for p in people:
        pid = p["id"]
        fixed_sum = sum(b["value"] for b in fixed_bills if b["paid_by"] == pid)
        other_sum = sum(e["amount"] for e in other_expenses if e["paid_by"] == pid)
        amounts.append(fixed_sum + other_sum)
    return amounts


def estimate_necessidade_from_fixed_bills(
    people: list[Person],
    fixed_bills: list[FixedBill],
    pcts: list[float],
) -> float:
    """Rough monthly need: sum(fixed) * primary person's pct."""
    total_fixed = sum(b["value"] for b in fixed_bills)
    primary_ix = _primary_person_index(people)
    pct = pcts[primary_ix] if primary_ix < len(pcts) else 0.5
    return round(total_fixed * pct, 2)


def _primary_person_index(people: list[Person]) -> int:
    for i, p in enumerate(people):
        if p["id"] == PRIMARY_PERSON_ID:
            return i
    return 0


def primary_person_share(total: float, pcts: list[float], people: list[Person]) -> float:
    ix = _primary_person_index(people)
    if ix >= len(pcts):
        return 0.0
    return round(total * pcts[ix], 2)


def primary_pay_now(
    nubank_per_person: list[float],
    reimbursements: list[float],
    people: list[Person],
    person_ids: list[str],
) -> float:
    """Operational cash: card share + reimbursements others owe primary (if primary underpaid)."""
    ix = _primary_person_index([Person({"id": pid, "name": pid}) for pid in person_ids])
    if ix >= len(nubank_per_person):
        return 0.0
    card_share = max(0.0, nubank_per_person[ix])
    # If primary has reimbursement, others owe them — not "pay now"
    reimb = reimbursements[ix] if ix < len(reimbursements) else 0.0
    if reimb > 0:
        return round(card_share, 2)
    return round(card_share, 2)
