"""Fiscal month discovery and completeness (from 7_Mês_Fiscal rules)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from pjtracker.api.services.paths import resolve_stored_path
from pjtracker.app import (
    get_boletos,
    get_darfs,
    get_explicit_fiscal_months,
    get_extratos,
    get_irpj_cslls,
    get_nf_entries,
    get_nf_images,
    get_withdraw_fiscal_months,
)
from pjtracker.casa.storage import list_saved_fiscal_meses

REQUIRED_NFS = 2
REQUIRED_BOLETO_WITH_RECEIPT = 1
REQUIRED_DARF_WITH_RECEIPT = 1
REQUIRED_IRPJ_CSLL_WITH_RECEIPT = 1
REQUIRED_EXTRATO_COM_CAIXINHA = 1
QUARTER_ENDING_MONTHS = {"03", "06", "09", "12"}


def is_irpj_csll_required(fiscal_mes: str) -> bool:
    parts = fiscal_mes.split("-")
    if len(parts) != 2:
        return False
    return parts[1] in QUARTER_ENDING_MONTHS


def collect_fiscal_months() -> list[str]:
    months: set[str] = set(get_explicit_fiscal_months())
    for row in get_nf_entries():
        fm = row.get("fiscal_mes")
        if fm and str(fm).strip():
            months.add(str(fm).strip())
    for row in get_boletos():
        fm = row.get("fiscal_mes")
        if fm and str(fm).strip():
            months.add(str(fm).strip())
    for row in get_darfs():
        fm = row.get("fiscal_mes")
        if fm and str(fm).strip():
            months.add(str(fm).strip())
    for row in get_irpj_cslls():
        fm = row.get("fiscal_mes")
        if fm and str(fm).strip():
            months.add(str(fm).strip())
    for row in get_extratos():
        fm = row.get("fiscal_mes")
        if fm and str(fm).strip():
            months.add(str(fm).strip())
    for fm in get_withdraw_fiscal_months():
        if fm:
            months.add(fm)
    for fm in list_saved_fiscal_meses():
        months.add(fm)
    return sorted(months, reverse=True)


def month_completeness(fm: str) -> dict:
    nfs = get_nf_entries(fiscal_mes=fm)
    boletos = get_boletos(fiscal_mes=fm)
    boletos_with_receipt = [b for b in boletos if b.get("receipt_path")]
    darfs = get_darfs(fiscal_mes=fm)
    darfs_with_receipt = [d for d in darfs if d.get("receipt_path")]
    irpj_cslls = get_irpj_cslls(fiscal_mes=fm)
    irpj_cslls_with_receipt = [d for d in irpj_cslls if d.get("receipt_path")]
    irpj_csll_required = is_irpj_csll_required(fm)
    extratos = get_extratos(fiscal_mes=fm)
    extratos_com_caixinha = [e for e in extratos if e.get("caixinha_pdf_path")]
    extratos_com_higlobe = [e for e in extratos if e.get("higlobe_pdf_path")]

    return {
        "fiscal_mes": fm,
        "nfs_count": len(nfs),
        "nfs_ok": len(nfs) >= REQUIRED_NFS,
        "boletos_with_receipt_count": len(boletos_with_receipt),
        "boletos_ok": len(boletos_with_receipt) >= REQUIRED_BOLETO_WITH_RECEIPT,
        "darfs_with_receipt_count": len(darfs_with_receipt),
        "darfs_ok": len(darfs_with_receipt) >= REQUIRED_DARF_WITH_RECEIPT,
        "irpj_csll_with_receipt_count": len(irpj_cslls_with_receipt),
        "irpj_csll_required": irpj_csll_required,
        "irpj_csll_ok": (
            len(irpj_cslls_with_receipt) >= REQUIRED_IRPJ_CSLL_WITH_RECEIPT
            if irpj_csll_required
            else True
        ),
        "extratos_caixinha_count": len(extratos_com_caixinha),
        "extratos_ok": len(extratos_com_caixinha) >= REQUIRED_EXTRATO_COM_CAIXINHA,
        "extratos_higlobe_count": len(extratos_com_higlobe),
        "higlobe_ok": len(extratos_com_higlobe) >= 1,
        "month_complete": (
            len(nfs) >= REQUIRED_NFS
            and len(boletos_with_receipt) >= REQUIRED_BOLETO_WITH_RECEIPT
            and len(darfs_with_receipt) >= REQUIRED_DARF_WITH_RECEIPT
            and (
                not irpj_csll_required
                or len(irpj_cslls_with_receipt) >= REQUIRED_IRPJ_CSLL_WITH_RECEIPT
            )
            and len(extratos_com_caixinha) >= REQUIRED_EXTRATO_COM_CAIXINHA
        ),
    }


def _safe_verification_code(code: str | None) -> str:
    if not code or not str(code).strip():
        return "nofc"
    safe = "".join(c if c.isalnum() else "_" for c in str(code).strip())
    return safe[:40] or "nofc"


def _add_file_to_zip(zf: zipfile.ZipFile, arcname: str, path: Path) -> bool:
    if not path.is_file():
        return False
    zf.write(path, arcname)
    return True


def build_fiscal_month_pack(fiscal_mes: str) -> bytes | None:
    """Build zip bytes for NF/extrato documents in a fiscal month. Returns None if empty."""
    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nf in get_nf_entries(fiscal_mes=fiscal_mes):
            nf_id = nf["id"]
            code = _safe_verification_code(nf.get("verification_code"))
            raw_pdf = nf.get("pdf_path")
            if raw_pdf:
                path = resolve_stored_path(raw_pdf)
                if path and _add_file_to_zip(zf, f"nfs/nf_{nf_id}_{code}.pdf", path):
                    added += 1
            for img in get_nf_images(nf_id):
                image_id = img["id"]
                raw_img = img.get("image_path")
                if not raw_img:
                    continue
                path = resolve_stored_path(raw_img)
                if path:
                    ext = path.suffix or ".png"
                    arcname = f"nfs/nf_{nf_id}_{code}_img_{image_id}{ext}"
                    if _add_file_to_zip(zf, arcname, path):
                        added += 1

        for extrato in get_extratos(fiscal_mes=fiscal_mes):
            extrato_id = extrato["id"]
            for field, arc_suffix in (
                ("extrato_pdf_path", "extrato"),
                ("caixinha_pdf_path", "caixinha"),
                ("higlobe_pdf_path", "higlobe"),
            ):
                raw = extrato.get(field)
                if not raw:
                    continue
                path = resolve_stored_path(raw)
                if path and _add_file_to_zip(
                    zf, f"extratos/{arc_suffix}_{extrato_id}.pdf", path
                ):
                    added += 1

    if added == 0:
        return None
    return buffer.getvalue()
