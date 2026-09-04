"""Persistence for car maintenance records (JSON + files under data/casa/)."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import pjtracker.app as app
from pjtracker.casa import storage as casa_storage


class SourceFile(TypedDict):
    path: str
    filename: str
    mime_type: str


class AttachmentFile(TypedDict):
    id: str
    path: str
    filename: str
    mime_type: str
    uploaded_at: str


class MaintenanceRecord(TypedDict):
    id: str
    created_at: str
    car_id: NotRequired[str | None]
    source: SourceFile
    extracted: dict[str, Any]
    analysis: NotRequired[dict[str, Any] | None]
    attachments: list[AttachmentFile]


def maintenance_dir() -> Path:
    return casa_storage.CASA_DATA_DIR / "maintenance"


def records_path() -> Path:
    return maintenance_dir() / "records.json"


def files_dir() -> Path:
    return maintenance_dir() / "files"


def _ensure_dirs() -> None:
    maintenance_dir().mkdir(parents=True, exist_ok=True)
    files_dir().mkdir(parents=True, exist_ok=True)


def _load_raw() -> list[MaintenanceRecord]:
    _ensure_dirs()
    path = records_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [MaintenanceRecord(r) for r in data]


def _save_raw(records: list[MaintenanceRecord]) -> None:
    _ensure_dirs()
    records_path().write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_records(*, car_id: str | None = None) -> list[MaintenanceRecord]:
    """Load maintenance records, newest first. Optionally filter by car_id."""
    records = _load_raw()
    if car_id is not None:
        records = [r for r in records if r.get("car_id") == car_id]
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


def get_record(record_id: str) -> MaintenanceRecord | None:
    for r in _load_raw():
        if r["id"] == record_id:
            return r
    return None


def find_previous_record(
    car_id: str | None,
    *,
    exclude_id: str | None = None,
) -> MaintenanceRecord | None:
    """Return the most recent record for the same car, excluding exclude_id."""
    if not car_id:
        return None
    for r in load_records(car_id=car_id):
        if exclude_id and r["id"] == exclude_id:
            continue
        return r
    return None


def _record_files_dir(record_id: str) -> Path:
    return files_dir() / record_id


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ]", "_", base)
    return cleaned or "file"


def _rel_to_project(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(app.PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def save_source_file(record_id: str, file_bytes: bytes, filename: str) -> str:
    """Save the original quote file; return relative path from project root."""
    dest_dir = _record_files_dir(record_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename)
    dest = dest_dir / f"source_{safe}"
    dest.write_bytes(file_bytes)
    return _rel_to_project(dest)


def save_attachment_file(record_id: str, file_bytes: bytes, filename: str) -> str:
    """Save an attachment file; return relative path from project root."""
    dest_dir = _record_files_dir(record_id) / "attachments"
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename)
    dest = dest_dir / f"{uuid.uuid4().hex[:8]}_{safe}"
    dest.write_bytes(file_bytes)
    return _rel_to_project(dest)


def resolve_file_path(relative_path: str) -> Path:
    p = Path(relative_path)
    if p.is_absolute():
        return p
    return app.PROJECT_ROOT / relative_path


def is_under_maintenance_files(path: Path) -> bool:
    """True if path resolves under the maintenance files directory."""
    try:
        path.resolve().relative_to(files_dir().resolve())
        return True
    except ValueError:
        return False


def create_record(
    *,
    car_id: str | None,
    source_bytes: bytes,
    source_filename: str,
    source_mime: str,
    extracted: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> MaintenanceRecord:
    record_id = uuid.uuid4().hex
    rel_path = save_source_file(record_id, source_bytes, source_filename)
    record: MaintenanceRecord = {
        "id": record_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "car_id": car_id,
        "source": {
            "path": rel_path,
            "filename": source_filename,
            "mime_type": source_mime,
        },
        "extracted": extracted,
        "analysis": analysis,
        "attachments": [],
    }
    records = _load_raw()
    records.append(record)
    _save_raw(records)
    return record


def update_record_analysis(record_id: str, analysis: dict[str, Any]) -> MaintenanceRecord | None:
    records = _load_raw()
    for i, r in enumerate(records):
        if r["id"] == record_id:
            records[i] = {**r, "analysis": analysis}
            _save_raw(records)
            return records[i]
    return None


def add_attachment(
    record_id: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> AttachmentFile | None:
    records = _load_raw()
    for i, r in enumerate(records):
        if r["id"] == record_id:
            rel_path = save_attachment_file(record_id, file_bytes, filename)
            attachment: AttachmentFile = {
                "id": uuid.uuid4().hex,
                "path": rel_path,
                "filename": filename,
                "mime_type": mime_type,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }
            attachments = list(r.get("attachments") or [])
            attachments.append(attachment)
            records[i] = {**r, "attachments": attachments}
            _save_raw(records)
            return attachment
    return None


def delete_attachment(record_id: str, att_id: str) -> bool:
    """Remove one attachment from a record and delete its file. Returns False if not found."""
    records = _load_raw()
    for i, r in enumerate(records):
        if r["id"] != record_id:
            continue
        attachments = list(r.get("attachments") or [])
        kept: list[AttachmentFile] = []
        removed: AttachmentFile | None = None
        for att in attachments:
            if att["id"] == att_id:
                removed = att
            else:
                kept.append(att)
        if removed is None:
            return False
        records[i] = {**r, "attachments": kept}
        _save_raw(records)
        path = resolve_file_path(removed["path"])
        if path.is_file() and is_under_maintenance_files(path):
            path.unlink(missing_ok=True)
        return True
    return False


def delete_record(record_id: str) -> bool:
    records = _load_raw()
    new_records = [r for r in records if r["id"] != record_id]
    if len(new_records) == len(records):
        return False
    _save_raw(new_records)
    files_path = _record_files_dir(record_id)
    if files_path.exists():
        shutil.rmtree(files_path)
    return True
