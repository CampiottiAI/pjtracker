"""Boletos – upload boleto PDF and optional receipt image; auto-extract value and dates from PDF."""

import base64
from pathlib import Path

import streamlit as st
from st_img_pastebutton import paste

from src.app import (
    DB_PATH,
    get_boletos,
    init_db,
    save_boleto_entry,
    save_boleto_pdf,
    save_boleto_receipt,
    update_boleto_pdf,
    update_boleto_receipt,
)
from src.boleto_parser import parse_boleto_pdf

st.set_page_config(page_title="Boletos", layout="centered")
st.title("Boletos")

init_db()

project_root = Path(DB_PATH).resolve().parent

mode = st.radio(
    "Modo",
    ["Adicionar boleto", "Listar boletos"],
    horizontal=True,
)

if mode == "Adicionar boleto":
    st.subheader("Novo boleto")
    uploaded_pdf = st.file_uploader(
        "Envie o PDF do boleto", type=["pdf"], key="boleto_pdf_upload"
    )

    if uploaded_pdf is not None:
        pdf_bytes = uploaded_pdf.read()
        uploaded_pdf.seek(0)
        if not pdf_bytes:
            st.error("Arquivo vazio.")
        else:
            try:
                parsed = parse_boleto_pdf(pdf_bytes)
                st.markdown(
                    '<div style="background: #e8f4f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
                    'border-left: 4px solid #1f77b4; margin-bottom: 1rem;">'
                    "<strong>Dados extraídos do boleto</strong></div>",
                    unsafe_allow_html=True,
                )
                col1, col2 = st.columns(2)
                with col1:
                    val_display = (
                        f"R$ {parsed.value:,.2f}" if parsed.value is not None else "—"
                    )
                    st.metric("Valor (R$)", val_display)
                    st.metric("Data de emissão", parsed.emission_date or "—")
                with col2:
                    st.metric("Data de vencimento", parsed.deadline_date or "—")

                # Receipt (optional): upload or paste + manual date
                st.divider()
                st.markdown(
                    '<div style="background: #f0e8f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
                    'border-left: 4px solid #7b2cbf; margin-bottom: 1rem;">'
                    "<strong>Comprovante de pagamento (opcional)</strong> — envie ou cole a imagem e informe a data.</div>",
                    unsafe_allow_html=True,
                )
                pdf_key = uploaded_pdf.name or str(id(uploaded_pdf))
                if st.session_state.get("pending_boleto_receipt_pdf_key") != pdf_key:
                    st.session_state["pending_boleto_receipt"] = None
                    st.session_state["pending_boleto_receipt_date"] = None
                    st.session_state["pending_boleto_receipt_pdf_key"] = pdf_key
                pending_receipt = st.session_state.get("pending_boleto_receipt")
                receipt_col1, receipt_col2 = st.columns(2)
                with receipt_col1:
                    receipt_upload = st.file_uploader(
                        "Enviar imagem do comprovante",
                        type=["png", "jpg", "jpeg", "gif", "webp"],
                        key="boleto_receipt_upload",
                    )
                    if receipt_upload:
                        data = receipt_upload.read()
                        ext = (
                            (Path(receipt_upload.name).suffix or ".png")
                            .lstrip(".")
                            .lower()
                        )
                        mime = (
                            ext
                            if ext in ("png", "jpg", "jpeg", "gif", "webp")
                            else "png"
                        )
                        if mime == "jpg":
                            mime = "jpeg"
                        st.session_state["pending_boleto_receipt"] = {
                            "bytes": data,
                            "mime": mime,
                        }
                    image_data = paste(
                        label="Colar imagem do comprovante",
                        key="boleto_receipt_paste",
                    )
                    if image_data is not None:
                        try:
                            if "," in image_data:
                                header, encoded = image_data.split(",", 1)
                                mime = "png"
                                if "image/" in header:
                                    mime = (
                                        header.split("image/", 1)[-1]
                                        .split(";")[0]
                                        .strip()
                                    )
                            else:
                                encoded = image_data
                                mime = "png"
                            binary_data = base64.b64decode(encoded)
                            st.session_state["pending_boleto_receipt"] = {
                                "bytes": binary_data,
                                "mime": mime,
                            }
                        except Exception:
                            pass
                with receipt_col2:
                    receipt_date = st.date_input(
                        "Data do comprovante",
                        format="DD/MM/YYYY",
                        key="boleto_receipt_date",
                    )
                    receipt_time = st.text_input(
                        "Hora (opcional, ex: 18:40:12)",
                        value="",
                        key="boleto_receipt_time",
                        placeholder="18:40:12",
                    )
                    if pending_receipt:
                        st.caption("Comprovante anexado.")
                        time_part = receipt_time.strip() if receipt_time else "00:00:00"
                        receipt_date_str = (
                            f"{receipt_date.strftime('%d/%m/%Y')} {time_part}"
                        )
                    else:
                        receipt_date_str = None

                st.divider()
                if st.button("Salvar boleto"):
                    pdf_path = save_boleto_pdf(
                        pdf_bytes,
                        emission_date=parsed.emission_date,
                        value=parsed.value,
                    )
                    boleto_id = save_boleto_entry(
                        pdf_path=str(pdf_path),
                        value=parsed.value,
                        emission_date=parsed.emission_date,
                        deadline_date=parsed.deadline_date,
                        receipt_path=None,
                        receipt_date=None,
                    )
                    if pending_receipt:
                        receipt_path = save_boleto_receipt(
                            boleto_id,
                            pending_receipt["bytes"],
                            pending_receipt["mime"],
                        )
                        update_boleto_receipt(
                            boleto_id, str(receipt_path), receipt_date_str
                        )
                    st.session_state["pending_boleto_receipt"] = None
                    st.session_state["pending_boleto_receipt_date"] = None
                    st.success("Boleto salvo.")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar o PDF: {e}")

else:
    # Listar boletos
    boletos = get_boletos()
    if not boletos:
        st.info("Nenhum boleto cadastrado.")
        st.stop()

    def _label(b: dict) -> str:
        val = b.get("value")
        val_str = f"R$ {val:,.2f}" if val is not None else "—"
        em = b.get("emission_date") or "—"
        return f"{em} — {val_str} — ID {b.get('id')}"

    options = list(range(len(boletos)))
    selected_idx = st.radio(
        "Selecione um boleto",
        options=options,
        format_func=lambda i: _label(boletos[i]),
    )
    row = boletos[selected_idx]
    boleto_id = row["id"]

    st.divider()
    if row.get("receipt_path") is None or (
        isinstance(row.get("receipt_path"), str)
        and row.get("receipt_path").strip() == ""
    ):
        st.warning("Comprovante de pagamento ausente.")
    st.markdown(
        '<div style="background: #e8f4f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
        'border-left: 4px solid #1f77b4; margin-bottom: 1rem;">'
        "<strong>Dados do boleto</strong></div>",
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Valor (R$)",
            f"R$ {row['value']:,.2f}" if row.get("value") is not None else "—",
        )
        st.metric("Data de emissão", row.get("emission_date") or "—")
    with col2:
        st.metric("Data de vencimento", row.get("deadline_date") or "—")
        st.metric("Data do comprovante", row.get("receipt_date") or "—")

    # Download PDF
    pdf_path_raw = row.get("pdf_path")
    if pdf_path_raw:
        p = Path(pdf_path_raw)
        if not p.is_absolute():
            p = project_root / pdf_path_raw
        if p.exists():
            pdf_bytes = p.read_bytes()
            st.download_button(
                "Baixar PDF do boleto",
                data=pdf_bytes,
                file_name=p.name,
                mime="application/pdf",
                key="dl_boleto_pdf",
            )
        else:
            st.caption("PDF não encontrado.")

    # Receipt image
    receipt_path_raw = row.get("receipt_path")
    if receipt_path_raw:
        rp = Path(receipt_path_raw)
        if not rp.is_absolute():
            rp = project_root / receipt_path_raw
        if rp.exists():
            st.divider()
            st.markdown("**Comprovante anexado**")
            st.image(str(rp), use_container_width=True)

    # Update PDF
    st.divider()
    st.subheader("Atualizar boleto")
    new_pdf = st.file_uploader(
        "Substituir PDF do boleto (opcional)",
        type=["pdf"],
        key="update_boleto_pdf",
    )
    if new_pdf is not None:
        new_bytes = new_pdf.read()
        if new_bytes:
            try:
                parsed = parse_boleto_pdf(new_bytes)
                val_txt = f"R$ {parsed.value:,.2f}" if parsed.value is not None else "—"
                st.caption(
                    f"Novos dados: Valor {val_txt}; "
                    f"Emissão {parsed.emission_date or '—'}; Vencimento {parsed.deadline_date or '—'}"
                )
                if st.button("Aplicar e salvar novo PDF", key="apply_update_pdf"):
                    update_boleto_pdf(
                        boleto_id,
                        new_bytes,
                        value=parsed.value,
                        emission_date=parsed.emission_date,
                        deadline_date=parsed.deadline_date,
                    )
                    st.success("PDF atualizado.")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

    # Update receipt
    st.markdown("**Atualizar comprovante** (opcional)")
    new_receipt_upload = st.file_uploader(
        "Nova imagem do comprovante",
        type=["png", "jpg", "jpeg", "gif", "webp"],
        key="update_boleto_receipt_upload",
    )
    new_receipt_paste = paste(
        label="Colar nova imagem", key="update_boleto_receipt_paste"
    )
    new_receipt_date = st.date_input(
        "Data do comprovante", format="DD/MM/YYYY", key="update_receipt_date"
    )
    new_receipt_time = st.text_input(
        "Hora (opcional)", value="", key="update_receipt_time", placeholder="18:40:12"
    )
    new_receipt_bytes = None
    new_receipt_mime = "png"
    if new_receipt_upload:
        new_receipt_bytes = new_receipt_upload.read()
        ext = (Path(new_receipt_upload.name).suffix or ".png").lstrip(".").lower()
        new_receipt_mime = (
            ext if ext in ("png", "jpg", "jpeg", "gif", "webp") else "png"
        )
        if new_receipt_mime == "jpg":
            new_receipt_mime = "jpeg"
    elif new_receipt_paste:
        try:
            if "," in new_receipt_paste:
                header, encoded = new_receipt_paste.split(",", 1)
                new_receipt_mime = "png"
                if "image/" in header:
                    new_receipt_mime = (
                        header.split("image/", 1)[-1].split(";")[0].strip()
                    )
            else:
                encoded = new_receipt_paste
            binary_data = base64.b64decode(encoded)
            new_receipt_bytes = binary_data
            if new_receipt_mime == "jpg":
                new_receipt_mime = "jpeg"
        except Exception:
            pass
    if new_receipt_bytes is not None:
        time_part = new_receipt_time.strip() if new_receipt_time else "00:00:00"
        new_receipt_date_str = f"{new_receipt_date.strftime('%d/%m/%Y')} {time_part}"
        if st.button("Salvar comprovante", key="apply_update_receipt"):
            # Remove old receipt file if present
            if receipt_path_raw:
                old_rp = (
                    Path(receipt_path_raw)
                    if Path(receipt_path_raw).is_absolute()
                    else project_root / receipt_path_raw
                )
                if old_rp.exists():
                    old_rp.unlink(missing_ok=True)
            receipt_path = save_boleto_receipt(
                boleto_id, new_receipt_bytes, new_receipt_mime
            )
            update_boleto_receipt(boleto_id, str(receipt_path), new_receipt_date_str)
            st.success("Comprovante atualizado.")
            st.rerun()
