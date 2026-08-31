"""Registered deadline checks. Add new checks here."""

from __future__ import annotations

from pjtracker.checks.base import DeadlineCheck
from pjtracker.checks.darf_receipt import PreviousMonthDarfReceiptCheck
from pjtracker.checks.prolabore import ProLaboreWithdrawCheck


def get_registered_checks() -> list[DeadlineCheck]:
    return [
        ProLaboreWithdrawCheck(),
        PreviousMonthDarfReceiptCheck(),
    ]
