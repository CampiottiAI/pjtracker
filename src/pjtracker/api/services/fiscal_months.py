"""Fiscal month discovery and completeness (from 7_Mês_Fiscal rules)."""

from __future__ import annotations

from pjtracker.app import (
    get_boletos,
    get_darfs,
    get_explicit_fiscal_months,
    get_extratos,
    get_irpj_cslls,
    get_nf_entries,
)

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
