"""Previous-month DARF + receipt deadline check."""

from __future__ import annotations

from datetime import date

from pjtracker.app import get_darfs
from pjtracker.checks.base import CheckResult, previous_fiscal_mes

DARF_DUE_BY_DAY = 20


class PreviousMonthDarfReceiptCheck:
    @property
    def id(self) -> str:
        return "darf_previous_month_receipt"

    def due_today(self, today: date) -> bool:
        # Remind every day of the month; escalate after day 20.
        return True

    def run(self, today: date) -> CheckResult:
        fiscal_mes = previous_fiscal_mes(today)
        overdue = today.day > DARF_DUE_BY_DAY
        darfs = get_darfs(fiscal_mes=fiscal_mes)
        with_receipt = [d for d in darfs if d.get("receipt_path")]
        if with_receipt:
            return CheckResult(
                check_id=self.id,
                passed=True,
                message=(
                    f"DARF with receipt found for previous month {fiscal_mes}."
                ),
                overdue=False,
                fiscal_mes=fiscal_mes,
            )
        status = "OVERDUE" if overdue else "due"
        return CheckResult(
            check_id=self.id,
            passed=False,
            message=(
                f"DARF+recibo {status} for previous month {fiscal_mes} "
                f"(deadline: day {DARF_DUE_BY_DAY} of current month)."
            ),
            overdue=overdue,
            fiscal_mes=fiscal_mes,
        )
