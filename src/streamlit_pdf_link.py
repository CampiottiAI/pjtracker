"""Streamlit-only helper: temp PDF link for in-browser viewing."""

import re
from pathlib import Path

import streamlit as st

# Static temp dir for PDFs opened in new tab (relative to this package = src/)
STATIC_TEMP_DIR = Path(__file__).resolve().parent / "static" / "temp"


def open_pdf_link(
    pdf_bytes: bytes, label: str = "Abrir PDF", unique_key: str = "view"
) -> None:
    """Write PDF to static temp dir and render a link that opens it in a new tab."""
    safe_key = re.sub(r"[^\w\-]", "_", unique_key).strip("_") or "view"
    STATIC_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    path = STATIC_TEMP_DIR / f"{safe_key}.pdf"
    path.write_bytes(pdf_bytes)
    href = f"/app/static/temp/{safe_key}.pdf"
    style = (
        "display:inline-block;padding:0.5rem 1rem;background:#f63366;color:white;"
        "border-radius:0.5rem;text-decoration:none;font-weight:500;"
    )
    html = f'<a href="{href}" target="_blank" rel="noopener noreferrer" style="{style}">{label}</a>'
    st.markdown(html, unsafe_allow_html=True)
