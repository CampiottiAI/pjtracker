"""API smoke tests for casa and fluxo."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pjtracker.api.main import app
import pjtracker.casa.storage as casa_storage


@contextmanager
def temporary_casa_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        casa_dir = root / "casa"
        original_dir = casa_storage.CASA_DATA_DIR
        original_history = casa_storage.HISTORY_PATH
        original_fixed = casa_storage.FIXED_BILLS_PATH
        original_people = casa_storage.PEOPLE_PATH
        casa_storage.CASA_DATA_DIR = casa_dir
        casa_storage.HISTORY_PATH = casa_dir / "bills_history.json"
        casa_storage.FIXED_BILLS_PATH = casa_dir / "fixed_bills.json"
        casa_storage.PEOPLE_PATH = casa_dir / "people.json"
        try:
            yield casa_dir
        finally:
            casa_storage.CASA_DATA_DIR = original_dir
            casa_storage.HISTORY_PATH = original_history
            casa_storage.FIXED_BILLS_PATH = original_fixed
            casa_storage.PEOPLE_PATH = original_people


@pytest.fixture
def client():
    return TestClient(app)


def test_casa_people_default(client: TestClient):
    with temporary_casa_paths():
        r = client.get("/api/v1/casa/people")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 2
    ids = {p["id"] for p in items}
    assert "rael" in ids and "fer" in ids


def test_casa_save_month_and_fluxo(client: TestClient):
    with temporary_casa_paths():
        casa_storage.save_fixed_bills(
            [
                {"name": "Internet", "value": 100.0, "paid_by": "rael"},
                {"name": "Aluguel", "value": 2000.0, "paid_by": "rael"},
            ]
        )
        payload = {
            "fiscal_mes": "2026-08",
            "person_ids": ["rael", "fer"],
            "pcts": [0.6, 0.4],
            "nubank": 3000.0,
            "fixed_bills": [
                {"name": "Internet", "value": 100.0, "paid_by": "rael"},
                {"name": "Aluguel", "value": 2000.0, "paid_by": "rael"},
            ],
            "other_expenses": [
                {"description": "Mercado", "amount": 200.0, "paid_by": "fer"},
            ],
            "cc_reserved_amount": 0.0,
            "cc_reserved_person_id": None,
        }
        save_r = client.put("/api/v1/casa/months/2026-08", json=payload)
        assert save_r.status_code == 200
        assert save_r.json()["saved"] is True

        fluxo_r = client.get("/api/v1/fluxo", params={"fiscal_mes": "2026-08"})
    assert fluxo_r.status_code == 200
    body = fluxo_r.json()
    assert body["casa"]["saved"] is True
    assert body["casa"]["household_total_brl"] > 0
    assert body["coverage"]["primary_share_brl"] > 0


def test_casa_workspace_unsaved(client: TestClient):
    with temporary_casa_paths():
        casa_storage.save_fixed_bills(
            [{"name": "Internet", "value": 150.0, "paid_by": "rael"}]
        )
        r = client.get("/api/v1/casa/workspace", params={"fiscal_mes": "2026-09"})
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] is False
    assert len(body["fixed_bills"]) == 1
