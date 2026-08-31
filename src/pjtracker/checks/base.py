"""Deadline check protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    message: str
    overdue: bool = False
    fiscal_mes: str | None = None


class DeadlineCheck(Protocol):
    @property
    def id(self) -> str: ...

    def due_today(self, today: date) -> bool: ...

    def run(self, today: date) -> CheckResult: ...


def fiscal_mes_for(d: date) -> str:
    """Return YYYY-MM for a calendar date."""
    return f"{d.year:04d}-{d.month:02d}"


def previous_fiscal_mes(d: date) -> str:
    """Return YYYY-MM for the calendar month before *d*."""
    if d.month == 1:
        return f"{d.year - 1:04d}-12"
    return f"{d.year:04d}-{d.month - 1:02d}"
