"""CLI for independent deadline checks (cron-friendly).

Example crontab (daily 09:00):

  0 9 * * * cd /path/to/pjtracker && uv run pjtracker-check >> /tmp/pjtracker-check.log 2>&1
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pjtracker.app as app_module
from pjtracker.app import init_db
from pjtracker.checks.notify.email import EmailConfig, EmailNotifier
from pjtracker.checks.registry import get_registered_checks
from pjtracker.checks.runner import (
    format_results_report,
    notify_failures,
    run_checks,
)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Expected YYYY-MM-DD, got {value!r}"
        ) from exc


def _apply_db_path_from_env() -> None:
    raw = os.environ.get("PJTRACKER_DB_PATH", "").strip()
    if not raw:
        return
    db_path = Path(raw).expanduser().resolve()
    app_module.DB_PATH = db_path
    root = db_path.parent
    app_module.PDF_DIR = root / "pdfs"
    app_module.IMAGES_DIR = root / "images"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pjtracker-check",
        description=(
            "Run PJ fiscal deadline checks against the local SQLite DB "
            "and optionally email failures via Gmail SMTP."
        ),
        epilog=(
            "Cron example (daily 09:00):\n"
            "  0 9 * * * cd /path/to/pjtracker && "
            "uv run pjtracker-check >> /tmp/pjtracker-check.log 2>&1\n\n"
            "Email env: PJTRACKER_SMTP_USER, PJTRACKER_SMTP_PASSWORD, "
            "PJTRACKER_ALERT_TO "
            "(optional: PJTRACKER_ALERT_FROM, PJTRACKER_SMTP_HOST, "
            "PJTRACKER_SMTP_PORT, PJTRACKER_DB_PATH)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results only; do not send email.",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Run all registered checks, ignoring calendar due windows.",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Simulate 'today' (default: system date).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    today: date = args.date or date.today()

    _apply_db_path_from_env()
    init_db()

    checks = get_registered_checks()
    results = run_checks(checks, today, force_all=args.force_all)
    report = format_results_report(results, today)
    print(report)

    failures = [r for r in results if not r.passed]
    if failures and not args.dry_run:
        try:
            config = EmailConfig.from_env()
        except ValueError as exc:
            print(f"Cannot send email: {exc}", file=sys.stderr)
            return 1
        notify_failures(EmailNotifier(config), results, today)
        print("Alert email sent.", file=sys.stderr)
    elif failures and args.dry_run:
        print("Dry-run: skipping email.", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
