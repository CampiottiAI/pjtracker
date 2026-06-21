"""Withdrawal summary helpers."""

from __future__ import annotations

from pjtracker.app import WITHDRAW_TARGET_BRL


def compute_withdraw_summary(items: list[dict]) -> dict:
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
    }
