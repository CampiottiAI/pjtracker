"""Extratos (bank statements + optional caixinha / Higlobe)."""

from __future__ import annotations

import json
import mimetypes
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from pjtracker.api.errors import conflict
from pjtracker.api.schemas.common import FISCAL_MES_REGEX, PatchFiscalMes
from pjtracker.api.services.paths import resolve_stored_path
from pjtracker.app import (
    delete_extrato,
    get_extrato_by_id,
    get_extratos,
    remove_caixinha_pdf,
    remove_higlobe_pdf,
    save_caixinha_pdf,
    save_extrato_entry,
    save_extrato_pdf,
    save_higlobe_pdf,
    update_caixinha_pdf,
    update_extrato_fiscal_mes,
    update_extrato_pdf,
    update_higlobe_pdf,
)
from pjtracker.parsers.extrato_parser import parse_caixinha_pdf, parse_extrato_pdf, parse_higlobe_pdf

router = APIRouter(prefix="/extratos", tags=["extratos"])


def _extrato_parsed_dict(p) -> dict[str, Any]:
    return {
        "period_start": p.period_start,
        "period_end": p.period_end,
        "saldo_inicial": p.saldo_inicial,
        "rendimento": p.rendimento,
        "total_entradas": p.total_entradas,
        "total_saidas": p.total_saidas,
        "saldo_final": p.saldo_final,
        "entries": p.entries,
        "source": p.source,
    }


def _caixinha_parsed_dict(p) -> dict[str, Any]:
    return {
        "period_start": p.period_start,
        "period_end": p.period_end,
        "saldo_final": p.saldo_final,
        "entries": p.entries,
        "source": p.source,
    }


def _higlobe_parsed_dict(p) -> dict[str, Any]:
    return {
        "period_start": p.period_start,
        "period_end": p.period_end,
        "entries": p.entries,
        "source": p.source,
    }


@router.post("/parse-preview")
async def parse_extrato_bundle_preview(
    extrato: UploadFile = File(..., description="Main extrato PDF"),
    caixinha: UploadFile | None = File(None),
    higlobe: UploadFile | None = File(None),
) -> dict[str, Any]:
    ex_bytes = await extrato.read()
    if not ex_bytes:
        raise HTTPException(status_code=422, detail="Empty extrato PDF")
    try:
        parsed_extrato = parse_extrato_pdf(
            ex_bytes,
            filename=extrato.filename or "extrato.pdf",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    out: dict[str, Any] = {"extrato": _extrato_parsed_dict(parsed_extrato)}

    if caixinha:
        cx = await caixinha.read()
        if cx:
            try:
                parsed_cx = parse_caixinha_pdf(
                    cx,
                    filename=caixinha.filename or "caixinha.pdf",
                )
                out["caixinha"] = _caixinha_parsed_dict(parsed_cx)
            except RuntimeError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
        else:
            out["caixinha"] = None
    else:
        out["caixinha"] = None

    if higlobe:
        hg = await higlobe.read()
        if hg:
            try:
                parsed_hg = parse_higlobe_pdf(
                    hg,
                    filename=higlobe.filename or "higlobe.pdf",
                )
                out["higlobe"] = _higlobe_parsed_dict(parsed_hg)
            except RuntimeError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
        else:
            out["higlobe"] = None
    else:
        out["higlobe"] = None

    return out


@router.post("")
async def create_extrato(
    extrato: UploadFile = File(..., description="Main extrato PDF"),
    fiscal_mes: str = Form(..., description="YYYY-MM"),
    caixinha: UploadFile | None = File(None),
    higlobe: UploadFile | None = File(None),
) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")

    extrato_bytes = await extrato.read()
    if not extrato_bytes:
        raise HTTPException(status_code=422, detail="Empty extrato PDF")

    try:
        parsed_extrato = parse_extrato_pdf(
            extrato_bytes,
            filename=extrato.filename or "extrato.pdf",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    caixinha_bytes: bytes | None = None
    parsed_caixinha = None
    if caixinha:
        caixinha_bytes = await caixinha.read()
        if caixinha_bytes:
            try:
                parsed_caixinha = parse_caixinha_pdf(
                    caixinha_bytes,
                    filename=caixinha.filename or "caixinha.pdf",
                )
            except RuntimeError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e

    higlobe_bytes: bytes | None = None
    parsed_higlobe = None
    if higlobe:
        higlobe_bytes = await higlobe.read()
        if higlobe_bytes:
            try:
                parsed_higlobe = parse_higlobe_pdf(
                    higlobe_bytes,
                    filename=higlobe.filename or "higlobe.pdf",
                )
            except RuntimeError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e

    extrato_pdf_path = save_extrato_pdf(
        extrato_bytes,
        period_start=parsed_extrato.period_start,
        period_end=parsed_extrato.period_end,
    )

    caixinha_pdf_path = None
    if caixinha_bytes is not None and parsed_caixinha is not None:
        caixinha_pdf_path = save_caixinha_pdf(
            caixinha_bytes,
            period_start=parsed_caixinha.period_start or parsed_extrato.period_start,
            period_end=parsed_caixinha.period_end or parsed_extrato.period_end,
        )

    higlobe_pdf_path = None
    if higlobe_bytes is not None and parsed_higlobe is not None:
        higlobe_pdf_path = save_higlobe_pdf(
            higlobe_bytes,
            period_start=parsed_higlobe.period_start or parsed_extrato.period_start,
            period_end=parsed_higlobe.period_end or parsed_extrato.period_end,
        )

    inserted, extrato_id = save_extrato_entry(
        extrato_pdf_path=str(extrato_pdf_path),
        period_start=parsed_extrato.period_start,
        period_end=parsed_extrato.period_end,
        saldo_inicial=parsed_extrato.saldo_inicial,
        rendimento=parsed_extrato.rendimento,
        total_entradas=parsed_extrato.total_entradas,
        total_saidas=parsed_extrato.total_saidas,
        saldo_final=parsed_extrato.saldo_final,
        extrato_entries_json=json.dumps(parsed_extrato.entries),
        caixinha_pdf_path=str(caixinha_pdf_path) if caixinha_pdf_path else None,
        caixinha_saldo_final=parsed_caixinha.saldo_final if parsed_caixinha else None,
        caixinha_entries_json=(
            json.dumps(parsed_caixinha.entries) if parsed_caixinha else None
        ),
        higlobe_pdf_path=str(higlobe_pdf_path) if higlobe_pdf_path else None,
        higlobe_entries_json=(
            json.dumps(parsed_higlobe.entries) if parsed_higlobe else None
        ),
        fiscal_mes=fm,
    )

    if not inserted or not extrato_id:
        ep = resolve_stored_path(str(extrato_pdf_path))
        if ep and ep.exists():
            ep.unlink(missing_ok=True)
        saved_caixinha = resolve_stored_path(str(caixinha_pdf_path)) if caixinha_pdf_path else None
        if saved_caixinha and saved_caixinha.exists():
            saved_caixinha.unlink(missing_ok=True)
        saved_higlobe = resolve_stored_path(str(higlobe_pdf_path)) if higlobe_pdf_path else None
        if saved_higlobe and saved_higlobe.exists():
            saved_higlobe.unlink(missing_ok=True)
        raise conflict(
            "duplicate_extrato",
            "An extrato for this period is already saved.",
        )

    row = get_extrato_by_id(extrato_id)
    assert row
    return dict(row)


@router.get("")
def list_extratos(fiscal_mes: str | None = Query(None)) -> list[dict]:
    rows = get_extratos(fiscal_mes=fiscal_mes.strip() if fiscal_mes else None)
    return [dict(r) for r in rows]


@router.get("/{extrato_id}")
def get_extrato(extrato_id: int) -> dict:
    row = get_extrato_by_id(extrato_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extrato not found")
    return dict(row)


@router.patch("/{extrato_id}")
def patch_extrato(extrato_id: int, body: PatchFiscalMes) -> dict:
    if not get_extrato_by_id(extrato_id):
        raise HTTPException(status_code=404, detail="Extrato not found")
    update_extrato_fiscal_mes(extrato_id, body.fiscal_mes)
    row = get_extrato_by_id(extrato_id)
    assert row
    return dict(row)


@router.put("/{extrato_id}/extrato-pdf")
async def put_extrato_pdf(
    extrato_id: int,
    file: UploadFile = File(..., description="Replacement extrato PDF"),
) -> dict:
    row = get_extrato_by_id(extrato_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extrato not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty PDF")
    try:
        parsed = parse_extrato_pdf(data, filename=file.filename or "extrato.pdf")
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    ok = update_extrato_pdf(
        extrato_id,
        data,
        period_start=parsed.period_start,
        period_end=parsed.period_end,
        saldo_inicial=parsed.saldo_inicial,
        rendimento=parsed.rendimento,
        total_entradas=parsed.total_entradas,
        total_saidas=parsed.total_saidas,
        saldo_final=parsed.saldo_final,
        extrato_entries_json=json.dumps(parsed.entries),
    )
    if not ok:
        raise conflict(
            "duplicate_extrato_period",
            "Updated period conflicts with another extrato row.",
        )
    row2 = get_extrato_by_id(extrato_id)
    assert row2
    return dict(row2)


@router.put("/{extrato_id}/caixinha")
async def put_caixinha(
    extrato_id: int,
    file: UploadFile = File(..., description="Caixinha PDF"),
) -> dict:
    row = get_extrato_by_id(extrato_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extrato not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty PDF")
    try:
        parsed = parse_caixinha_pdf(data, filename=file.filename or "caixinha.pdf")
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    update_caixinha_pdf(
        extrato_id,
        data,
        period_start=parsed.period_start or row.get("period_start"),
        period_end=parsed.period_end or row.get("period_end"),
        caixinha_saldo_final=parsed.saldo_final,
        caixinha_entries_json=json.dumps(parsed.entries),
    )
    row2 = get_extrato_by_id(extrato_id)
    assert row2
    return dict(row2)


@router.delete("/{extrato_id}/caixinha", status_code=204)
def delete_caixinha(extrato_id: int) -> None:
    if not get_extrato_by_id(extrato_id):
        raise HTTPException(status_code=404, detail="Extrato not found")
    if not remove_caixinha_pdf(extrato_id):
        raise HTTPException(status_code=404, detail="Caixinha PDF not present")


@router.put("/{extrato_id}/higlobe")
async def put_higlobe(
    extrato_id: int,
    file: UploadFile = File(..., description="Higlobe PDF"),
) -> dict:
    row = get_extrato_by_id(extrato_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extrato not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty PDF")
    try:
        parsed = parse_higlobe_pdf(data, filename=file.filename or "higlobe.pdf")
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    update_higlobe_pdf(
        extrato_id,
        data,
        period_start=parsed.period_start or row.get("period_start"),
        period_end=parsed.period_end or row.get("period_end"),
        higlobe_entries_json=json.dumps(parsed.entries),
    )
    row2 = get_extrato_by_id(extrato_id)
    assert row2
    return dict(row2)


@router.delete("/{extrato_id}/higlobe", status_code=204)
def delete_higlobe(extrato_id: int) -> None:
    if not get_extrato_by_id(extrato_id):
        raise HTTPException(status_code=404, detail="Extrato not found")
    if not remove_higlobe_pdf(extrato_id):
        raise HTTPException(status_code=404, detail="Higlobe PDF not present")


@router.delete("/{extrato_id}", status_code=204)
def remove_extrato(extrato_id: int) -> None:
    if not delete_extrato(extrato_id):
        raise HTTPException(status_code=404, detail="Extrato not found")


@router.get("/{extrato_id}/extrato-pdf")
def download_extrato_pdf(extrato_id: int) -> FileResponse:
    row = get_extrato_by_id(extrato_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extrato not found")
    path = resolve_stored_path(row.get("extrato_pdf_path"))
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    mt, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mt or "application/pdf", filename=path.name)


@router.get("/{extrato_id}/caixinha-pdf")
def download_caixinha_pdf(extrato_id: int) -> FileResponse:
    row = get_extrato_by_id(extrato_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extrato not found")
    path = resolve_stored_path(row.get("caixinha_pdf_path"))
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Caixinha PDF not found")
    mt, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mt or "application/pdf", filename=path.name)


@router.get("/{extrato_id}/higlobe-pdf")
def download_higlobe_pdf(extrato_id: int) -> FileResponse:
    row = get_extrato_by_id(extrato_id)
    if not row:
        raise HTTPException(status_code=404, detail="Extrato not found")
    path = resolve_stored_path(row.get("higlobe_pdf_path"))
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Higlobe PDF not found")
    mt, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mt or "application/pdf", filename=path.name)
