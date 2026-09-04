"""API smoke tests for cars and maintenance."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from pjtracker.api.main import app
from pjtracker.casa import storage as casa_storage
from pjtracker.llm_extraction import LLMExtractionResult


class _FakeOrcamento(BaseModel):
    tipo_documento: str | None = "orcamento"
    oficina: str | None = "Oficina Teste"
    data: str | None = "01/09/2026"
    cliente: str | None = "Rael"
    veiculo: dict | None = None
    itens: list = []
    total: float | None = 1500.0
    consultor: str | None = None
    observacoes: str | None = None


class _FakeAnalise(BaseModel):
    resumo: str = "Revisão de rotina"
    mudancas: str | None = None
    motivo_geral: str = "Manutenção preventiva"


@contextmanager
def temporary_cars_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        casa_dir = root / "data" / "casa"
        casa_dir.mkdir(parents=True)
        original_dir = casa_storage.CASA_DATA_DIR
        original_project = None
        import pjtracker.app as app_module

        original_project = app_module.PROJECT_ROOT
        casa_storage.CASA_DATA_DIR = casa_dir
        app_module.PROJECT_ROOT = root
        try:
            yield casa_dir
        finally:
            casa_storage.CASA_DATA_DIR = original_dir
            app_module.PROJECT_ROOT = original_project


@pytest.fixture
def client():
    return TestClient(app)


def test_cars_crud(client: TestClient):
    with temporary_cars_paths():
        empty = client.get("/api/v1/cars")
        assert empty.status_code == 200
        assert empty.json()["items"] == []

        created = client.post(
            "/api/v1/cars",
            json={"name": "Yaris", "placa": "FSY9E03", "modelo": "Toyota Yaris"},
        )
        assert created.status_code == 200
        body = created.json()
        assert body["id"] == "yaris"
        assert body["placa"] == "FSY9E03"
        assert "Yaris" in body["label"]

        listed = client.get("/api/v1/cars")
        assert len(listed.json()["items"]) == 1

        patched = client.patch(
            "/api/v1/cars/yaris",
            json={"name": "Yaris XS", "placa": "FSY9E03"},
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Yaris XS"

        # Cannot delete last car
        deleted = client.delete("/api/v1/cars/yaris")
        assert deleted.status_code == 409

        client.post("/api/v1/cars", json={"name": "Golf", "id": "golf"})
        deleted2 = client.delete("/api/v1/cars/golf")
        assert deleted2.status_code == 204
        assert len(client.get("/api/v1/cars").json()["items"]) == 1


def test_parse_preview_does_not_save(client: TestClient):
    with temporary_cars_paths():
        client.post("/api/v1/cars", json={"name": "Yaris", "placa": "ABC1D23"})
        fake = _FakeOrcamento(veiculo={"km": 40000})
        with patch(
            "pjtracker.api.routers.cars.parse_quote",
            return_value=LLMExtractionResult(data=fake),
        ):
            r = client.post(
                "/api/v1/cars/yaris/maintenance/parse-preview",
                files={"file": ("quote.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["extracted"]["oficina"] == "Oficina Teste"
        assert data["extracted"]["veiculo"]["placa"] == "ABC1D23"
        assert client.get("/api/v1/cars/yaris/maintenance").json()["items"] == []
        assert not (casa_storage.CASA_DATA_DIR / "maintenance" / "files").exists() or not any(
            (casa_storage.CASA_DATA_DIR / "maintenance" / "files").iterdir()
        )


def test_create_maintenance_with_analysis(client: TestClient):
    with temporary_cars_paths():
        client.post("/api/v1/cars", json={"name": "Yaris"})
        extracted = {
            "oficina": "Oficina Editada",
            "data": "02/09/2026",
            "total": 2000.0,
            "itens": [{"descricao": "Óleo", "valor_total": 200.0}],
            "veiculo": {"km": 41000},
        }
        with patch(
            "pjtracker.api.routers.cars.analyze_quote",
            return_value=LLMExtractionResult(data=_FakeAnalise()),
        ):
            r = client.post(
                "/api/v1/cars/yaris/maintenance",
                data={"extracted": json.dumps(extracted)},
                files={"file": ("quote.pdf", b"%PDF-1.4 content", "application/pdf")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["extracted"]["oficina"] == "Oficina Editada"
        assert body["analysis"]["resumo"] == "Revisão de rotina"
        assert "warning" not in body

        record_id = body["id"]
        got = client.get(f"/api/v1/cars/maintenance/{record_id}")
        assert got.status_code == 200

        src = client.get(f"/api/v1/cars/maintenance/{record_id}/source")
        assert src.status_code == 200
        assert src.content == b"%PDF-1.4 content"


def test_create_maintenance_analysis_failure_still_saves(client: TestClient):
    with temporary_cars_paths():
        client.post("/api/v1/cars", json={"name": "Yaris"})
        with patch(
            "pjtracker.api.routers.cars.analyze_quote",
            return_value=LLMExtractionResult(data=None, error="boom"),
        ):
            r = client.post(
                "/api/v1/cars/yaris/maintenance",
                data={"extracted": json.dumps({"oficina": "X", "total": 10})},
                files={"file": ("q.pdf", b"pdfbytes", "application/pdf")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["analysis"] is None
        assert body["warning"] == "boom"
        assert len(client.get("/api/v1/cars/yaris/maintenance").json()["items"]) == 1


def test_attachment_and_delete_record(client: TestClient):
    with temporary_cars_paths():
        client.post("/api/v1/cars", json={"name": "Yaris"})
        with patch(
            "pjtracker.api.routers.cars.analyze_quote",
            return_value=LLMExtractionResult(data=_FakeAnalise()),
        ):
            created = client.post(
                "/api/v1/cars/yaris/maintenance",
                data={"extracted": json.dumps({"oficina": "X"})},
                files={"file": ("q.pdf", b"source", "application/pdf")},
            )
        record_id = created.json()["id"]
        files_path = casa_storage.CASA_DATA_DIR / "maintenance" / "files" / record_id
        assert files_path.exists()

        att = client.post(
            f"/api/v1/cars/maintenance/{record_id}/attachments",
            files={"file": ("photo.jpg", b"imagedata", "image/jpeg")},
        )
        assert att.status_code == 200
        att_id = att.json()["id"]

        dl = client.get(f"/api/v1/cars/maintenance/{record_id}/attachments/{att_id}")
        assert dl.status_code == 200
        assert dl.content == b"imagedata"

        deleted = client.delete(f"/api/v1/cars/maintenance/{record_id}")
        assert deleted.status_code == 204
        assert not files_path.exists()
        assert client.get(f"/api/v1/cars/maintenance/{record_id}").status_code == 404
