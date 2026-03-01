"""Home page – upload NF PDF, parse and save."""

import streamlit as st

from src.app import (
    init_db,
    save_nf_entry,
    save_pdf,
)
from src.nf_parser import (
    compute_brl,
    extract_text_from_pdf,
    get_date_from_pdf,
    get_description_block,
    get_payment_via,
    get_verification_code,
    parse_description_block,
)

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
