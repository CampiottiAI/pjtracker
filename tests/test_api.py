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
from pjtracker.app import init_db, save_nf_entry, save_pdf
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
