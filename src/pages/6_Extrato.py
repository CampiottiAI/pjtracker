"""Extrato – upload statement PDF, optional caixinha PDF, optional Higlobe PDF."""

import json
from pathlib import Path

import streamlit as st

from src.app import (
    DB_PATH,
    default_fiscal_mes_date,
    delete_extrato,
    format_fiscal_mes,
    fiscal_mes_to_date,
    get_extrato_by_id,
    get_extratos,
    init_db,
    remove_caixinha_pdf,
    remove_higlobe_pdf,
    save_caixinha_pdf,
    save_extrato_entry,
    save_extrato_pdf,
    save_higlobe_pdf,
    update_caixinha_pdf,
    update_higlobe_pdf,
    update_extrato_fiscal_mes,
    update_extrato_pdf,
)
from src.extrato_parser import parse_caixinha_pdf, parse_extrato_pdf, parse_higlobe_pdf
from src.streamlit_pdf_link import open_pdf_link

st.set_page_config(page_title="Extrato", layout="centered")
st.title("Extrato")

init_db()

project_root = Path(DB_PATH).resolve().parent


def _set_flash_messages(success: str, warning: str | None = None) -> None:
    st.session_state["extrato_flash_success"] = success
    if warning:
        st.session_state["extrato_flash_warning"] = warning


def _show_flash_messages() -> None:
    success = st.session_state.pop("extrato_flash_success", None)
    warning = st.session_state.pop("extrato_flash_warning", None)
    if success:
        st.success(success)
    if warning:
        st.warning(warning)


def _format_currency(value: float | None) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.2f}"


def _load_entries(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _resolve_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_root / raw_path
    return path


def _show_extrato_summary(
    *,
    period_start: str | None,
    period_end: str | None,
    saldo_inicial: float | None,
    rendimento: float | None,
    total_entradas: float | None,
    total_saidas: float | None,
    saldo_final: float | None,
    source: str | None = None,
) -> None:
    st.markdown(
        '<div style="background: #e8f4f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
        'border-left: 4px solid #1f77b4; margin-bottom: 1rem;">'
        "<strong>Dados extraídos do extrato</strong></div>",
        unsafe_allow_html=True,
    )
    if period_start or period_end:
        st.caption(f"Período identificado: {period_start or '—'} até {period_end or '—'}")
    cols = st.columns(5)
    cols[0].metric("Saldo inicial", _format_currency(saldo_inicial))
    cols[1].metric("Rendimento", _format_currency(rendimento))
    cols[2].metric("Entradas", _format_currency(total_entradas))
    cols[3].metric("Saídas", _format_currency(total_saidas))
    cols[4].metric("Saldo final", _format_currency(saldo_final))
    if source:
        st.caption(f"Fonte da extração: {source}")


def _show_caixinha_summary(
    *,
    period_start: str | None,
    period_end: str | None,
    saldo_final: float | None,
    source: str | None = None,
) -> None:
    st.markdown(
        '<div style="background: #f0e8f8; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
        'border-left: 4px solid #7b2cbf; margin-bottom: 1rem;">'
        "<strong>Dados extraídos da caixinha</strong></div>",
        unsafe_allow_html=True,
    )
    if period_start or period_end:
        st.caption(f"Período identificado: {period_start or '—'} até {period_end or '—'}")
    st.metric("Saldo final da caixinha", _format_currency(saldo_final))
    if source:
        st.caption(f"Fonte da extração: {source}")


def _show_higlobe_summary(
    *,
    period_start: str | None,
    period_end: str | None,
    source: str | None = None,
) -> None:
    st.markdown(
        '<div style="background: #e8f8f0; color: black; padding: 0.5rem 1rem; border-radius: 8px; '
        'border-left: 4px solid #2ca02c; margin-bottom: 1rem;">'
        "<strong>Dados extraídos do extrato Higlobe</strong></div>",
        unsafe_allow_html=True,
    )
    if period_start or period_end:
        st.caption(f"Período identificado: {period_start or '—'} até {period_end or '—'}")
    if source:
        st.caption(f"Fonte da extração: {source}")


def _show_entries_table(title: str, entries: list[dict]) -> None:
    st.markdown(f"**{title}**")
    if not entries:
        st.info("Nenhum item extraído.")
        return
    st.dataframe(entries, use_container_width=True)


mode = st.radio(
    "Modo",
    ["Adicionar extrato", "Listar extratos"],
    horizontal=True,
)

_show_flash_messages()

if mode == "Adicionar extrato":
    st.subheader("Novo extrato")
    uploaded_extrato = st.file_uploader(
        "Envie o PDF do extrato",
        type=["pdf"],
        key="extrato_pdf_upload",
    )

    if uploaded_extrato is not None:
        extrato_bytes = uploaded_extrato.read()
        uploaded_extrato.seek(0)
        if not extrato_bytes:
            st.error("Arquivo vazio.")
        else:
            try:
                parsed_extrato = parse_extrato_pdf(
                    extrato_bytes,
                    filename=uploaded_extrato.name or "extrato.pdf",
                )
                _show_extrato_summary(
                    period_start=parsed_extrato.period_start,
                    period_end=parsed_extrato.period_end,
                    saldo_inicial=parsed_extrato.saldo_inicial,
                    rendimento=parsed_extrato.rendimento,
                    total_entradas=parsed_extrato.total_entradas,
                    total_saidas=parsed_extrato.total_saidas,
                    saldo_final=parsed_extrato.saldo_final,
                    source=parsed_extrato.source,
                )
                _show_entries_table("Transações do extrato", parsed_extrato.entries)

                st.divider()
                st.subheader("Caixinha (opcional)")
                uploaded_caixinha = st.file_uploader(
                    "Envie o PDF da caixinha",
                    type=["pdf"],
                    key="caixinha_pdf_upload",
                )
                parsed_caixinha = None
                caixinha_bytes = None

                if uploaded_caixinha is not None:
                    caixinha_bytes = uploaded_caixinha.read()
                    uploaded_caixinha.seek(0)
                    if not caixinha_bytes:
                        st.error("Arquivo da caixinha vazio.")
                    else:
                        parsed_caixinha = parse_caixinha_pdf(
                            caixinha_bytes,
                            filename=uploaded_caixinha.name or "caixinha.pdf",
                        )
                        _show_caixinha_summary(
                            period_start=parsed_caixinha.period_start,
                            period_end=parsed_caixinha.period_end,
                            saldo_final=parsed_caixinha.saldo_final,
                            source=parsed_caixinha.source,
                        )
                        _show_entries_table(
                            "Movimentações da caixinha",
                            parsed_caixinha.entries,
                        )

                st.divider()
                st.subheader("Extrato Higlobe (opcional)")
                uploaded_higlobe = st.file_uploader(
                    "Envie o PDF do extrato Higlobe",
                    type=["pdf"],
                    key="higlobe_pdf_upload",
                )
                parsed_higlobe = None
                higlobe_bytes = None

                if uploaded_higlobe is not None:
                    higlobe_bytes = uploaded_higlobe.read()
                    uploaded_higlobe.seek(0)
                    if not higlobe_bytes:
                        st.error("Arquivo Higlobe vazio.")
                    else:
                        parsed_higlobe = parse_higlobe_pdf(
                            higlobe_bytes,
                            filename=uploaded_higlobe.name or "higlobe.pdf",
                        )
                        _show_higlobe_summary(
                            period_start=parsed_higlobe.period_start,
                            period_end=parsed_higlobe.period_end,
                            source=parsed_higlobe.source,
                        )
                        _show_entries_table(
                            "Transações Higlobe",
                            parsed_higlobe.entries,
                        )

                st.divider()
                fiscal_mes_date = st.date_input(
                    "Fiscal Mês (mês/ano)",
                    value=default_fiscal_mes_date(),
                    format="DD/MM/YYYY",
                    key="extrato_fiscal_mes",
                )
                if st.button("Salvar extrato", key="save_extrato"):
                    fiscal_mes = (
                        fiscal_mes_date.replace(day=1).strftime("%Y-%m")
                        if fiscal_mes_date else None
                    )
                    if not fiscal_mes:
                        st.error("Selecione o Fiscal Mês (mês/ano).")
                    else:
                        extrato_pdf_path = save_extrato_pdf(
                            extrato_bytes,
                            period_start=parsed_extrato.period_start,
                            period_end=parsed_extrato.period_end,
                        )
                        caixinha_pdf_path = None
                        if caixinha_bytes is not None and parsed_caixinha is not None:
                            caixinha_pdf_path = save_caixinha_pdf(
                                caixinha_bytes,
                                period_start=parsed_caixinha.period_start or parsed_extrato.period_start,
                                period_end=parsed_caixinha.period_end or parsed_extrato.period_end,
                            )

                        higlobe_pdf_path = None
                        if higlobe_bytes is not None and parsed_higlobe is not None:
                            higlobe_pdf_path = save_higlobe_pdf(
                                higlobe_bytes,
                                period_start=parsed_higlobe.period_start or parsed_extrato.period_start,
                                period_end=parsed_higlobe.period_end or parsed_extrato.period_end,
                            )

                        inserted, _ = save_extrato_entry(
                            extrato_pdf_path=str(extrato_pdf_path),
                            period_start=parsed_extrato.period_start,
                            period_end=parsed_extrato.period_end,
                            saldo_inicial=parsed_extrato.saldo_inicial,
                            rendimento=parsed_extrato.rendimento,
                            total_entradas=parsed_extrato.total_entradas,
                            total_saidas=parsed_extrato.total_saidas,
                            saldo_final=parsed_extrato.saldo_final,
                            extrato_entries_json=json.dumps(parsed_extrato.entries),
                            caixinha_pdf_path=str(caixinha_pdf_path) if caixinha_pdf_path else None,
                            caixinha_saldo_final=(
                                parsed_caixinha.saldo_final if parsed_caixinha else None
                            ),
                            caixinha_entries_json=(
                                json.dumps(parsed_caixinha.entries) if parsed_caixinha else None
                            ),
                            higlobe_pdf_path=str(higlobe_pdf_path) if higlobe_pdf_path else None,
                            higlobe_entries_json=(
                                json.dumps(parsed_higlobe.entries) if parsed_higlobe else None
                            ),
                            fiscal_mes=fiscal_mes,
                        )
                        if not inserted:
                            extrato_path = _resolve_path(str(extrato_pdf_path))
                            if extrato_path and extrato_path.exists():
                                extrato_path.unlink(missing_ok=True)
                            saved_caixinha_path = (
                                _resolve_path(str(caixinha_pdf_path)) if caixinha_pdf_path else None
                            )
                            if saved_caixinha_path and saved_caixinha_path.exists():
                                saved_caixinha_path.unlink(missing_ok=True)
                            saved_higlobe_path = (
                                _resolve_path(str(higlobe_pdf_path)) if higlobe_pdf_path else None
                            )
                            if saved_higlobe_path and saved_higlobe_path.exists():
                                saved_higlobe_path.unlink(missing_ok=True)
                            st.error("Já existe um extrato salvo para esse período.")
                        else:
                            _set_flash_messages(
                                "Extrato salvo.",
                                "Confira os dados extraídos antes de usar. A leitura do PDF é feita por IA e pode precisar de revisão.",
                            )
                            st.rerun()
            except Exception as exc:
                st.error(f"Erro ao processar o PDF: {exc}")

else:
    extratos = get_extratos()
    if not extratos:
        st.info("Nenhum extrato cadastrado.")
        st.stop()

    def _label(row: dict) -> str:
        period_start = row.get("period_start") or "—"
        period_end = row.get("period_end") or "—"
        saldo_final = _format_currency(row.get("saldo_final"))
        return f"{period_start} até {period_end} — {saldo_final} — ID {row.get('id')}"

    options = list(range(len(extratos)))
    selected_idx = st.radio(
        "Selecione um extrato",
        options=options,
        format_func=lambda i: _label(extratos[i]),
    )
    row = extratos[selected_idx]
    extrato_id = row["id"]

    st.divider()
    if st.button("Excluir extrato", type="secondary", key="delete_extrato"):
        if delete_extrato(extrato_id):
            st.success("Extrato excluído.")
            st.rerun()
        else:
            st.error("Extrato não encontrado.")

    _show_extrato_summary(
        period_start=row.get("period_start"),
        period_end=row.get("period_end"),
        saldo_inicial=row.get("saldo_inicial"),
        rendimento=row.get("rendimento"),
        total_entradas=row.get("total_entradas"),
        total_saidas=row.get("total_saidas"),
        saldo_final=row.get("saldo_final"),
    )
    _show_entries_table(
        "Transações salvas do extrato",
        _load_entries(row.get("extrato_entries_json")),
    )

    st.divider()
    st.markdown("**Fiscal Mês**")
    st.caption(f"Atual: {format_fiscal_mes(row.get('fiscal_mes'))}")
    extrato_fiscal_default = fiscal_mes_to_date(row.get("fiscal_mes")) or default_fiscal_mes_date()
    extrato_fiscal_mes_date = st.date_input(
        "Alterar Fiscal Mês (mês/ano)",
        value=extrato_fiscal_default,
        format="DD/MM/YYYY",
        key="extrato_detail_fiscal_mes",
    )
    if st.button("Atualizar fiscal mês", key="extrato_update_fiscal_mes"):
        new_fiscal_mes = extrato_fiscal_mes_date.replace(day=1).strftime("%Y-%m") if extrato_fiscal_mes_date else None
        update_extrato_fiscal_mes(extrato_id, new_fiscal_mes)
        st.success("Fiscal mês atualizado.")
        st.rerun()

    extrato_path = _resolve_path(row.get("extrato_pdf_path"))
    if extrato_path and extrato_path.exists():
        open_pdf_link(
            extrato_path.read_bytes(),
            "Abrir PDF do extrato",
            unique_key=f"extrato_{extrato_id}",
        )
    else:
        st.caption("PDF do extrato não encontrado.")

    st.divider()
    if row.get("caixinha_pdf_path"):
        _show_caixinha_summary(
            period_start=row.get("period_start"),
            period_end=row.get("period_end"),
            saldo_final=row.get("caixinha_saldo_final"),
        )
        _show_entries_table(
            "Movimentações salvas da caixinha",
            _load_entries(row.get("caixinha_entries_json")),
        )
        caixinha_path = _resolve_path(row.get("caixinha_pdf_path"))
        if caixinha_path and caixinha_path.exists():
            open_pdf_link(
                caixinha_path.read_bytes(),
                "Abrir PDF da caixinha",
                unique_key=f"extrato_{extrato_id}_caixinha",
            )
        else:
            st.caption("PDF da caixinha não encontrado.")
        if st.button("Remover caixinha", key=f"remove_caixinha_{extrato_id}"):
            if remove_caixinha_pdf(extrato_id):
                st.success("Caixinha removida.")
                st.rerun()
            else:
                st.error("Não foi possível remover a caixinha.")
    else:
        st.info("Caixinha ausente.")

    st.divider()
    if row.get("higlobe_pdf_path"):
        _show_higlobe_summary(
            period_start=row.get("period_start"),
            period_end=row.get("period_end"),
        )
        _show_entries_table(
            "Transações salvas Higlobe",
            _load_entries(row.get("higlobe_entries_json")),
        )
        higlobe_path = _resolve_path(row.get("higlobe_pdf_path"))
        if higlobe_path and higlobe_path.exists():
            open_pdf_link(
                higlobe_path.read_bytes(),
                "Abrir PDF do extrato Higlobe",
                unique_key=f"extrato_{extrato_id}_higlobe",
            )
        else:
            st.caption("PDF do extrato Higlobe não encontrado.")
        if st.button("Remover extrato Higlobe", key=f"remove_higlobe_{extrato_id}"):
            if remove_higlobe_pdf(extrato_id):
                st.success("Extrato Higlobe removido.")
                st.rerun()
            else:
                st.error("Não foi possível remover o extrato Higlobe.")
    else:
        st.info("Extrato Higlobe ausente.")

    st.divider()
    st.subheader("Atualizar extrato")
    new_extrato = st.file_uploader(
        "Substituir PDF do extrato (opcional)",
        type=["pdf"],
        key="update_extrato_pdf",
    )
    if new_extrato is not None:
        new_extrato_bytes = new_extrato.read()
        if new_extrato_bytes:
            try:
                parsed_extrato = parse_extrato_pdf(
                    new_extrato_bytes,
                    filename=new_extrato.name or "extrato.pdf",
                )
                _show_extrato_summary(
                    period_start=parsed_extrato.period_start,
                    period_end=parsed_extrato.period_end,
                    saldo_inicial=parsed_extrato.saldo_inicial,
                    rendimento=parsed_extrato.rendimento,
                    total_entradas=parsed_extrato.total_entradas,
                    total_saidas=parsed_extrato.total_saidas,
                    saldo_final=parsed_extrato.saldo_final,
                    source=parsed_extrato.source,
                )
                if st.button("Aplicar e salvar novo extrato", key="apply_update_extrato"):
                    ok = update_extrato_pdf(
                        extrato_id,
                        new_extrato_bytes,
                        period_start=parsed_extrato.period_start,
                        period_end=parsed_extrato.period_end,
                        saldo_inicial=parsed_extrato.saldo_inicial,
                        rendimento=parsed_extrato.rendimento,
                        total_entradas=parsed_extrato.total_entradas,
                        total_saidas=parsed_extrato.total_saidas,
                        saldo_final=parsed_extrato.saldo_final,
                        extrato_entries_json=json.dumps(parsed_extrato.entries),
                    )
                    if ok:
                        _set_flash_messages(
                            "Extrato atualizado.",
                            "Confira os dados extraídos antes de usar. A leitura do PDF é feita por IA e pode precisar de revisão.",
                        )
                        st.rerun()
                    else:
                        st.error("Já existe outro extrato salvo para esse período.")
            except Exception as exc:
                st.error(f"Erro ao processar o novo extrato: {exc}")

    st.divider()
    st.subheader("Atualizar caixinha")
    new_caixinha = st.file_uploader(
        "Substituir PDF da caixinha (opcional)",
        type=["pdf"],
        key="update_caixinha_pdf",
    )
    if new_caixinha is not None:
        new_caixinha_bytes = new_caixinha.read()
        if new_caixinha_bytes:
            try:
                parsed_caixinha = parse_caixinha_pdf(
                    new_caixinha_bytes,
                    filename=new_caixinha.name or "caixinha.pdf",
                )
                _show_caixinha_summary(
                    period_start=parsed_caixinha.period_start,
                    period_end=parsed_caixinha.period_end,
                    saldo_final=parsed_caixinha.saldo_final,
                    source=parsed_caixinha.source,
                )
                if st.button("Aplicar e salvar nova caixinha", key="apply_update_caixinha"):
                    ok = update_caixinha_pdf(
                        extrato_id,
                        new_caixinha_bytes,
                        period_start=parsed_caixinha.period_start or row.get("period_start"),
                        period_end=parsed_caixinha.period_end or row.get("period_end"),
                        caixinha_saldo_final=parsed_caixinha.saldo_final,
                        caixinha_entries_json=json.dumps(parsed_caixinha.entries),
                    )
                    if ok:
                        _set_flash_messages(
                            "Caixinha atualizada.",
                            "Confira os dados extraídos antes de usar. A leitura do PDF é feita por IA e pode precisar de revisão.",
                        )
                        st.rerun()
                    else:
                        st.error("Extrato não encontrado.")
            except Exception as exc:
                st.error(f"Erro ao processar a nova caixinha: {exc}")

    st.divider()
    st.subheader("Atualizar extrato Higlobe")
    new_higlobe = st.file_uploader(
        "Substituir PDF do extrato Higlobe (opcional)",
        type=["pdf"],
        key="update_higlobe_pdf",
    )
    if new_higlobe is not None:
        new_higlobe_bytes = new_higlobe.read()
        if new_higlobe_bytes:
            try:
                parsed_higlobe = parse_higlobe_pdf(
                    new_higlobe_bytes,
                    filename=new_higlobe.name or "higlobe.pdf",
                )
                _show_higlobe_summary(
                    period_start=parsed_higlobe.period_start,
                    period_end=parsed_higlobe.period_end,
                    source=parsed_higlobe.source,
                )
                if st.button("Aplicar e salvar novo extrato Higlobe", key="apply_update_higlobe"):
                    ok = update_higlobe_pdf(
                        extrato_id,
                        new_higlobe_bytes,
                        period_start=parsed_higlobe.period_start or row.get("period_start"),
                        period_end=parsed_higlobe.period_end or row.get("period_end"),
                        higlobe_entries_json=json.dumps(parsed_higlobe.entries),
                    )
                    if ok:
                        _set_flash_messages(
                            "Extrato Higlobe atualizado.",
                            "Confira os dados extraídos antes de usar. A leitura do PDF é feita por IA e pode precisar de revisão.",
                        )
                        st.rerun()
                    else:
                        st.error("Extrato não encontrado.")
            except Exception as exc:
                st.error(f"Erro ao processar o novo extrato Higlobe: {exc}")

    refreshed_row = get_extrato_by_id(extrato_id) or row
    if refreshed_row.get("caixinha_pdf_path") is None:
        st.caption("Você também pode adicionar uma caixinha depois, enviando um PDF acima.")
    if refreshed_row.get("higlobe_pdf_path") is None:
        st.caption("Você também pode adicionar o extrato Higlobe depois, enviando um PDF acima.")
