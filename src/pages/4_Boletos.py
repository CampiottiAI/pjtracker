"""Boletos – upload boleto PDF and optional receipt image with barcode matching."""

import base64
import hashlib
from datetime import datetime
from pathlib import Path

import streamlit as st
from st_img_pastebutton import paste

from src.app import (
    DB_PATH,
    default_fiscal_mes_date,
    delete_boleto,
    format_fiscal_mes,
    fiscal_mes_to_date,
    get_boletos,
    init_db,
    save_boleto_entry,
    save_boleto_pdf,
    save_boleto_receipt,
    update_boleto_fiscal_mes,
    update_boleto_pdf,
    update_boleto_receipt,
)
from src.barcode_diff import format_barcode_diff
from src.boleto_parser import parse_boleto_pdf, parse_receipt_image
from src.streamlit_pdf_link import open_pdf_link

st.set_page_config(page_title="Boletos", layout="centered")
st.title("Boletos")

init_db()

project_root = Path(DB_PATH).resolve().parent


def _receipt_signature(image_bytes: bytes) -> str:
    return hashlib.sha1(image_bytes).hexdigest()


def _compute_match_status(
    document_digits: str | None, receipt_digits: str | None
) -> str | None:
    if not document_digits or not receipt_digits:
        return None
    return "match" if document_digits == receipt_digits else "mismatch"


def _clear_receipt_state(base_key: str) -> None:
    st.session_state[f"{base_key}_date"] = None
    st.session_state[f"{base_key}_time"] = ""
    st.session_state[f"{base_key}_signature"] = None
    st.session_state[f"{base_key}_status"] = None
    st.session_state[f"{base_key}_message"] = None
    st.session_state[f"{base_key}_value"] = None
    st.session_state[f"{base_key}_codigo_barras"] = None
    st.session_state[f"{base_key}_codigo_barras_digits"] = None
    st.session_state[f"{base_key}_source"] = None


def _populate_receipt_data(
    base_key: str,
    image_bytes: bytes,
    *,
    mime_type: str,
    filename: str,
    force: bool = False,
) -> None:
    signature = _receipt_signature(image_bytes)
    signature_key = f"{base_key}_signature"
    if not force and st.session_state.get(signature_key) == signature:
        return

    _clear_receipt_state(base_key)
    with st.spinner("Extraindo dados do comprovante..."):
        extracted = parse_receipt_image(
            image_bytes,
            filename=filename,
            mime_type=f"image/{mime_type}",
        )

    st.session_state[signature_key] = signature
    st.session_state[f"{base_key}_value"] = extracted.value
    st.session_state[f"{base_key}_codigo_barras"] = extracted.codigo_barras_raw
    st.session_state[f"{base_key}_codigo_barras_digits"] = extracted.codigo_barras_digits
    st.session_state[f"{base_key}_source"] = extracted.source

    if extracted.payment_datetime:
        try:
            dt = datetime.strptime(extracted.payment_datetime, "%d/%m/%Y %H:%M:%S")
            st.session_state[f"{base_key}_date"] = dt.date()
            st.session_state[f"{base_key}_time"] = dt.strftime("%H:%M:%S")
            st.session_state[f"{base_key}_status"] = "success"
            st.session_state[f"{base_key}_message"] = (
                f"Data extraída automaticamente: {extracted.payment_datetime}"
            )
        except ValueError:
            st.session_state[f"{base_key}_status"] = "error"
            st.session_state[f"{base_key}_message"] = "Data extraída em formato inválido."
    elif extracted.value is not None or extracted.codigo_barras_raw:
        st.session_state[f"{base_key}_status"] = "warning"
        st.session_state[f"{base_key}_message"] = (
            "A extração encontrou dados do comprovante, mas não conseguiu identificar a data automaticamente."
        )
    else:
        st.session_state[f"{base_key}_status"] = "warning"
        st.session_state[f"{base_key}_message"] = (
            "Não foi possível extrair dados do comprovante automaticamente."
        )


def _show_receipt_feedback(base_key: str, document_digits: str | None) -> None:
    status = st.session_state.get(f"{base_key}_status")
    message = st.session_state.get(f"{base_key}_message")
    if status and message:
        getattr(st, status)(message)

    source = st.session_state.get(f"{base_key}_source")
    if source:
        st.caption(f"Fonte da extração do comprovante: {source}")

    value = st.session_state.get(f"{base_key}_value")
    if value is not None:
        st.caption(f"Valor extraído do comprovante: R$ {value:,.2f}")

    codigo_barras = st.session_state.get(f"{base_key}_codigo_barras")
    codigo_barras_digits = st.session_state.get(f"{base_key}_codigo_barras_digits")
    display_barcode = codigo_barras_digits or codigo_barras
    if display_barcode:
        st.caption(f"Código de barras do comprovante: {display_barcode}")

    match_status = _compute_match_status(document_digits, codigo_barras_digits)
    if match_status == "match":
        st.success("O código de barras do comprovante corresponde ao do boleto.")
    elif match_status == "mismatch":
        st.warning("O código de barras do comprovante não corresponde ao do boleto.")
        if document_digits and codigo_barras_digits:
            with st.expander("Ver diferença entre os códigos"):
                st.code(
                    format_barcode_diff(
                        document_digits,
                        codigo_barras_digits,
                        "Boleto (documento)",
                        "Comprovante",
                    )
                )
    elif document_digits or codigo_barras_digits:
        st.info("Ainda não foi possível comparar os códigos de barras.")


def _get_receipt_payload(base_key: str) -> dict[str, str | float | None]:
    return {
        "value": st.session_state.get(f"{base_key}_value"),
        "codigo_barras": st.session_state.get(f"{base_key}_codigo_barras"),
        "codigo_barras_digits": st.session_state.get(f"{base_key}_codigo_barras_digits"),
    }


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
                parsed = parse_boleto_pdf(pdf_bytes, filename=uploaded_pdf.name or "boleto.pdf")
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
                    st.metric(
                        "Código de barras",
                        parsed.codigo_barras_raw or "—",
                    )
                st.caption(f"Fonte da extração: {parsed.source}")
                if (
                    parsed.codigo_barras_digits
                    and parsed.codigo_barras_digits != parsed.codigo_barras_raw
                ):
                    st.caption(
                        f"Código normalizado do boleto: {parsed.codigo_barras_digits}"
                    )

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
                    st.session_state["pending_boleto_receipt_pdf_key"] = pdf_key
                    _clear_receipt_state("boleto_receipt")

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
                            "filename": receipt_upload.name or "comprovante.png",
                        }
                        _populate_receipt_data(
                            "boleto_receipt",
                            data,
                            mime_type=mime,
                            filename=receipt_upload.name or "comprovante.png",
                        )
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
                                "filename": f"comprovante.{mime}",
                            }
                            _populate_receipt_data(
                                "boleto_receipt",
                                binary_data,
                                mime_type=mime,
                                filename=f"comprovante.{mime}",
                            )
                        except Exception:
                            pass
                pending_receipt = st.session_state.get("pending_boleto_receipt")
                with receipt_col2:
                    if pending_receipt:
                        _show_receipt_feedback(
                            "boleto_receipt", parsed.codigo_barras_digits
                        )
                        if st.button(
                            "Extrair comprovante novamente", key="extract_receipt_date"
                        ):
                            _populate_receipt_data(
                                "boleto_receipt",
                                pending_receipt["bytes"],
                                mime_type=pending_receipt["mime"],
                                filename=pending_receipt["filename"],
                                force=True,
                            )
                            st.rerun()
                    if "boleto_receipt_date" not in st.session_state:
                        st.session_state["boleto_receipt_date"] = None
                    if "boleto_receipt_time" not in st.session_state:
                        st.session_state["boleto_receipt_time"] = ""
                    receipt_date = st.date_input(
                        "Data do comprovante",
                        format="DD/MM/YYYY",
                        key="boleto_receipt_date",
                    )
                    receipt_time = st.text_input(
                        "Hora (opcional, ex: 18:40:12)",
                        key="boleto_receipt_time",
                        placeholder="18:40:12",
                    )
                    if pending_receipt:
                        st.caption("Comprovante anexado.")
                        if receipt_date is None:
                            receipt_date_str = None
                        else:
                            time_part = receipt_time.strip() if receipt_time else "00:00:00"
                            receipt_date_str = (
                                f"{receipt_date.strftime('%d/%m/%Y')} {time_part}"
                            )
                    else:
                        receipt_date_str = None

                st.divider()
                fiscal_mes_date = st.date_input(
                    "Fiscal Mês (mês/ano)",
                    value=default_fiscal_mes_date(),
                    format="DD/MM/YYYY",
                    key="boleto_fiscal_mes",
                )
                if st.button("Salvar boleto"):
                    if pending_receipt and receipt_date_str is None:
                        st.error("Informe ou extraia a data do comprovante.")
                    else:
                        fiscal_mes = (
                            fiscal_mes_date.replace(day=1).strftime("%Y-%m")
                            if fiscal_mes_date else None
                        )
                        if not fiscal_mes:
                            st.error("Selecione o Fiscal Mês (mês/ano).")
                        else:
                            pdf_path = save_boleto_pdf(
                                pdf_bytes,
                                emission_date=parsed.emission_date,
                                value=parsed.value,
                            )
                            inserted, boleto_id = save_boleto_entry(
                                pdf_path=str(pdf_path),
                                value=parsed.value,
                                emission_date=parsed.emission_date,
                                deadline_date=parsed.deadline_date,
                                codigo_barras=parsed.codigo_barras_raw,
                                codigo_barras_digits=parsed.codigo_barras_digits,
                                receipt_path=None,
                                receipt_date=None,
                                fiscal_mes=fiscal_mes,
                            )
                            if not inserted:
                                p = Path(pdf_path)
                                if not p.is_absolute():
                                    p = project_root / pdf_path
                                if p.exists():
                                    p.unlink(missing_ok=True)
                                st.error("Já existe um boleto com esses dados (valor e datas).")
                            else:
                                if pending_receipt and boleto_id:
                                    receipt_payload = _get_receipt_payload("boleto_receipt")
                                    receipt_path = save_boleto_receipt(
                                        boleto_id,
                                        pending_receipt["bytes"],
                                        pending_receipt["mime"],
                                    )
                                    update_boleto_receipt(
                                        boleto_id,
                                        str(receipt_path),
                                        receipt_date_str,
                                        receipt_value=receipt_payload["value"],
                                        receipt_codigo_barras=receipt_payload["codigo_barras"],
                                        receipt_codigo_barras_digits=receipt_payload[
                                            "codigo_barras_digits"
                                        ],
                                        receipt_match_status=_compute_match_status(
                                            parsed.codigo_barras_digits,
                                            receipt_payload["codigo_barras_digits"],
                                        ),
                                    )
                                st.session_state["pending_boleto_receipt"] = None
                                st.session_state["pending_boleto_receipt_pdf_key"] = None
                                st.success("Boleto salvo.")
                                st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar o PDF: {e}")

else:
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
    if st.button("Excluir boleto", type="secondary", key="delete_boleto"):
        if delete_boleto(boleto_id):
            st.success("Boleto excluído.")
            st.rerun()
        else:
            st.error("Boleto não encontrado.")
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
        st.metric("Código de barras", row.get("codigo_barras") or "—")
    with col2:
        st.metric("Data de vencimento", row.get("deadline_date") or "—")
        st.metric("Data do comprovante", row.get("receipt_date") or "—")
        receipt_value = row.get("receipt_value")
        st.metric(
            "Valor do comprovante",
            f"R$ {receipt_value:,.2f}" if receipt_value is not None else "—",
        )
    if row.get("codigo_barras_digits") and row.get("codigo_barras_digits") != row.get(
        "codigo_barras"
    ):
        st.caption(
            f"Código normalizado do boleto: {row.get('codigo_barras_digits')}"
        )
    receipt_barcode = row.get("receipt_codigo_barras_digits") or row.get(
        "receipt_codigo_barras"
    )
    if receipt_barcode:
        st.caption(f"Código de barras do comprovante: {receipt_barcode}")
    if row.get("receipt_match_status") == "match":
        st.success("O código de barras do comprovante corresponde ao do boleto.")
    elif row.get("receipt_match_status") == "mismatch":
        st.warning("O código de barras do comprovante não corresponde ao do boleto.")
        doc_d = row.get("codigo_barras_digits")
        rec_d = row.get("receipt_codigo_barras_digits")
        if doc_d and rec_d:
            with st.expander("Ver diferença entre os códigos"):
                st.code(
                    format_barcode_diff(
                        doc_d,
                        rec_d,
                        "Boleto (documento)",
                        "Comprovante",
                    )
                )
    else:
        st.info("Ainda não foi possível comparar os códigos de barras salvos.")

    st.divider()
    st.markdown("**Fiscal Mês**")
    st.caption(f"Atual: {format_fiscal_mes(row.get('fiscal_mes'))}")
    boleto_fiscal_default = fiscal_mes_to_date(row.get("fiscal_mes")) or default_fiscal_mes_date()
    boleto_fiscal_mes_date = st.date_input(
        "Alterar Fiscal Mês (mês/ano)",
        value=boleto_fiscal_default,
        format="DD/MM/YYYY",
        key="boleto_detail_fiscal_mes",
    )
    if st.button("Atualizar fiscal mês", key="boleto_update_fiscal_mes"):
        new_fiscal_mes = boleto_fiscal_mes_date.replace(day=1).strftime("%Y-%m") if boleto_fiscal_mes_date else None
        update_boleto_fiscal_mes(boleto_id, new_fiscal_mes)
        st.success("Fiscal mês atualizado.")
        st.rerun()

    pdf_path_raw = row.get("pdf_path")
    if pdf_path_raw:
        p = Path(pdf_path_raw)
        if not p.is_absolute():
            p = project_root / pdf_path_raw
        if p.exists():
            pdf_bytes = p.read_bytes()
            boleto_id = row.get("id")
            open_pdf_link(pdf_bytes, "Abrir PDF do boleto", unique_key=f"boleto_{boleto_id}")
        else:
            st.caption("PDF não encontrado.")

    receipt_path_raw = row.get("receipt_path")
    if receipt_path_raw:
        rp = Path(receipt_path_raw)
        if not rp.is_absolute():
            rp = project_root / receipt_path_raw
        if rp.exists():
            st.divider()
            st.markdown("**Comprovante anexado**")
            st.image(str(rp), use_container_width=True)

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
                parsed = parse_boleto_pdf(new_bytes, filename=new_pdf.name or "boleto.pdf")
                val_txt = f"R$ {parsed.value:,.2f}" if parsed.value is not None else "—"
                st.caption(
                    f"Novos dados: Valor {val_txt}; Emissão {parsed.emission_date or '—'}; "
                    f"Vencimento {parsed.deadline_date or '—'}"
                )
                st.caption(f"Fonte da extração: {parsed.source}")
                st.caption(f"Código de barras: {parsed.codigo_barras_raw or '—'}")
                if st.button("Aplicar e salvar novo PDF", key="apply_update_pdf"):
                    ok = update_boleto_pdf(
                        boleto_id,
                        new_bytes,
                        value=parsed.value,
                        emission_date=parsed.emission_date,
                        deadline_date=parsed.deadline_date,
                        codigo_barras=parsed.codigo_barras_raw,
                        codigo_barras_digits=parsed.codigo_barras_digits,
                        receipt_match_status=_compute_match_status(
                            parsed.codigo_barras_digits,
                            row.get("receipt_codigo_barras_digits"),
                        ),
                    )
                    if ok:
                        st.success("PDF atualizado.")
                        st.rerun()
                    else:
                        st.error("Já existe outro boleto com esses dados.")
            except Exception as e:
                st.error(f"Erro: {e}")

    st.markdown("**Atualizar comprovante** (opcional)")
    new_receipt_upload = st.file_uploader(
        "Nova imagem do comprovante",
        type=["png", "jpg", "jpeg", "gif", "webp"],
        key="update_boleto_receipt_upload",
    )
    new_receipt_paste = paste(
        label="Colar nova imagem", key="update_boleto_receipt_paste"
    )
    new_receipt_bytes = None
    new_receipt_mime = "png"
    new_receipt_filename = "comprovante.png"
    if new_receipt_upload:
        new_receipt_bytes = new_receipt_upload.read()
        ext = (Path(new_receipt_upload.name).suffix or ".png").lstrip(".").lower()
        new_receipt_mime = (
            ext if ext in ("png", "jpg", "jpeg", "gif", "webp") else "png"
        )
        if new_receipt_mime == "jpg":
            new_receipt_mime = "jpeg"
        new_receipt_filename = new_receipt_upload.name or "comprovante.png"
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
            new_receipt_filename = f"comprovante.{new_receipt_mime}"
        except Exception:
            pass
    if new_receipt_bytes is not None:
        _populate_receipt_data(
            "update_receipt",
            new_receipt_bytes,
            mime_type=new_receipt_mime,
            filename=new_receipt_filename,
        )
    new_receipt_date = st.date_input(
        "Data do comprovante", format="DD/MM/YYYY", key="update_receipt_date"
    )
    new_receipt_time = st.text_input(
        "Hora (opcional)", key="update_receipt_time", placeholder="18:40:12"
    )
    if new_receipt_bytes is not None:
        _show_receipt_feedback("update_receipt", row.get("codigo_barras_digits"))
        if st.button("Extrair comprovante novamente", key="extract_update_receipt_date"):
            _populate_receipt_data(
                "update_receipt",
                new_receipt_bytes,
                mime_type=new_receipt_mime,
                filename=new_receipt_filename,
                force=True,
            )
            st.rerun()
        time_part = new_receipt_time.strip() if new_receipt_time else "00:00:00"
        new_receipt_date_str = f"{new_receipt_date.strftime('%d/%m/%Y')} {time_part}"
        if st.button("Salvar comprovante", key="apply_update_receipt"):
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
            receipt_payload = _get_receipt_payload("update_receipt")
            update_boleto_receipt(
                boleto_id,
                str(receipt_path),
                new_receipt_date_str,
                receipt_value=receipt_payload["value"],
                receipt_codigo_barras=receipt_payload["codigo_barras"],
                receipt_codigo_barras_digits=receipt_payload["codigo_barras_digits"],
                receipt_match_status=_compute_match_status(
                    row.get("codigo_barras_digits"),
                    receipt_payload["codigo_barras_digits"],
                ),
            )
            st.success("Comprovante atualizado.")
            st.rerun()
