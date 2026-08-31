"""Pro-labore withdraw deadline check."""

from __future__ import annotations

from datetime import date

from pjtracker.app import get_withdraws
from pjtracker.checks.base import CheckResult, fiscal_mes_for

PRO_LABORE_AMOUNT_BRL = 1442.69
PRO_LABORE_AMOUNT_TOLERANCE = 0.01
PRO_LABORE_NOTES_TOKEN = "prolabore"
PRO_LABORE_DUE_FROM_DAY = 5


class ProLaboreWithdrawCheck:
    @property
    def id(self) -> str:
        return "prolabore_withdraw"

    def due_today(self, today: date) -> bool:
        return today.day >= PRO_LABORE_DUE_FROM_DAY

    def run(self, today: date) -> CheckResult:
        fiscal_mes = fiscal_mes_for(today)
        withdraws = get_withdraws(fiscal_mes=fiscal_mes)
        for row in withdraws:
            amount = row.get("amount_brl")
            notes = (row.get("notes") or "").lower()
            if amount is None:
                continue
            try:
                amount_f = float(amount)
            except (TypeError, ValueError):
                continue
            if (
                abs(amount_f - PRO_LABORE_AMOUNT_BRL) < PRO_LABORE_AMOUNT_TOLERANCE
                and PRO_LABORE_NOTES_TOKEN in notes
            ):
                return CheckResult(
                    check_id=self.id,
                    passed=True,
                    message=(
                        f"Pro-labore withdraw found for {fiscal_mes} "
                        f"(R$ {amount_f:.2f})."
                    ),
                    fiscal_mes=fiscal_mes,
                )
        return CheckResult(
            check_id=self.id,
            passed=False,
            message=(
                f"Missing pro-labore saque for {fiscal_mes}: "
                f"need withdraw ≈ R$ {PRO_LABORE_AMOUNT_BRL:.2f} "
                f'with notes containing "{PRO_LABORE_NOTES_TOKEN}".'
            ),
            fiscal_mes=fiscal_mes,
        )
