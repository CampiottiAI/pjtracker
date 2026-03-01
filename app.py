"""Nota Fiscal Tracker – Streamlit app."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from nf_parser import (
    compute_brl,
    extract_text_from_pdf,
    get_date_from_pdf,
    get_description_block,
    get_verification_code,
    parse_description_block,
)

DB_PATH = Path(__file__).resolve().parent / "pjtracker.db"


def init_db() -> None:
    """Create the nf_entries table if it does not exist and ensure unique (nf_date, verification_code, usd)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nf_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                usd REAL NOT NULL,
                rate REAL NOT NULL,
                spread REAL NOT NULL,
                brl_no_spread REAL NOT NULL,
                brl_with_spread REAL NOT NULL,
                nf_date TEXT,
                verification_code TEXT,
                created_at TEXT NOT NULL
            )
        """)
        # Uniqueness: one row per NF (NULLs normalized to '' for index)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_nf_entries_unique
            ON nf_entries (COALESCE(nf_date, ''), COALESCE(verification_code, ''), usd)
        """)


def save_nf_entry(
    company: str | None,
    usd: float,
    rate: float,
    spread: float,
    brl_no_spread: float,
    brl_with_spread: float,
    nf_date: str | None,
    verification_code: str | None,
) -> bool:
    """Insert one NF entry; skip if (nf_date, verification_code, usd) already exists. Returns True if inserted."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO nf_entries (
                company, usd, rate, spread, brl_no_spread, brl_with_spread,
                nf_date, verification_code, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company,
                usd,
                rate,
                spread,
                brl_no_spread,
                brl_with_spread,
                nf_date,
                verification_code,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.rowcount > 0


st.set_page_config(page_title="Nota Fiscal Tracker", layout="centered")
st.title("Nota Fiscal Tracker")

init_db()

uploaded = st.file_uploader("Envie o PDF da Nota Fiscal", type=["pdf"])

if uploaded is not None:
    pdf_bytes = uploaded.read()
    if not pdf_bytes:
        st.error("Arquivo vazio.")
    else:
        try:
            full_text = extract_text_from_pdf(pdf_bytes)
            if not full_text:
                st.error("Não foi possível extrair texto do PDF.")
            else:
                block = get_description_block(full_text)
                if block is None:
                    st.error(
                        "Bloco de descrição do serviço não encontrado. "
                        "Verifique se o PDF contém os marcadores esperados."
                    )
                else:
                    parsed = parse_description_block(block)
                    if parsed.usd is None or parsed.rate is None:
                        st.error(
                            "Não foi possível extrair Valor em Dólar e/ou Cotação do texto. "
                            "Confira o conteúdo da descrição do serviço."
                        )
                    else:
                        brl = compute_brl(parsed.usd, parsed.rate, parsed.spread)

                        st.divider()
                        st.markdown(
                            '<div style="background: #e8f4f8; padding: 0.5rem 1rem; border-radius: 8px; '
                            'border-left: 4px solid #1f77b4; margin-bottom: 1rem;">'
                            "<strong>Dados extraídos</strong></div>",
                            unsafe_allow_html=True,
                        )
                        verification_code = get_verification_code(full_text)
                        nf_date = get_date_from_pdf(full_text)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Empresa", parsed.company or "—")
                            st.metric("Valor em USD", f"${parsed.usd:,.2f}")
                            if nf_date:
                                date_part, time_part = nf_date.split(" ", 1)
                                st.metric("Data", date_part)
                                st.metric("Hora", time_part)
                            if verification_code:
                                st.metric("Código de Verificação", verification_code)
                        with col2:
                            st.metric("Cotação (BRL)", f"{parsed.rate:.4f}")
                            st.metric("Spread", f"{parsed.spread}%")

                        st.divider()
                        st.markdown(
                            '<div style="background: #e8f8e8; padding: 0.5rem 1rem; border-radius: 8px; '
                            'border-left: 4px solid #2ca02c; margin-bottom: 1rem;">'
                            "<strong>Valores em BRL</strong></div>",
                            unsafe_allow_html=True,
                        )
                        delta_brl = brl.brl_no_spread - brl.brl_with_spread
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("BRL sem spread", f"R$ {brl.brl_no_spread:,.2f}")
                        with col2:
                            st.metric(
                                "BRL com spread",
                                f"R$ {brl.brl_with_spread:,.2f}",
                                delta=f"- R$ {delta_brl:,.2f}",
                            )

                        st.divider()
                        if st.button("Aceitar e salvar"):
                            inserted = save_nf_entry(
                                company=parsed.company,
                                usd=parsed.usd,
                                rate=parsed.rate,
                                spread=parsed.spread,
                                brl_no_spread=brl.brl_no_spread,
                                brl_with_spread=brl.brl_with_spread,
                                nf_date=nf_date,
                                verification_code=verification_code,
                            )
                            if inserted:
                                st.success("Dados salvos.")
                            else:
                                st.info("Estes dados já foram salvos anteriormente.")

        except Exception as e:
            st.error(f"Erro ao processar o PDF: {e}")
