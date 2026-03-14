"""NFs page – upload NF PDF (tab NF), view history and delete (tab Histórico)."""

import base64
import hashlib
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
from st_img_pastebutton import paste

from src.app import (
    DB_PATH,
    delete_nf,
    get_nf_entries,
    get_nf_images,
    init_db,
    save_image,
    save_nf_entry,
    save_nf_image,
    save_pdf,
)
from src.nf_parser import (
    compute_brl,
    parse_nf_pdf,
)

st.set_page_config(page_title="Nota Fiscal Tracker", layout="centered")
st.title("NFs")

init_db()

tab_nf, tab_historico = st.tabs(["NF", "Histórico"])

# --- Tab NF: upload, parse, save ---
with tab_nf:
    uploaded = st.file_uploader("Envie o PDF da Nota Fiscal", type=["pdf"], key="nf_upload")

    if uploaded is not None:
        pdf_bytes = uploaded.read()
        if not pdf_bytes:
            st.error("Arquivo vazio.")
        else:
            try:
                parsed = parse_nf_pdf(pdf_bytes, filename=uploaded.name or "nota_fiscal.pdf")
                if parsed.usd is None or parsed.rate is None:
                    st.error(
                        "Não foi possível extrair Valor em Dólar e/ou Cotação do documento. "
                        "Confira o PDF ou ajuste a extração."
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
                    verification_code = parsed.verification_code or "-"
                    nf_date = parsed.nf_date
                    payment_via = parsed.payment_via
                    date_part, time_part = "-", "-"
                    if nf_date and " " in nf_date:
                        date_part, time_part = nf_date.split(" ", 1)
                    elif nf_date:
                        date_part = nf_date
                    st.caption(f"Fonte da extração: {parsed.source}")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Empresa", parsed.company or "—")
                        st.metric("Data", date_part)
                        st.metric("Pagamento via", payment_via or "—")
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

                    # Pending images: clear when PDF context changes
                    pdf_key = uploaded.name or str(id(uploaded))
                    if st.session_state.get("pending_nf_images_pdf_key") != pdf_key:
                        st.session_state["pending_nf_images"] = []
                        st.session_state["pending_nf_images_pdf_key"] = pdf_key
                        st.session_state["pending_nf_images_added_uploads"] = set()
                        st.session_state["pending_nf_images_added_paste_hashes"] = set()
                    pending = st.session_state.setdefault("pending_nf_images", [])
                    added_uploads = st.session_state.setdefault(
                        "pending_nf_images_added_uploads", set()
                    )
                    added_paste_hashes = st.session_state.setdefault(
                        "pending_nf_images_added_paste_hashes", set()
                    )

                    st.divider()
                    st.markdown(
                        '<div style="background: #f0e8f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
                        'border-left: 4px solid #7b2cbf; margin-bottom: 1rem;">'
                        "<strong>Adicionar imagem(ns) antes de salvar</strong> — envie arquivo(s) ou cole da área de transferência.</div>",
                        unsafe_allow_html=True,
                    )
                    img_col1, img_col2 = st.columns(2)
                    with img_col1:
                        uploaded_imgs = st.file_uploader(
                            "Enviar imagem(ns)",
                            type=["png", "jpg", "jpeg", "gif", "webp"],
                            accept_multiple_files=True,
                            key="pending_image_upload",
                        )
                        if uploaded_imgs:
                            for f in uploaded_imgs:
                                key = (f.name, f.size)
                                if key not in added_uploads:
                                    data = f.read()
                                    ext = (Path(f.name).suffix or ".png").lstrip(".").lower()
                                    mime = ext if ext in ("png", "jpg", "jpeg", "gif", "webp") else "png"
                                    if mime == "jpg":
                                        mime = "jpeg"
                                    pending.append({"bytes": data, "mime": mime})
                                    added_uploads.add(key)
                    with img_col2:
                        image_data = paste(
                            label="Colar imagem da área de transferência",
                            key="paste_image_pending",
                        )
                        if image_data is not None:
                            try:
                                if "," in image_data:
                                    header, encoded = image_data.split(",", 1)
                                    mime = "png"
                                    if "image/" in header:
                                        mime = header.split("image/", 1)[-1].split(";")[0].strip()
                                else:
                                    encoded = image_data
                                    mime = "png"
                                binary_data = base64.b64decode(encoded)
                                paste_hash = hashlib.sha256(binary_data).hexdigest()
                                if paste_hash not in added_paste_hashes:
                                    pending.append({"bytes": binary_data, "mime": mime})
                                    added_paste_hashes.add(paste_hash)
                            except Exception:
                                pass  # ignore malformed paste
                    if pending:
                        st.caption(f"{len(pending)} imagem(ns) anexada(s) — serão salvas com a NF.")

                    st.divider()
                    if st.button("Aceitar e salvar", key="accept_save_nf"):
                        pdf_path_obj = save_pdf(
                            pdf_bytes, verification_code, nf_date, parsed.usd
                        )
                        pdf_path_str = str(pdf_path_obj)
                        inserted, nf_id = save_nf_entry(
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
                        project_root = Path(DB_PATH).resolve().parent
                        for item in pending:
                            try:
                                path_obj = save_image(item["bytes"], nf_id, item["mime"])
                                rel_path = path_obj.relative_to(project_root)
                                save_nf_image(nf_id, str(rel_path))
                            except Exception:
                                pass  # log and continue
                        st.session_state["last_saved_nf_id"] = nf_id
                        st.session_state["pending_nf_images"] = []
                        st.session_state["pending_nf_images_added_uploads"] = set()
                        st.session_state["pending_nf_images_added_paste_hashes"] = set()
                        st.rerun()

            except Exception as e:
                st.error(f"Erro ao processar o PDF: {e}")

    # Sucesso ao salvar — mostrar mensagem e opção de adicionar outra NF
    if st.session_state.get("last_saved_nf_id"):
        st.divider()
        st.success("NF salva com sucesso.")
        if st.button("Adicionar outra NF", key="done_add_nf"):
            del st.session_state["last_saved_nf_id"]
            st.rerun()

# --- Tab Histórico: filter, list, view, download, delete ---
with tab_historico:
    st.subheader("Histórico de Notas Fiscais")

    if "hist_applied_date_from" not in st.session_state:
        st.session_state.hist_applied_date_from = date.today() - timedelta(days=30)
    if "hist_applied_date_to" not in st.session_state:
        st.session_state.hist_applied_date_to = date.today()

    date_from = st.date_input("De", value=st.session_state.hist_applied_date_from, format="DD/MM/YYYY", key="hist_date_from")
    date_to = st.date_input("Até", value=st.session_state.hist_applied_date_to, format="DD/MM/YYYY", key="hist_date_to")

    if date_from > date_to:
        st.warning("A data 'De' deve ser anterior ou igual à data 'Até'.")

    if st.button("Aplicar filtro", key="hist_apply_filter"):
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
    else:

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
            key="hist_radio",
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
                    key="hist_download_pdf",
                )
            else:
                st.info("PDF não disponível para esta NF.")
        else:
            st.info("PDF não disponível para esta NF.")

        nf_id = row.get("id")
        if st.session_state.get("hist_nf_deleted"):
            st.success("NF excluída.")
            del st.session_state["hist_nf_deleted"]
        if st.button("Excluir NF", type="secondary", key="hist_delete_nf"):
            if nf_id is not None and delete_nf(nf_id):
                st.session_state["hist_nf_deleted"] = True
                st.rerun()
            else:
                st.error("NF não encontrada.")

        # Imagens anexadas
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
