"""Smoke tests for FastAPI routes."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import pjtracker.app as app_module
from pjtracker.api.main import app
from pjtracker.app import (
    init_db,
    save_boleto_entry,
    save_boleto_pdf,
    save_darf_entry,
    save_darf_pdf,
    save_caixinha_pdf,
    save_extrato_entry,
    save_extrato_pdf,
    save_irpj_csll_entry,
    save_irpj_csll_pdf,
    save_nf_entry,
    save_pdf,
)
from pjtracker.parsers.boleto_parser import BoletoParsed, ReceiptParsed
from pjtracker.parsers.darf_parser import DarfParsed
from pjtracker.parsers.nf_parser import NFParsed


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
            yield root
        finally:
            app_module.DB_PATH = original_db_path
            app_module.PDF_DIR = original_pdf_dir
            app_module.IMAGES_DIR = original_images_dir


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready(client: TestClient):
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    data = r.json()
    assert "ready" in data
    assert "database" in data
    assert "llm_key_configured" in data


def test_nf_parse_preview_mocked(client: TestClient):
    fake = NFParsed(
        company="Acme",
        usd=100.0,
        rate=5.2,
        spread=3.0,
        spread_was_default=False,
        nf_date="15/03/2025 12:00:00",
        verification_code="XYZ",
        payment_via="Higlobe",
        source="test",
    )
    with patch("pjtracker.api.routers.nfs.parse_nf_pdf", return_value=fake):
        r = client.post(
            "/api/v1/nfs/parse-preview",
            files={"file": ("nf.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["usd"] == 100.0
    assert body["brl"] is not None
    assert body["brl"]["brl_no_spread"] == 520.0


def test_nf_duplicate_returns_409(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_pdf(b"%PDF", "CODE", "01/01/2025 00:00:00", 50.0)
        save_nf_entry(
            company="C",
            usd=50.0,
            rate=5.0,
            spread=3.0,
            brl_no_spread=250.0,
            brl_with_spread=242.5,
            nf_date="01/01/2025 00:00:00",
            verification_code="CODE",
            payment_via=None,
            pdf_path=str(pdf_path),
            fiscal_mes="2025-01",
        )
        fake = NFParsed(
            company="C",
            usd=50.0,
            rate=5.0,
            spread=3.0,
            spread_was_default=False,
            nf_date="01/01/2025 00:00:00",
            verification_code="CODE",
            payment_via=None,
            source="test",
        )
        with patch("pjtracker.api.routers.nfs.parse_nf_pdf", return_value=fake):
            r = client.post(
                "/api/v1/nfs",
                data={"fiscal_mes": "2025-01"},
                files={"file": ("nf.pdf", b"%PDF-1.4", "application/pdf")},
            )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "duplicate_nf"


def test_nf_pdf_download_headers(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_pdf(b"%PDF-test", "VC", "02/02/2025 00:00:00", 10.0)
        inserted, nf_id = save_nf_entry(
            company=None,
            usd=10.0,
            rate=5.0,
            spread=3.0,
            brl_no_spread=50.0,
            brl_with_spread=48.5,
            nf_date="02/02/2025 00:00:00",
            verification_code="VC",
            payment_via=None,
            pdf_path=str(pdf_path),
            fiscal_mes="2025-02",
        )
        assert inserted
        r = client.get(f"/api/v1/nfs/{nf_id}/pdf")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content.startswith(b"%PDF")


def test_analytics_nf_series(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_pdf(b"%PDF", "X", "10/03/2025 00:00:00", 20.0)
        save_nf_entry(
            company=None,
            usd=20.0,
            rate=5.0,
            spread=0.0,
            brl_no_spread=100.0,
            brl_with_spread=100.0,
            nf_date="10/03/2025 00:00:00",
            verification_code="X",
            payment_via=None,
            pdf_path=str(pdf_path),
            fiscal_mes="2025-03",
        )
        r = client.get(
            "/api/v1/analytics/nf-series",
            params={
                "date_from": "2025-03-01",
                "date_to": "2025-03-31",
            },
        )
    assert r.status_code == 200
    pts = r.json()["points"]
    assert len(pts) == 1
    assert pts[0]["usd"] == 20.0


def test_fiscal_months_list(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_pdf(b"%PDF", "Y", "11/04/2025 00:00:00", 1.0)
        save_nf_entry(
            company=None,
            usd=1.0,
            rate=1.0,
            spread=0.0,
            brl_no_spread=1.0,
            brl_with_spread=1.0,
            nf_date="11/04/2025 00:00:00",
            verification_code="Y",
            payment_via=None,
            pdf_path=str(pdf_path),
            fiscal_mes="2025-04",
        )
        r = client.get("/api/v1/fiscal-months")
    assert r.status_code == 200
    assert "2025-04" in r.json()["months"]


def test_patch_boleto_fields_persists_and_recomputes_match_status(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_boleto_pdf(b"%PDF", emission_date="01/01/2025", value=100.0)
        inserted, boleto_id = save_boleto_entry(
            pdf_path=str(pdf_path),
            value=100.0,
            emission_date="01/01/2025",
            deadline_date="15/01/2025",
            codigo_barras="old_raw",
            codigo_barras_digits="1111",
            receipt_path=None,
            receipt_date="01/01/2025 10:00:00",
            receipt_value=100.0,
            receipt_codigo_barras="old_receipt_raw",
            receipt_codigo_barras_digits="9999",
            receipt_match_status="mismatch",
            fiscal_mes="2025-01",
        )
        assert inserted and boleto_id is not None

        r = client.patch(
            f"/api/v1/boletos/{boleto_id}/fields",
            json={
                "value": 200.5,
                "emission_date": "05/02/2025",
                "deadline_date": "20/02/2025",
                "codigo_barras": "doc_raw_new",
                "codigo_barras_digits": "123456",
                "receipt_date": "05/02/2025 11:22:33",
                "receipt_value": 200.5,
                "receipt_codigo_barras": "receipt_raw_new",
                "receipt_codigo_barras_digits": "123456",
                "fiscal_mes": "2025-02",
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["value"] == 200.5
    assert body["emission_date"] == "05/02/2025"
    assert body["deadline_date"] == "20/02/2025"
    assert body["codigo_barras_digits"] == "123456"
    assert body["receipt_codigo_barras_digits"] == "123456"
    assert body["receipt_match_status"] == "match"
    assert body["fiscal_mes"] == "2025-02"


def test_patch_boleto_fields_rejects_non_digit_barcode(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_boleto_pdf(b"%PDF", emission_date="01/01/2025", value=100.0)
        inserted, boleto_id = save_boleto_entry(
            pdf_path=str(pdf_path),
            value=100.0,
            emission_date="01/01/2025",
            deadline_date="15/01/2025",
            codigo_barras_digits="1111",
            fiscal_mes="2025-01",
        )
        assert inserted and boleto_id is not None

        r = client.patch(
            f"/api/v1/boletos/{boleto_id}/fields",
            json={
                "value": 100.0,
                "emission_date": "01/01/2025",
                "deadline_date": "15/01/2025",
                "codigo_barras": "abc",
                "codigo_barras_digits": "12A3",
                "receipt_date": None,
                "receipt_value": None,
                "receipt_codigo_barras": None,
                "receipt_codigo_barras_digits": None,
                "fiscal_mes": "2025-01",
            },
        )

    assert r.status_code == 422


def test_reprocess_boleto_refreshes_pdf_only_fields(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_boleto_pdf(b"%PDF", emission_date="01/01/2025", value=100.0)
        inserted, boleto_id = save_boleto_entry(
            pdf_path=str(pdf_path),
            value=100.0,
            emission_date="01/01/2025",
            deadline_date="15/01/2025",
            codigo_barras="old_raw",
            codigo_barras_digits="1111",
            fiscal_mes="2025-01",
        )
        assert inserted and boleto_id is not None

        fake_doc = BoletoParsed(
            value=250.0,
            emission_date="05/02/2025",
            deadline_date="20/02/2025",
            codigo_barras_raw="doc_raw_new",
            codigo_barras_digits="2222",
            source="test",
        )
        with patch("pjtracker.api.routers.boletos.parse_boleto_pdf", return_value=fake_doc):
            r = client.post(f"/api/v1/boletos/{boleto_id}/reprocess")

    assert r.status_code == 200
    body = r.json()
    assert body["value"] == 250.0
    assert body["emission_date"] == "05/02/2025"
    assert body["deadline_date"] == "20/02/2025"
    assert body["codigo_barras"] == "doc_raw_new"
    assert body["codigo_barras_digits"] == "2222"
    assert body["receipt_path"] is None
    assert body["receipt_match_status"] is None
    assert body["fiscal_mes"] == "2025-01"


def test_reprocess_boleto_refreshes_pdf_and_receipt_fields(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_boleto_pdf(b"%PDF", emission_date="01/01/2025", value=100.0)
        inserted, boleto_id = save_boleto_entry(
            pdf_path=str(pdf_path),
            value=100.0,
            emission_date="01/01/2025",
            deadline_date="15/01/2025",
            codigo_barras="old_raw",
            codigo_barras_digits="1111",
            fiscal_mes="2025-01",
        )
        assert inserted and boleto_id is not None

        receipt_path = app_module.save_boleto_receipt(boleto_id, b"fake-image", "png")
        app_module.update_boleto_receipt(
            boleto_id,
            str(receipt_path),
            "01/01/2025 10:00:00",
            receipt_value=100.0,
            receipt_codigo_barras="old_receipt_raw",
            receipt_codigo_barras_digits="9999",
            receipt_match_status="mismatch",
        )

        fake_doc = BoletoParsed(
            value=333.0,
            emission_date="06/02/2025",
            deadline_date="22/02/2025",
            codigo_barras_raw="doc_raw_reprocessed",
            codigo_barras_digits="7777",
            source="test",
        )
        fake_receipt = ReceiptParsed(
            value=333.0,
            payment_datetime="07/02/2025 09:08:07",
            codigo_barras_raw="receipt_raw_reprocessed",
            codigo_barras_digits="7777",
            source="test",
        )
        with (
            patch("pjtracker.api.routers.boletos.parse_boleto_pdf", return_value=fake_doc),
            patch("pjtracker.api.routers.boletos.parse_receipt_image", return_value=fake_receipt),
        ):
            r = client.post(f"/api/v1/boletos/{boleto_id}/reprocess")

    assert r.status_code == 200
    body = r.json()
    assert body["value"] == 333.0
    assert body["codigo_barras"] == "doc_raw_reprocessed"
    assert body["codigo_barras_digits"] == "7777"
    assert body["receipt_date"] == "07/02/2025 09:08:07"
    assert body["receipt_value"] == 333.0
    assert body["receipt_codigo_barras"] == "receipt_raw_reprocessed"
    assert body["receipt_codigo_barras_digits"] == "7777"
    assert body["receipt_match_status"] == "match"
    assert body["fiscal_mes"] == "2025-01"


def test_patch_darf_fields_persists_and_recomputes_match_status(client: TestClient):
    with temporary_app_paths():
        init_db()
        pdf_path = save_darf_pdf(b"%PDF", emission_date="01/03/2025", value=300.0)
        inserted, darf_id = save_darf_entry(
            pdf_path=str(pdf_path),
            value=300.0,
            emission_date="01/03/2025",
            deadline_date="20/03/2025",
            codigo_barras="old_darf_raw",
            codigo_barras_digits="8888",
            receipt_path=None,
            receipt_date="01/03/2025 10:00:00",
            receipt_value=300.0,
            receipt_codigo_barras="old_receipt_raw",
            receipt_codigo_barras_digits="7777",
            receipt_match_status="mismatch",
            fiscal_mes="2025-03",
        )
        assert inserted and darf_id is not None

        r = client.patch(
            f"/api/v1/darfs/{darf_id}/fields",
            json={
                "value": 350.0,
                "emission_date": "02/03/2025",
                "deadline_date": "21/03/2025",
                "codigo_barras": "darf_raw_new",
                "codigo_barras_digits": "654321",
                "receipt_date": "02/03/2025 09:08:07",
                "receipt_value": 350.0,
                "receipt_codigo_barras": "receipt_raw_new",
                "receipt_codigo_barras_digits": "654321",
                "fiscal_mes": "2025-03",
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["value"] == 350.0
    assert body["codigo_barras_digits"] == "654321"
    assert body["receipt_codigo_barras_digits"] == "654321"
    assert body["receipt_match_status"] == "match"


def test_create_irpj_csll_with_receipt(client: TestClient):
    with temporary_app_paths():
        init_db()
        fake_doc = DarfParsed(
            value=420.0,
            emission_date="03/2025",
            deadline_date="31/03/2025",
            codigo_barras_raw="111.222.333",
            codigo_barras_digits="111222333",
            source="test",
        )
        fake_receipt = ReceiptParsed(
            value=420.0,
            payment_datetime="20/03/2025 12:34:56",
            codigo_barras_raw="111 222 333",
            codigo_barras_digits="111222333",
            source="test",
        )
        with (
            patch("pjtracker.api.routers.irpj_csll.parse_irpj_csll_pdf", return_value=fake_doc),
            patch("pjtracker.api.routers.irpj_csll.parse_receipt_image", return_value=fake_receipt),
        ):
            r = client.post(
                "/api/v1/irpj-csll",
                data={"fiscal_mes": "2025-03"},
                files={
                    "file": ("irpj.pdf", b"%PDF-1.4 irpj", "application/pdf"),
                    "receipt": ("receipt.png", b"fake-image", "image/png"),
                },
            )

        assert r.status_code == 200
        body = r.json()
        assert body["value"] == 420.0
        assert body["receipt_value"] == 420.0
        assert body["receipt_match_status"] == "match"

        list_response = client.get("/api/v1/irpj-csll", params={"fiscal_mes": "2025-03"})
        assert list_response.status_code == 200
        listed = list_response.json()
        assert len(listed) == 1
        assert listed[0]["fiscal_mes"] == "2025-03"


def test_fiscal_month_completeness_only_requires_irpj_csll_in_quarter_months(client: TestClient):
    with temporary_app_paths():
        init_db()

        def seed_complete_month(fiscal_mes: str) -> None:
            month = fiscal_mes[-2:]
            nf_date = f"10/{month}/2025 00:00:00"
            pdf_path_1 = save_pdf(b"%PDF", f"NF-{fiscal_mes}-A", nf_date, 10.0)
            save_nf_entry(
                company=None,
                usd=10.0,
                rate=5.0,
                spread=0.0,
                brl_no_spread=50.0,
                brl_with_spread=50.0,
                nf_date=nf_date,
                verification_code=f"NF-{fiscal_mes}-A",
                payment_via=None,
                pdf_path=str(pdf_path_1),
                fiscal_mes=fiscal_mes,
            )
            pdf_path_2 = save_pdf(b"%PDF", f"NF-{fiscal_mes}-B", nf_date, 20.0)
            save_nf_entry(
                company=None,
                usd=20.0,
                rate=5.0,
                spread=0.0,
                brl_no_spread=100.0,
                brl_with_spread=100.0,
                nf_date=nf_date,
                verification_code=f"NF-{fiscal_mes}-B",
                payment_via=None,
                pdf_path=str(pdf_path_2),
                fiscal_mes=fiscal_mes,
            )

            boleto_pdf = save_boleto_pdf(
                b"%PDF",
                emission_date=f"01/{month}/2025",
                value=float(month),
            )
            save_boleto_entry(
                pdf_path=str(boleto_pdf),
                value=float(month),
                emission_date=f"01/{month}/2025",
                deadline_date=f"10/{month}/2025",
                receipt_path="images/boleto.png",
                receipt_date=f"10/{month}/2025 10:00:00",
                fiscal_mes=fiscal_mes,
            )

            darf_pdf = save_darf_pdf(
                b"%PDF",
                emission_date=f"{month}/2025",
                value=float(int(month) + 100),
            )
            save_darf_entry(
                pdf_path=str(darf_pdf),
                value=float(int(month) + 100),
                emission_date=f"{month}/2025",
                deadline_date=f"20/{month}/2025",
                receipt_path="images/darf.png",
                receipt_date=f"20/{month}/2025 10:00:00",
                fiscal_mes=fiscal_mes,
            )

            extrato_pdf = save_extrato_pdf(
                b"%PDF",
                period_start=f"01/{month}/2025",
                period_end=f"28/{month}/2025",
            )
            caixinha_pdf = save_caixinha_pdf(
                b"%PDF",
                period_start=f"01/{month}/2025",
                period_end=f"28/{month}/2025",
            )
            save_extrato_entry(
                extrato_pdf_path=str(extrato_pdf),
                caixinha_pdf_path=str(caixinha_pdf),
                period_start=f"01/{month}/2025",
                period_end=f"28/{month}/2025",
                fiscal_mes=fiscal_mes,
            )

        seed_complete_month("2025-02")
        seed_complete_month("2025-03")

        non_quarter = client.get("/api/v1/fiscal-months/2025-02/completeness")
        assert non_quarter.status_code == 200
        non_quarter_body = non_quarter.json()
        assert non_quarter_body["irpj_csll_required"] is False
        assert non_quarter_body["irpj_csll_ok"] is True
        assert non_quarter_body["month_complete"] is True

        quarter = client.get("/api/v1/fiscal-months/2025-03/completeness")
        assert quarter.status_code == 200
        quarter_body = quarter.json()
        assert quarter_body["irpj_csll_required"] is True
        assert quarter_body["irpj_csll_with_receipt_count"] == 0
        assert quarter_body["irpj_csll_ok"] is False
        assert quarter_body["month_complete"] is False

        irpj_pdf = save_irpj_csll_pdf(b"%PDF", emission_date="03/2025", value=300.0)
        inserted, irpj_id = save_irpj_csll_entry(
            pdf_path=str(irpj_pdf),
            value=300.0,
            emission_date="03/2025",
            deadline_date="31/03/2025",
            receipt_path="images/irpj.png",
            receipt_date="31/03/2025 12:00:00",
            fiscal_mes="2025-03",
        )
        assert inserted and irpj_id is not None

        quarter_after_insert = client.get("/api/v1/fiscal-months/2025-03/completeness")
        assert quarter_after_insert.status_code == 200
        quarter_after_body = quarter_after_insert.json()
        assert quarter_after_body["irpj_csll_with_receipt_count"] == 1
        assert quarter_after_body["irpj_csll_ok"] is True
        assert quarter_after_body["month_complete"] is True
