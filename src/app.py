"""Nota Fiscal Tracker – Streamlit app."""

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st

from src.nf_parser import (
    compute_brl,
    extract_text_from_pdf,
    get_date_from_pdf,
    get_description_block,
    get_payment_via,
    get_verification_code,
    parse_description_block,
)

DB_PATH = Path(__file__).resolve().parent / "pjtracker.db"
PDF_DIR = Path(__file__).resolve().parent / "pdfs"


def init_db() -> None:
    """Create the nf_entries table if it does not exist and ensure unique (nf_date, verification_code, usd)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
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
                payment_via TEXT,
                pdf_path TEXT,
                created_at TEXT NOT NULL
            )
        """)
        # Migration: add payment_via if table existed without it
        try:
            conn.execute("ALTER TABLE nf_entries ADD COLUMN payment_via TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migration: add pdf_path if table existed without it
        try:
            conn.execute("ALTER TABLE nf_entries ADD COLUMN pdf_path TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Uniqueness: one row per NF (NULLs normalized to '' for index)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_nf_entries_unique
            ON nf_entries (COALESCE(nf_date, ''), COALESCE(verification_code, ''), usd)
        """)


def _sanitize_filename(s: str) -> str:
    """Replace characters that are unsafe in filenames."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


def save_pdf(pdf_bytes: bytes, verification_code: str, nf_date: str | None, usd: float) -> Path:
    """Save PDF to pdfs/ and return the path. Filename is unique per (date, code, usd)."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    safe_code = _sanitize_filename(verification_code or "unknown")[:50]
    safe_date = _sanitize_filename((nf_date or "").replace(" ", "_"))[:30] or "nodate"
    base = f"nf_{safe_date}_{safe_code}_{usd:.2f}"
    path = PDF_DIR / f"{base}.pdf"
    counter = 0
    while path.exists():
        counter += 1
        path = PDF_DIR / f"{base}_{counter}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_nf_entry(
    company: str | None,
    usd: float,
    rate: float,
    spread: float,
    brl_no_spread: float,
    brl_with_spread: float,
    nf_date: str | None,
    verification_code: str | None,
    payment_via: str | None,
    pdf_path: str | None = None,
) -> bool:
    """Insert one NF entry; skip if (nf_date, verification_code, usd) already exists. Returns True if inserted."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO nf_entries (
                company, usd, rate, spread, brl_no_spread, brl_with_spread,
                nf_date, verification_code, payment_via, pdf_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payment_via,
                pdf_path,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.rowcount > 0


def _parse_nf_date_to_date(nf_date: str | None) -> date | None:
    """Parse nf_date 'DD/MM/YYYY HH:MM:SS' to a date for filtering. Returns None if invalid or empty."""
    if not nf_date or not nf_date.strip():
        return None
    try:
        dt = datetime.strptime(nf_date.strip().split()[0], "%d/%m/%Y")
        return dt.date()
    except (ValueError, IndexError):
        return None


def get_nf_entries(
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Return NF entries, optionally filtered by nf_date range. Newest first. Each row is a dict."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM nf_entries ORDER BY created_at DESC",
        )
        rows = [dict(r) for r in cur.fetchall()]

    if date_from is None and date_to is None:
        return rows

    filtered = []
    for row in rows:
        d = _parse_nf_date_to_date(row.get("nf_date"))
        if d is None:
            continue
        if date_from is not None and d < date_from:
            continue
        if date_to is not None and d > date_to:
            continue
        filtered.append(row)
    return filtered


if __name__ == "__main__":
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
                                '<div style="background: #e8f4f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
                                'border-left: 4px solid #1f77b4; margin-bottom: 1rem;">'
                                "<strong>Dados extraídos</strong></div>",
                                unsafe_allow_html=True,
                            )
                            verification_code = get_verification_code(full_text) or "-"
                            nf_date = get_date_from_pdf(full_text)
                            payment_via = get_payment_via(full_text)
                            date_part, time_part = "-", "-"
                            if nf_date:
                                date_part, time_part = nf_date.split(" ", 1)

                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Empresa", parsed.company or "—")
                                st.metric("Data", date_part)
                                st.metric("Pagamento via", f"{payment_via}")
                                st.metric("Cotação (BRL)", f"{parsed.rate:.4f}")
                            with col2:
                                st.metric("Código de Verificação", verification_code)
                                st.metric("Hora", time_part)
                                st.metric("Valor em USD", f"${parsed.usd:,.2f}")
                                st.metric("Spread", f"{parsed.spread}%")

                            st.divider()
                            st.markdown(
                                '<div style="background: #e8f8e8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
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
                                pdf_path_obj = save_pdf(
                                    pdf_bytes, verification_code, nf_date, parsed.usd
                                )
                                pdf_path_str = str(pdf_path_obj)
                                inserted = save_nf_entry(
                                    company=parsed.company,
                                    usd=parsed.usd,
                                    rate=parsed.rate,
                                    spread=parsed.spread,
                                    brl_no_spread=brl.brl_no_spread,
                                    brl_with_spread=brl.brl_with_spread,
                                    nf_date=nf_date,
                                    verification_code=verification_code,
                                    payment_via=payment_via,
                                    pdf_path=pdf_path_str,
                                )
                                if inserted:
                                    st.success("Dados e PDF salvos.")
                                else:
                                    pdf_path_obj.unlink(missing_ok=True)  # remove orphan PDF
                                    st.info("Estes dados já foram salvos anteriormente.")

            except Exception as e:
                st.error(f"Erro ao processar o PDF: {e}")
