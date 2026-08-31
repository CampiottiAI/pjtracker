"""Evaluate due checks and optionally notify on failures."""

from __future__ import annotations

from datetime import date

from pjtracker.checks.base import CheckResult, DeadlineCheck
from pjtracker.checks.notify.base import Notifier


def run_checks(
    checks: list[DeadlineCheck],
    today: date,
    *,
    force_all: bool = False,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        if force_all or check.due_today(today):
            results.append(check.run(today))
    return results


def format_results_report(results: list[CheckResult], today: date) -> str:
    if not results:
        return f"pjtracker-check ({today.isoformat()}): no checks due."
    lines = [f"pjtracker-check results for {today.isoformat()}:", ""]
    for r in results:
        status = "PASS" if r.passed else ("OVERDUE" if r.overdue else "FAIL")
        mes = f" [{r.fiscal_mes}]" if r.fiscal_mes else ""
        lines.append(f"[{status}] {r.check_id}{mes}: {r.message}")
    failures = [r for r in results if not r.passed]
    lines.append("")
    lines.append(
        f"{len(results) - len(failures)} passed, {len(failures)} failed."
    )
    return "\n".join(lines)


def build_alert_subject(failures: list[CheckResult], today: date) -> str:
    if any(r.overdue for r in failures):
        prefix = "OVERDUE"
    else:
        prefix = "ALERT"
    n = len(failures)
    return f"[pjtracker] {prefix}: {n} deadline check{'s' if n != 1 else ''} failed ({today.isoformat()})"


def notify_failures(
    notifier: Notifier,
    results: list[CheckResult],
    today: date,
) -> bool:
    """Send an alert if any check failed. Returns True if email was sent."""
    failures = [r for r in results if not r.passed]
    if not failures:
        return False
    subject = build_alert_subject(failures, today)
    body = format_results_report(results, today)
    notifier.send(subject, body)
    return True
