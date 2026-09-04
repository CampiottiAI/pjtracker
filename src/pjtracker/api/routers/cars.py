"""Cars and maintenance quotes API."""

from __future__ import annotations

import json
import mimetypes
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from pjtracker.api.errors import conflict
from pjtracker.casa import cars_storage, maintenance_storage
from pjtracker.casa.cars_storage import car_label
from pjtracker.parsers.maintenance_parser import (
    analyze_quote,
    apply_car_defaults,
    parse_quote,
)

router = APIRouter(prefix="/cars", tags=["cars"])

_QUOTE_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_ATTACHMENT_MIME = {
    **_QUOTE_MIME,
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
}


class CarCreate(BaseModel):
    name: str = Field(min_length=1)
    id: str | None = None
    placa: str | None = None
    modelo: str | None = None


class CarUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    placa: str | None = None
    modelo: str | None = None


def _guess_mime(filename: str, content_type: str | None, allowed: dict[str, str]) -> str:
    if content_type and content_type != "application/octet-stream":
        return content_type
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in allowed:
        return allowed[suffix]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _record_to_json(record: maintenance_storage.MaintenanceRecord) -> dict[str, Any]:
    out = dict(record)
    # Prefer download routes; keep path for debug but UI should not use it.
    return out


def _file_response(relative_path: str, filename: str, mime_type: str) -> FileResponse:
    path = maintenance_storage.resolve_file_path(relative_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not maintenance_storage.is_under_maintenance_files(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type=mime_type or None, filename=filename)


# ---------------------------------------------------------------------------
# Maintenance by record id (static path before /{car_id})
# ---------------------------------------------------------------------------


@router.get("/maintenance/{record_id}")
def get_maintenance(record_id: str) -> dict:
    record = maintenance_storage.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    return _record_to_json(record)


@router.delete("/maintenance/{record_id}", status_code=204)
def delete_maintenance(record_id: str) -> None:
    if not maintenance_storage.delete_record(record_id):
        raise HTTPException(status_code=404, detail="Maintenance record not found")


@router.post("/maintenance/{record_id}/attachments")
async def add_maintenance_attachment(
    record_id: str,
    file: UploadFile = File(...),
) -> dict:
    record = maintenance_storage.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")
    filename = file.filename or "attachment"
    mime = _guess_mime(filename, file.content_type, _ATTACHMENT_MIME)
    attachment = maintenance_storage.add_attachment(record_id, data, filename, mime)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    return dict(attachment)


@router.get("/maintenance/{record_id}/source")
def download_maintenance_source(record_id: str) -> FileResponse:
    record = maintenance_storage.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    source = record["source"]
    return _file_response(source["path"], source["filename"], source["mime_type"])


@router.get("/maintenance/{record_id}/attachments/{att_id}")
def download_maintenance_attachment(record_id: str, att_id: str) -> FileResponse:
    record = maintenance_storage.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    for att in record.get("attachments") or []:
        if att["id"] == att_id:
            return _file_response(att["path"], att["filename"], att["mime_type"])
    raise HTTPException(status_code=404, detail="Attachment not found")


# ---------------------------------------------------------------------------
# Cars CRUD
# ---------------------------------------------------------------------------


@router.get("")
def list_cars() -> dict:
    items = [dict(c) for c in cars_storage.load_cars()]
    for item in items:
        item["label"] = car_label(cars_storage.Car(item))  # type: ignore[arg-type]
    return {"items": items}


@router.post("")
def create_car(payload: CarCreate) -> dict:
    name = payload.name.strip()
    car_id = (payload.id or "").strip() or cars_storage.slug_from_name(name)
    placa = (payload.placa or "").strip() or None
    modelo = (payload.modelo or "").strip() or None
    try:
        car = cars_storage.add_car(car_id, name, placa=placa, modelo=modelo)
    except ValueError as e:
        raise conflict("car_id_exists", str(e)) from e
    out = dict(car)
    out["label"] = car_label(car)
    return out


@router.patch("/{car_id}")
def patch_car(car_id: str, payload: CarUpdate) -> dict:
    if payload.name is None and payload.placa is None and payload.modelo is None:
        raise HTTPException(status_code=422, detail="No fields to update")
    car = cars_storage.update_car(
        car_id,
        name=payload.name.strip() if payload.name is not None else None,
        placa=payload.placa.strip() if payload.placa is not None else None,
        modelo=payload.modelo.strip() if payload.modelo is not None else None,
    )
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    out = dict(car)
    out["label"] = car_label(car)
    return out


@router.delete("/{car_id}", status_code=204)
def delete_car(car_id: str) -> None:
    cars = cars_storage.load_cars()
    if not any(c["id"] == car_id for c in cars):
        raise HTTPException(status_code=404, detail="Car not found")
    if len(cars) <= 1:
        raise conflict("last_car", "Cannot delete the last car")
    cars_storage.remove_car(car_id)


# ---------------------------------------------------------------------------
# Maintenance under a car
# ---------------------------------------------------------------------------


@router.get("/{car_id}/maintenance")
def list_car_maintenance(car_id: str) -> dict:
    if not cars_storage.get_car(car_id):
        raise HTTPException(status_code=404, detail="Car not found")
    items = [_record_to_json(r) for r in maintenance_storage.load_records(car_id=car_id)]
    return {"items": items}


@router.post("/{car_id}/maintenance/parse-preview")
async def parse_maintenance_preview(
    car_id: str,
    file: UploadFile = File(...),
) -> dict:
    car = cars_storage.get_car(car_id)
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")
    filename = file.filename or "orcamento.pdf"
    mime = _guess_mime(filename, file.content_type, _QUOTE_MIME)
    result = parse_quote(data, filename=filename, mime_type=mime)
    if not result.ok or result.data is None:
        raise HTTPException(
            status_code=422,
            detail=result.error or "Failed to extract quote data",
        )
    extracted = apply_car_defaults(result.data.model_dump(), car)
    return {
        "extracted": extracted,
        "filename": filename,
        "mime_type": mime,
    }


@router.post("/{car_id}/maintenance")
async def create_maintenance(
    car_id: str,
    file: UploadFile = File(...),
    extracted: str = Form(..., description="JSON string of edited extraction"),
) -> dict:
    car = cars_storage.get_car(car_id)
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")
    try:
        extracted_obj = json.loads(extracted)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail="extracted must be valid JSON") from e
    if not isinstance(extracted_obj, dict):
        raise HTTPException(status_code=422, detail="extracted must be a JSON object")

    filename = file.filename or "orcamento.pdf"
    mime = _guess_mime(filename, file.content_type, _QUOTE_MIME)

    previous = maintenance_storage.find_previous_record(car_id)
    record = maintenance_storage.create_record(
        car_id=car_id,
        source_bytes=data,
        source_filename=filename,
        source_mime=mime,
        extracted=extracted_obj,
        analysis=None,
    )

    warning: str | None = None
    prev_extracted = previous.get("extracted") if previous else None
    analysis_result = analyze_quote(extracted_obj, prev_extracted)
    if analysis_result.ok and analysis_result.data is not None:
        updated = maintenance_storage.update_record_analysis(
            record["id"], analysis_result.data.model_dump()
        )
        if updated:
            record = updated
    else:
        warning = analysis_result.error or "Analysis failed"

    out = _record_to_json(record)
    if warning:
        out["warning"] = warning
    return out
