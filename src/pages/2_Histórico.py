"""Histórico de Notas Fiscais – filter by date, view data, download PDF."""

from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from src.app import DB_PATH, get_nf_entries, get_nf_images, init_db

init_db()

st.title("Histórico de Notas Fiscais")

if "hist_applied_date_from" not in st.session_state:
    st.session_state.hist_applied_date_from = date.today() - timedelta(days=30)
if "hist_applied_date_to" not in st.session_state:
    st.session_state.hist_applied_date_to = date.today()

date_from = st.date_input("De", value=st.session_state.hist_applied_date_from, format="DD/MM/YYYY")
date_to = st.date_input("Até", value=st.session_state.hist_applied_date_to, format="DD/MM/YYYY")

if date_from > date_to:
    st.warning("A data 'De' deve ser anterior ou igual à data 'Até'.")

if st.button("Aplicar filtro"):
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    st.session_state.hist_applied_date_from = date_from
    st.session_state.hist_applied_date_to = date_to
    st.rerun()

date_from = st.session_state.hist_applied_date_from
date_to = st.session_state.hist_applied_date_to
entries = get_nf_entries(date_from=date_from, date_to=date_to)

if not entries:
    st.info("Nenhuma NF encontrada no período.")
    st.stop()


def _label(row: dict) -> str:
    nf_date = row.get("nf_date") or "—"
    company = row.get("company") or "—"
    usd = row.get("usd", 0)
    code = row.get("verification_code") or "—"
    return f"{nf_date} — {company} — $ {usd:,.2f} — {code}"


options = list(range(len(entries)))
selected_idx = st.radio(
    "Selecione uma NF",
    options=options,
    format_func=lambda i: _label(entries[i]),
)

selected = entries[selected_idx]
row = selected

st.divider()
st.markdown(
    '<div style="background: #e8f4f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
    'border-left: 4px solid #1f77b4; margin-bottom: 1rem;">'
    "<strong>Dados da NF</strong></div>",
    unsafe_allow_html=True,
)

date_part = "—"
time_part = "—"
if row.get("nf_date"):
    parts = str(row["nf_date"]).split(" ", 1)
    date_part = parts[0]
    time_part = parts[1] if len(parts) > 1 else "—"

col1, col2 = st.columns(2)
with col1:
    st.metric("Empresa", row.get("company") or "—")
    st.metric("Data", date_part)
    st.metric("Pagamento via", row.get("payment_via") or "—")
    st.metric("Cotação (BRL)", f"{row.get('rate', 0):.4f}")
with col2:
    st.metric("Código de Verificação", row.get("verification_code") or "—")
    st.metric("Hora", time_part)
    st.metric("Valor em USD", f"${row.get('usd', 0):,.2f}")
    st.metric("Spread", f"{row.get('spread', 0)}%")

st.divider()
st.markdown(
    '<div style="background: #e8f8e8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
    'border-left: 4px solid #2ca02c; margin-bottom: 1rem;">'
    "<strong>Valores em BRL</strong></div>",
    unsafe_allow_html=True,
)
brl_ns = row.get("brl_no_spread", 0)
brl_ws = row.get("brl_with_spread", 0)
delta_brl = brl_ns - brl_ws
col1, col2 = st.columns(2)
with col1:
    st.metric("BRL sem spread", f"R$ {brl_ns:,.2f}")
with col2:
    st.metric(
        "BRL com spread",
        f"R$ {brl_ws:,.2f}",
        delta=f"- R$ {delta_brl:,.2f}",
    )

st.divider()
pdf_path_raw = row.get("pdf_path")
if pdf_path_raw:
    p = Path(pdf_path_raw)
    if not p.is_absolute():
        p = Path(DB_PATH).resolve().parent / pdf_path_raw
    if p.exists():
        pdf_bytes = p.read_bytes()
        st.download_button(
            "Baixar PDF",
            data=pdf_bytes,
            file_name=p.name,
            mime="application/pdf",
        )
    else:
        st.info("PDF não disponível para esta NF.")
else:
    st.info("PDF não disponível para esta NF.")

# Imagens anexadas — só mostrar a seção se houver pelo menos uma imagem exibível (evita caixa vermelha de erro)
nf_id = row.get("id")
if nf_id is not None:
    images = get_nf_images(nf_id)
    project_root = Path(DB_PATH).resolve().parent
    displayable = []
    for img in images:
        path_raw = img.get("image_path")
        if not path_raw:
            continue
        p = Path(path_raw)
        if not p.is_absolute():
            p = project_root / path_raw
        if p.exists():
            img_bytes = p.read_bytes()
            if img_bytes:
                displayable.append((img, p, img_bytes))
    if displayable:
        st.divider()
        st.markdown(
            '<div style="background: #f0e8f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
            'border-left: 4px solid #7b2cbf; margin-bottom: 1rem;">'
            "<strong>Imagens anexadas</strong></div>",
            unsafe_allow_html=True,
        )
        for i, (img, p, img_bytes) in enumerate(displayable):
            try:
                st.image(img_bytes, caption=f"Anexo {i + 1}", use_container_width=True)
            except Exception:
                st.caption(f"Anexo {i + 1}: não foi possível exibir a imagem.")
