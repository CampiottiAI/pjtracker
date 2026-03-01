"""Nota Fiscal Tracker – Streamlit app."""

import streamlit as st

from nf_parser import (
    compute_brl,
    extract_text_from_pdf,
    find_valor_liquido,
    get_description_block,
    get_verification_code,
    parse_description_block,
    validate,
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
                        valor_liquido = find_valor_liquido(full_text)
                        validation = validate(brl.brl_with_spread, valor_liquido)

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
                        st.metric("BRL sem spread", f"R$ {brl.brl_no_spread:,.2f}")
                        st.metric("BRL com spread", f"R$ {brl.brl_with_spread:,.2f}")

                        if valor_liquido is not None:
                            st.metric(
                                "Valor Líquido da NFSe Campinas (R$)",
                                f"R$ {valor_liquido:,.2f}",
                            )

                        st.subheader("Conferência")
                        if validation.match:
                            st.success(validation.message)
                        else:
                            st.warning(validation.message)
                            if validation.difference is not None:
                                st.caption(
                                    f"Computed: R$ {validation.computed_brl:,.2f} | "
                                    f"PDF: R$ {validation.valor_liquido:,.2f} | "
                                    f"Diferença: R$ {validation.difference:,.2f}"
                                )
        except Exception as e:
            st.error(f"Erro ao processar o PDF: {e}")
