"""Shared receipt parse preview."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from pjtracker.parsers.boleto_parser import parse_receipt_image

router = APIRouter(tags=["receipts"])


@router.post("/receipts/parse-preview")
async def parse_receipt_preview(
    file: UploadFile = File(..., description="Receipt image"),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")
    mime = file.content_type or "image/png"
    parsed = parse_receipt_image(
        data,
        filename=file.filename or "comprovante.png",
        mime_type=mime,
    )
    return {
        "value": parsed.value,
        "payment_datetime": parsed.payment_datetime,
        "codigo_barras_raw": parsed.codigo_barras_raw,
        "codigo_barras_digits": parsed.codigo_barras_digits,
        "source": parsed.source,
    }
