"""Tests for deadline checks CLI and rules."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import pjtracker.app as app_module
from pjtracker.app import init_db, save_darf_entry, save_withdraw
from pjtracker.checks.cli import main
from pjtracker.checks.darf_receipt import PreviousMonthDarfReceiptCheck
from pjtracker.checks.prolabore import ProLaboreWithdrawCheck
from pjtracker.checks.runner import (
    build_alert_subject,
    notify_failures,
    run_checks,
)


@contextmanager
def temporary_app_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        original_db_path = app_module.DB_PATH
        original_pdf_dir = app_module.PDF_DIR
        original_images_dir = app_module.IMAGES_DIR
        app_module.DB_PATH = root / "pjtracker.db"
        app_module.PDF_DIR = root / "pdfs"
        app_module.IMAGES_DIR = root / "images"
        try:
            init_db()
            yield root
        finally:
            app_module.DB_PATH = original_db_path
            app_module.PDF_DIR = original_pdf_dir
            app_module.IMAGES_DIR = original_images_dir


# --- Pro-labore ---


def test_prolabore_due_window():
    check = ProLaboreWithdrawCheck()
    assert check.due_today(date(2026, 5, 4)) is False
    assert check.due_today(date(2026, 5, 5)) is True
    assert check.due_today(date(2026, 5, 31)) is True


def test_prolabore_pass_with_matching_withdraw():
    with temporary_app_paths():
        save_withdraw(
            fiscal_mes="2026-05",
            amount_brl=1442.69,
            notes="Prolabore mensal",
        )
        result = ProLaboreWithdrawCheck().run(date(2026, 5, 10))
        assert result.passed is True
        assert result.fiscal_mes == "2026-05"


def test_prolabore_fail_wrong_amount():
    with temporary_app_paths():
        save_withdraw(
            fiscal_mes="2026-05",
            amount_brl=1500.0,
            notes="prolabore",
        )
        result = ProLaboreWithdrawCheck().run(date(2026, 5, 10))
        assert result.passed is False


def test_prolabore_fail_missing_notes_token():
    with temporary_app_paths():
        save_withdraw(
            fiscal_mes="2026-05",
            amount_brl=1442.69,
            notes="saque pessoal",
        )
        result = ProLaboreWithdrawCheck().run(date(2026, 5, 10))
        assert result.passed is False


def test_prolabore_fail_wrong_month():
    with temporary_app_paths():
        save_withdraw(
            fiscal_mes="2026-04",
            amount_brl=1442.69,
            notes="prolabore",
        )
        result = ProLaboreWithdrawCheck().run(date(2026, 5, 10))
        assert result.passed is False
        assert result.fiscal_mes == "2026-05"


# --- DARF ---


def test_darf_always_due():
    check = PreviousMonthDarfReceiptCheck()
    assert check.due_today(date(2026, 5, 1)) is True
    assert check.due_today(date(2026, 5, 20)) is True
    assert check.due_today(date(2026, 5, 21)) is True


def test_darf_pass_with_receipt():
    with temporary_app_paths():
        ok, _ = save_darf_entry(
            pdf_path="pdfs/darf.pdf",
            value=100.0,
            emission_date="01/04/2026",
            deadline_date="20/05/2026",
            receipt_path="images/darf_receipt.jpg",
            fiscal_mes="2026-04",
        )
        assert ok is True
        result = PreviousMonthDarfReceiptCheck().run(date(2026, 5, 15))
        assert result.passed is True
        assert result.overdue is False
        assert result.fiscal_mes == "2026-04"


def test_darf_fail_without_receipt_warn():
    with temporary_app_paths():
        ok, _ = save_darf_entry(
            pdf_path="pdfs/darf.pdf",
            value=100.0,
            emission_date="01/04/2026",
            deadline_date="20/05/2026",
            receipt_path=None,
            fiscal_mes="2026-04",
        )
        assert ok is True
        result = PreviousMonthDarfReceiptCheck().run(date(2026, 5, 15))
        assert result.passed is False
        assert result.overdue is False


def test_darf_fail_overdue_after_day_20():
    with temporary_app_paths():
        result = PreviousMonthDarfReceiptCheck().run(date(2026, 5, 21))
        assert result.passed is False
        assert result.overdue is True
        assert result.fiscal_mes == "2026-04"
        assert "OVERDUE" in result.message


def test_darf_previous_month_january_wrap():
    with temporary_app_paths():
        result = PreviousMonthDarfReceiptCheck().run(date(2026, 1, 10))
        assert result.fiscal_mes == "2025-12"
        assert result.passed is False


# --- Runner / notify ---


def test_run_checks_respects_due_window():
    with temporary_app_paths():
        checks = [ProLaboreWithdrawCheck(), PreviousMonthDarfReceiptCheck()]
        early = run_checks(checks, date(2026, 5, 4), force_all=False)
        assert [r.check_id for r in early] == ["darf_previous_month_receipt"]

        forced = run_checks(checks, date(2026, 5, 4), force_all=True)
        assert {r.check_id for r in forced} == {
            "prolabore_withdraw",
            "darf_previous_month_receipt",
        }


def test_notify_failures_dry_path_does_not_send_on_pass():
    notifier = MagicMock()
    with temporary_app_paths():
        save_withdraw(
            fiscal_mes="2026-05",
            amount_brl=1442.69,
            notes="prolabore",
        )
        ok, _ = save_darf_entry(
            pdf_path="pdfs/darf.pdf",
            value=50.0,
            emission_date="01/04/2026",
            deadline_date="20/05/2026",
            receipt_path="images/r.jpg",
            fiscal_mes="2026-04",
        )
        assert ok is True
        results = run_checks(
            [ProLaboreWithdrawCheck(), PreviousMonthDarfReceiptCheck()],
            date(2026, 5, 10),
            force_all=True,
        )
        assert all(r.passed for r in results)
        sent = notify_failures(notifier, results, date(2026, 5, 10))
        assert sent is False
        notifier.send.assert_not_called()


def test_notify_failures_sends_on_fail():
    notifier = MagicMock()
    with temporary_app_paths():
        results = run_checks(
            [ProLaboreWithdrawCheck()],
            date(2026, 5, 10),
            force_all=True,
        )
        assert results[0].passed is False
        sent = notify_failures(notifier, results, date(2026, 5, 10))
        assert sent is True
        notifier.send.assert_called_once()
        subject = notifier.send.call_args.args[0]
        assert subject.startswith("[pjtracker] ALERT:")


def test_build_alert_subject_overdue():
    from pjtracker.checks.base import CheckResult

    failures = [
        CheckResult(
            check_id="darf_previous_month_receipt",
            passed=False,
            message="missing",
            overdue=True,
            fiscal_mes="2026-04",
        )
    ]
    subject = build_alert_subject(failures, date(2026, 5, 25))
    assert subject.startswith("[pjtracker] OVERDUE:")


def test_cli_dry_run_exit_codes(capsys: pytest.CaptureFixture[str]):
    with temporary_app_paths():
        # Missing checks → exit 1
        code = main(["--dry-run", "--force-all", "--date", "2026-05-10"])
        assert code == 1
        out = capsys.readouterr().out
        assert "FAIL" in out or "failed" in out

        save_withdraw(
            fiscal_mes="2026-05",
            amount_brl=1442.69,
            notes="prolabore",
        )
        save_darf_entry(
            pdf_path="pdfs/darf.pdf",
            value=50.0,
            emission_date="01/04/2026",
            deadline_date="20/05/2026",
            receipt_path="images/r.jpg",
            fiscal_mes="2026-04",
        )
        code = main(["--dry-run", "--force-all", "--date", "2026-05-10"])
        assert code == 0
