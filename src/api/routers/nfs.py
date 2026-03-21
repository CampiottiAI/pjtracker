"""Notas fiscais."""

from __future__ import annotations

import mimetypes
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from src.api.errors import conflict
from src.api.schemas.common import FISCAL_MES_REGEX, PatchFiscalMes
from src.api.services.paths import project_root, resolve_stored_path
from src.app import (
    delete_nf,
    get_nf_by_id,
    get_nf_entries,
    get_nf_images,
    save_image,
    save_nf_entry,
    save_nf_image,
    save_pdf,
    update_nf_fiscal_mes,
)
from src.nf_parser import compute_brl, parse_nf_pdf

router = APIRouter(prefix="/nfs", tags=["nfs"])


def _nf_to_json(row: dict) -> dict:
    return dict(row)


@router.post("/parse-preview")
async def parse_nf_preview(
    file: UploadFile = File(..., description="NF PDF"),
) -> dict:
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="Empty PDF")
    parsed = parse_nf_pdf(pdf_bytes, filename=file.filename or "nota_fiscal.pdf")
    out: dict = {
        "company": parsed.company,
        "usd": parsed.usd,
        "rate": parsed.rate,
        "spread": parsed.spread,
        "spread_was_default": parsed.spread_was_default,
        "nf_date": parsed.nf_date,
        "verification_code": parsed.verification_code,
        "payment_via": parsed.payment_via,
        "source": parsed.source,
        "brl": None,
    }
    if parsed.usd is not None and parsed.rate is not None:
        brl = compute_brl(parsed.usd, parsed.rate, parsed.spread)
        out["brl"] = {
            "brl_no_spread": brl.brl_no_spread,
            "brl_with_spread": brl.brl_with_spread,
        }
    return out


@router.post("")
async def create_nf(
    file: UploadFile = File(..., description="NF PDF"),
    fiscal_mes: str = Form(..., description="YYYY-MM"),
    images: list[UploadFile] | None = File(None),
) -> dict:
    fm = fiscal_mes.strip()
    if not FISCAL_MES_REGEX.match(fm):
        raise HTTPException(status_code=422, detail="fiscal_mes must be YYYY-MM")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="Empty PDF")

    parsed = parse_nf_pdf(pdf_bytes, filename=file.filename or "nota_fiscal.pdf")
    if parsed.usd is None or parsed.rate is None:
        raise HTTPException(
            status_code=422,
            detail="Could not extract USD and/or rate from PDF",
        )
    brl = compute_brl(parsed.usd, parsed.rate, parsed.spread)
    verification_code = parsed.verification_code or "-"
    nf_date = parsed.nf_date

    pdf_path_obj = save_pdf(pdf_bytes, verification_code, nf_date, parsed.usd)
    pdf_path_str = str(pdf_path_obj)
    inserted, nf_id = save_nf_entry(
        company=parsed.company,
        usd=parsed.usd,
        rate=parsed.rate,
        spread=parsed.spread,
        brl_no_spread=brl.brl_no_spread,
        brl_with_spread=brl.brl_with_spread,
        nf_date=nf_date,
        verification_code=verification_code,
        payment_via=parsed.payment_via,
        pdf_path=pdf_path_str,
        fiscal_mes=fm,
    )
    if not inserted:
        pdf_path_obj.unlink(missing_ok=True)
        raise conflict(
            "duplicate_nf",
            "A nota fiscal with the same date, verification code, and USD already exists.",
            existing_id=nf_id,
        )

    root = project_root()
    upload_list = images if images else []
    for item in upload_list:
        img_bytes = await item.read()
        if not img_bytes:
            continue
        mime = item.content_type or "image/png"
        path_obj = save_image(img_bytes, nf_id, mime)
        try:
            rel_path = path_obj.relative_to(root)
            save_nf_image(nf_id, str(rel_path))
        except ValueError:
            save_nf_image(nf_id, str(path_obj))

    row = get_nf_by_id(nf_id)
    return _nf_to_json(row) if row else {"id": nf_id}


@router.get("")
def list_nfs(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    fiscal_mes: str | None = Query(None),
) -> list[dict]:
    if fiscal_mes is not None:
        rows = get_nf_entries(fiscal_mes=fiscal_mes.strip() or None)
    else:
        rows = get_nf_entries(date_from=date_from, date_to=date_to)
    return [_nf_to_json(r) for r in rows]


@router.get("/{nf_id}")
def get_nf(nf_id: int) -> dict:
    row = get_nf_by_id(nf_id)
    if not row:
        raise HTTPException(status_code=404, detail="NF not found")
    return _nf_to_json(row)


@router.patch("/{nf_id}")
def patch_nf(nf_id: int, body: PatchFiscalMes) -> dict:
    if not get_nf_by_id(nf_id):
        raise HTTPException(status_code=404, detail="NF not found")
    update_nf_fiscal_mes(nf_id, body.fiscal_mes)
    row = get_nf_by_id(nf_id)
    assert row
    return _nf_to_json(row)


@router.delete("/{nf_id}", status_code=204)
def remove_nf(nf_id: int) -> None:
    if not delete_nf(nf_id):
        raise HTTPException(status_code=404, detail="NF not found")


@router.get("/{nf_id}/pdf")
def download_nf_pdf(nf_id: int) -> FileResponse:
    row = get_nf_by_id(nf_id)
    if not row:
        raise HTTPException(status_code=404, detail="NF not found")
    raw = row.get("pdf_path")
    path = resolve_stored_path(raw) if raw else None
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="PDF file not found")
    mt, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mt or "application/pdf", filename=path.name)


@router.get("/{nf_id}/images")
def list_nf_images(nf_id: int) -> list[dict]:
    if not get_nf_by_id(nf_id):
        raise HTTPException(status_code=404, detail="NF not found")
    return get_nf_images(nf_id)


@router.get("/{nf_id}/images/{image_id}")
def download_nf_image(nf_id: int, image_id: int) -> FileResponse:
    if not get_nf_by_id(nf_id):
        raise HTTPException(status_code=404, detail="NF not found")
    for img in get_nf_images(nf_id):
        if img.get("id") == image_id:
            path = resolve_stored_path(img.get("image_path"))
            if not path or not path.is_file():
                raise HTTPException(status_code=404, detail="Image file not found")
            mt, _ = mimetypes.guess_type(str(path))
            return FileResponse(
                path,
                media_type=mt or "application/octet-stream",
                filename=path.name,
            )
    raise HTTPException(status_code=404, detail="Image not found")
