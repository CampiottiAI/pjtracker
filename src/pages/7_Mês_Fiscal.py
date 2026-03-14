"""Mês Fiscal – exibe o que há por mês fiscal e alerta o que falta para fechar o mês."""

import streamlit as st

from src.app import (
    format_fiscal_mes,
    get_boletos,
    get_darfs,
    get_extratos,
    get_nf_entries,
    init_db,
)

st.set_page_config(page_title="Mês Fiscal", layout="centered")
st.title("Mês Fiscal")

init_db()

# Descobrir todos os meses fiscais presentes nos dados
def _collect_fiscal_months() -> list[str]:
    months = set()
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
    for row in get_extratos():
        fm = row.get("fiscal_mes")
        if fm and str(fm).strip():
            months.add(str(fm).strip())
    return sorted(months, reverse=True)


fiscal_months = _collect_fiscal_months()

if not fiscal_months:
    st.info("Nenhum mês fiscal encontrado. Cadastre NFs, boletos, DARFs ou extratos com Fiscal Mês definido.")
    st.stop()

# Regras de completude por mês
REQUIRED_NFS = 2
REQUIRED_BOLETO_WITH_RECEIPT = 1
REQUIRED_DARF_WITH_RECEIPT = 1
REQUIRED_EXTRATO_COM_CAIXINHA = 1


def _check_month(fm: str) -> dict:
    nfs = get_nf_entries(fiscal_mes=fm)
    boletos = get_boletos(fiscal_mes=fm)
    boletos_with_receipt = [b for b in boletos if b.get("receipt_path")]
    darfs = get_darfs(fiscal_mes=fm)
    darfs_with_receipt = [d for d in darfs if d.get("receipt_path")]
    extratos = get_extratos(fiscal_mes=fm)
    extratos_com_caixinha = [e for e in extratos if e.get("caixinha_pdf_path")]

    return {
        "nfs_count": len(nfs),
        "nfs_ok": len(nfs) >= REQUIRED_NFS,
        "boletos_with_receipt_count": len(boletos_with_receipt),
        "boletos_ok": len(boletos_with_receipt) >= REQUIRED_BOLETO_WITH_RECEIPT,
        "darfs_with_receipt_count": len(darfs_with_receipt),
        "darfs_ok": len(darfs_with_receipt) >= REQUIRED_DARF_WITH_RECEIPT,
        "extratos_caixinha_count": len(extratos_com_caixinha),
        "extratos_ok": len(extratos_com_caixinha) >= REQUIRED_EXTRATO_COM_CAIXINHA,
    }


st.caption(
    "Para um mês fiscal estar completo são necessários: "
    "2 NFs, 1 Boleto com comprovante, 1 DARF com comprovante, 1 Extrato com caixinha."
)

def _month_incomplete(fm: str) -> bool:
    c = _check_month(fm)
    return not (c["nfs_ok"] and c["boletos_ok"] and c["darfs_ok"] and c["extratos_ok"])

st.write("**Meses a verificar:**")
for fm in fiscal_months:
    label = format_fiscal_mes(fm)
    if _month_incomplete(fm):
        st.write(f"{label} ⚠️")
    else:
        st.write(label)

st.divider()

selected = st.selectbox(
    "Selecione o mês",
    options=fiscal_months,
    format_func=format_fiscal_mes,
    key="fiscal_mes_select",
)

if selected:
    check = _check_month(selected)
    label = format_fiscal_mes(selected)

    st.subheader(label)

    # NFs
    nf_status = "OK" if check["nfs_ok"] else "Faltando"
    st.write(f"**NFs:** {check['nfs_count']} / {REQUIRED_NFS} — {nf_status}")
    if not check["nfs_ok"]:
        falta = REQUIRED_NFS - check["nfs_count"]
        st.warning(f"Faltam {falta} NF(s) para fechar o mês.")

    # Boleto com comprovante
    boleto_status = "OK" if check["boletos_ok"] else "Faltando"
    st.write(f"**Boleto com comprovante:** {check['boletos_with_receipt_count']} / {REQUIRED_BOLETO_WITH_RECEIPT} — {boleto_status}")
    if not check["boletos_ok"]:
        st.warning("Falta 1 Boleto com comprovante para fechar o mês.")

    # DARF com comprovante
    darf_status = "OK" if check["darfs_ok"] else "Faltando"
    st.write(f"**DARF com comprovante:** {check['darfs_with_receipt_count']} / {REQUIRED_DARF_WITH_RECEIPT} — {darf_status}")
    if not check["darfs_ok"]:
        st.warning("Falta 1 DARF com comprovante para fechar o mês.")

    # Extrato com caixinha
    extrato_status = "OK" if check["extratos_ok"] else "Faltando"
    st.write(f"**Extrato com caixinha:** {check['extratos_caixinha_count']} / {REQUIRED_EXTRATO_COM_CAIXINHA} — {extrato_status}")
    if not check["extratos_ok"]:
        st.warning("Falta 1 Extrato com caixinha para fechar o mês.")

    all_ok = (
        check["nfs_ok"]
        and check["boletos_ok"]
        and check["darfs_ok"]
        and check["extratos_ok"]
    )
    if all_ok:
        st.success("Mês fiscal completo.")
