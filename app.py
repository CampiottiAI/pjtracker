"""Nota Fiscal Tracker – Streamlit app."""

import streamlit as st

from nf_parser import (
    compute_brl,
    extract_text_from_pdf,
    get_description_block,
    get_verification_code,
    parse_description_block,
)

st.set_page_config(page_title="Nota Fiscal Tracker", layout="centered")
st.title("Nota Fiscal Tracker")

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

                        st.subheader("Dados extraídos")
                        verification_code = get_verification_code(full_text)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Empresa", parsed.company or "—")
                            st.metric("Valor em USD", f"${parsed.usd:,.2f}")
                            if verification_code:
                                st.metric("Código de Verificação", verification_code)
                        with col2:
                            st.metric("Cotação (BRL)", f"{parsed.rate:.4f}")
                            spread_label = f"{parsed.spread}%"
                            if parsed.spread_was_default:
                                spread_label += " (padrão)"
                            st.metric("Spread", spread_label)

                        st.subheader("Valores em BRL")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("BRL sem spread", f"R$ {brl.brl_no_spread:,.2f}")
                        with col2:
                            st.metric("BRL com spread", f"R$ {brl.brl_with_spread:,.2f}")

        except Exception as e:
            st.error(f"Erro ao processar o PDF: {e}")
