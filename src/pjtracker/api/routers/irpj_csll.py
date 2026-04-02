"""IRPJ/CSLL documents — same shapes as DARFs."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from pjtracker.api.errors import conflict
from pjtracker.api.schemas.common import (
    FISCAL_MES_REGEX,
    PatchBoletoLikeFields,
    PatchFiscalMes,
)
from pjtracker.api.services.paths import project_root, resolve_stored_path
from pjtracker.app import (
    delete_irpj_csll,
    get_irpj_csll_by_id,
    get_irpj_cslls,
    save_irpj_csll_entry,
    save_irpj_csll_pdf,
    save_irpj_csll_receipt,
    update_irpj_csll_fields,
    update_irpj_csll_fiscal_mes,
    update_irpj_csll_pdf,
    update_irpj_csll_receipt,
)
from pjtracker.parsers.barcode_diff import format_barcode_diff
from pjtracker.parsers.boleto_parser import parse_receipt_image
from pjtracker.parsers.irpj_csll_parser import parse_irpj_csll_pdf

router = APIRouter(prefix="/irpj-csll", tags=["irpj-csll"])


def _match_status(document_digits: str | None, receipt_digits: str | None) -> str | None:
    if not document_digits or not receipt_digits:
        return None
    return "match" if document_digits == receipt_digits else "mismatch"


def _receipt_payload_from_parsed(parsed) -> dict:
    return {
        "value": parsed.value,
        "codigo_barras": parsed.codigo_barras_raw,
        "codigo_barras_digits": parsed.codigo_barras_digits,
    }


@router.post("/parse-preview")
async def parse_irpj_csll_preview(
    file: UploadFile = File(..., description="IRPJ/CSLL PDF"),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty PDF")
    parsed = parse_irpj_csll_pdf(data, filename=file.filename or "irpj_csll.pdf")
    return {
        "value": parsed.value,
        "emission_date": parsed.emission_date,
        "deadline_date": parsed.deadline_date,
        "codigo_barras_raw": parsed.codigo_barras_raw,
        "codigo_barras_digits": parsed.codigo_barras_digits,
        "source": parsed.source,
    }


@router.post("")
async def create_irpj_csll(
    file: UploadFile = File(..., description="IRPJ/CSLL PDF"),
    fiscal_mes: str = Form(..., description="YYYY-MM"),
    receipt: UploadFile | None = File(None),
    receipt_date: str | None = Form(None),
    receipt_time: str | None = Form(None),
) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="Empty PDF")

    parsed = parse_irpj_csll_pdf(pdf_bytes, filename=file.filename or "irpj_csll.pdf")
    receipt_bytes = await receipt.read() if receipt else None
    receipt_payload: dict | None = None
    receipt_date_str: str | None = None

    if receipt_bytes:
        rec_name = (receipt.filename if receipt else None) or "comprovante.png"
        mime_header = (receipt.content_type if receipt else None) or "image/png"
        rec_parsed = parse_receipt_image(
            receipt_bytes,
            filename=rec_name,
            mime_type=mime_header,
        )
        receipt_payload = _receipt_payload_from_parsed(rec_parsed)
        if receipt_date and receipt_date.strip():
            time_part = (receipt_time or "").strip() or "00:00:00"
            receipt_date_str = f"{receipt_date.strip()} {time_part}"
        elif rec_parsed.payment_datetime:
            receipt_date_str = rec_parsed.payment_datetime
        else:
            raise HTTPException(
                status_code=422,
                detail="Receipt image requires receipt_date or extractable payment datetime",
            )

    pdf_path = save_irpj_csll_pdf(
        pdf_bytes,
        emission_date=parsed.emission_date,
        value=parsed.value,
    )
    inserted, irpj_csll_id = save_irpj_csll_entry(
        pdf_path=str(pdf_path),
        value=parsed.value,
        emission_date=parsed.emission_date,
        deadline_date=parsed.deadline_date,
        codigo_barras=parsed.codigo_barras_raw,
        codigo_barras_digits=parsed.codigo_barras_digits,
        receipt_path=None,
        receipt_date=None,
        fiscal_mes=fm,
    )
    if not inserted or not irpj_csll_id:
        p = Path(str(pdf_path))
        if not p.is_absolute():
            p = project_root() / str(pdf_path)
        if p.exists():
            p.unlink(missing_ok=True)
        raise conflict(
            "duplicate_irpj_csll",
            "An IRPJ/CSLL document with the same value and dates already exists.",
        )

    if receipt_bytes and receipt_payload is not None and receipt_date_str is not None:
        ext = rec_name.rsplit(".", 1)[-1].lower() if "." in rec_name else "png"
        if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
            ext = "png"
        if ext == "jpg":
            ext = "jpeg"
        rpath = save_irpj_csll_receipt(irpj_csll_id, receipt_bytes, ext)
        update_irpj_csll_receipt(
            irpj_csll_id,
            str(rpath),
            receipt_date_str,
            receipt_value=receipt_payload["value"],
            receipt_codigo_barras=receipt_payload["codigo_barras"],
            receipt_codigo_barras_digits=receipt_payload["codigo_barras_digits"],
            receipt_match_status=_match_status(
                parsed.codigo_barras_digits,
                receipt_payload["codigo_barras_digits"],
            ),
        )

    row = get_irpj_csll_by_id(irpj_csll_id)
    assert row
    return dict(row)


@router.get("")
def list_irpj_csll(fiscal_mes: str | None = Query(None)) -> list[dict]:
    rows = get_irpj_cslls(fiscal_mes=fiscal_mes.strip() if fiscal_mes else None)
    return [dict(r) for r in rows]


@router.get("/{irpj_csll_id}")
def get_irpj_csll(irpj_csll_id: int) -> dict:
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")
    return dict(row)


@router.patch("/{irpj_csll_id}")
def patch_irpj_csll(irpj_csll_id: int, body: PatchFiscalMes) -> dict:
    if not get_irpj_csll_by_id(irpj_csll_id):
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")
    update_irpj_csll_fiscal_mes(irpj_csll_id, body.fiscal_mes)
    row = get_irpj_csll_by_id(irpj_csll_id)
    assert row
    return dict(row)


@router.patch("/{irpj_csll_id}/fields")
def patch_irpj_csll_fields(irpj_csll_id: int, body: PatchBoletoLikeFields) -> dict:
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")
    ok = update_irpj_csll_fields(
        irpj_csll_id,
        value=body.value,
        emission_date=body.emission_date,
        deadline_date=body.deadline_date,
        codigo_barras=body.codigo_barras,
        codigo_barras_digits=body.codigo_barras_digits,
        receipt_date=body.receipt_date,
        receipt_value=body.receipt_value,
        receipt_codigo_barras=body.receipt_codigo_barras,
        receipt_codigo_barras_digits=body.receipt_codigo_barras_digits,
        fiscal_mes=body.fiscal_mes,
    )
    if not ok:
        raise conflict(
            "duplicate_irpj_csll_hash",
            "Another IRPJ/CSLL document already has the same content hash.",
        )
    row2 = get_irpj_csll_by_id(irpj_csll_id)
    assert row2
    return dict(row2)


@router.put("/{irpj_csll_id}/pdf")
async def put_irpj_csll_pdf(
    irpj_csll_id: int,
    file: UploadFile = File(..., description="Replacement IRPJ/CSLL PDF"),
) -> dict:
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty PDF")
    parsed = parse_irpj_csll_pdf(data, filename=file.filename or "irpj_csll.pdf")
    ok = update_irpj_csll_pdf(
        irpj_csll_id,
        data,
        value=parsed.value,
        emission_date=parsed.emission_date,
        deadline_date=parsed.deadline_date,
        codigo_barras=parsed.codigo_barras_raw,
        codigo_barras_digits=parsed.codigo_barras_digits,
        receipt_match_status=_match_status(
            parsed.codigo_barras_digits,
            row.get("receipt_codigo_barras_digits"),
        ),
    )
    if not ok:
        raise conflict(
            "duplicate_irpj_csll_hash",
            "Another IRPJ/CSLL document already has the same content hash.",
        )
    row2 = get_irpj_csll_by_id(irpj_csll_id)
    assert row2
    return dict(row2)


@router.put("/{irpj_csll_id}/receipt")
async def put_irpj_csll_receipt(
    irpj_csll_id: int,
    file: UploadFile = File(..., description="Receipt image"),
    receipt_date: str | None = Form(None),
    receipt_time: str | None = Form(None),
) -> dict:
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty image")

    rec_name = file.filename or "comprovante.png"
    mime_header = file.content_type or "image/png"
    rec_parsed = parse_receipt_image(
        data,
        filename=rec_name,
        mime_type=mime_header,
    )
    receipt_payload = _receipt_payload_from_parsed(rec_parsed)
    if receipt_date and receipt_date.strip():
        time_part = (receipt_time or "").strip() or "00:00:00"
        receipt_date_str = f"{receipt_date.strip()} {time_part}"
    elif rec_parsed.payment_datetime:
        receipt_date_str = rec_parsed.payment_datetime
    else:
        raise HTTPException(
            status_code=422,
            detail="receipt_date or extractable payment datetime required",
        )

    old_raw = row.get("receipt_path")
    if old_raw:
        old_p = Path(old_raw) if Path(old_raw).is_absolute() else project_root() / old_raw
        if old_p.exists():
            old_p.unlink(missing_ok=True)

    ext = rec_name.rsplit(".", 1)[-1].lower() if "." in rec_name else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        ext = "png"
    if ext == "jpg":
        ext = "jpeg"
    rpath = save_irpj_csll_receipt(irpj_csll_id, data, ext)
    update_irpj_csll_receipt(
        irpj_csll_id,
        str(rpath),
        receipt_date_str,
        receipt_value=receipt_payload["value"],
        receipt_codigo_barras=receipt_payload["codigo_barras"],
        receipt_codigo_barras_digits=receipt_payload["codigo_barras_digits"],
        receipt_match_status=_match_status(
            row.get("codigo_barras_digits"),
            receipt_payload["codigo_barras_digits"],
        ),
    )
    row2 = get_irpj_csll_by_id(irpj_csll_id)
    assert row2
    return dict(row2)


@router.delete("/{irpj_csll_id}", status_code=204)
def remove_irpj_csll(irpj_csll_id: int) -> None:
    if not delete_irpj_csll(irpj_csll_id):
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")


@router.get("/{irpj_csll_id}/pdf")
def download_irpj_csll_pdf(irpj_csll_id: int) -> FileResponse:
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")
    path = resolve_stored_path(row.get("pdf_path"))
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    mt, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mt or "application/pdf", filename=path.name)


@router.get("/{irpj_csll_id}/receipt")
def download_irpj_csll_receipt(irpj_csll_id: int) -> FileResponse:
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")
    path = resolve_stored_path(row.get("receipt_path"))
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Receipt not found")
    mt, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mt or "image/png", filename=path.name)


@router.get("/{irpj_csll_id}/barcode-diff", response_class=PlainTextResponse)
def irpj_csll_barcode_diff(irpj_csll_id: int) -> str:
    row = get_irpj_csll_by_id(irpj_csll_id)
    if not row:
        raise HTTPException(status_code=404, detail="IRPJ/CSLL not found")
    if row.get("receipt_match_status") != "mismatch":
        raise HTTPException(
            status_code=404,
            detail="Barcode diff only available when receipt_match_status is mismatch",
        )
    doc_d = row.get("codigo_barras_digits")
    rec_d = row.get("receipt_codigo_barras_digits")
    if not doc_d or not rec_d:
        raise HTTPException(status_code=404, detail="Missing digit strings for diff")
    return format_barcode_diff(
        doc_d,
        rec_d,
        "IRPJ/CSLL (documento)",
        "Comprovante",
    )
