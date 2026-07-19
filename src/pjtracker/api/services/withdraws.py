"""Withdrawal summary helpers."""

from __future__ import annotations

from pjtracker.app import WITHDRAW_TARGET_BRL, get_nf_entries


def previous_fiscal_mes(fiscal_mes: str) -> str:
    """Return the prior calendar month as YYYY-MM."""
    year_str, month_str = fiscal_mes.strip().split("-", 1)
    year = int(year_str)
    month = int(month_str)
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def previous_month_income_brl(fiscal_mes: str) -> float:
    """Sum NF brl_with_spread for the month before fiscal_mes."""
    prev = previous_fiscal_mes(fiscal_mes)
    total = sum(float(row.get("brl_with_spread") or 0) for row in get_nf_entries(fiscal_mes=prev))
    return round(total, 2)


def compute_withdraw_summary(items: list[dict], fiscal_mes: str) -> dict:
    total = sum(float(row.get("amount_brl") or 0) for row in items)
    target = WITHDRAW_TARGET_BRL
    remaining = max(0.0, target - total)
    over = max(0.0, total - target)
    return {
        "target_brl": target,
        "total_brl": round(total, 2),
        "remaining_brl": round(remaining, 2),
        "over_target_brl": round(over, 2),
        "target_reached": total >= target,
        "previous_month_income_brl": previous_month_income_brl(fiscal_mes),
    }
