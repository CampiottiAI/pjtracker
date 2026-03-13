"""Extrato and caixinha extraction using structured LLM parsing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.llm_extraction import (
    extract_caixinha_pdf,
    extract_extrato_pdf,
    normalize_dd_mm_yyyy,
)


@dataclass
class ExtratoParsed:
    """Normalized fields extracted from the main extrato PDF."""

    entries: list[dict[str, str | float | None]]
    period_start: str | None
    period_end: str | None
    saldo_inicial: float | None
    rendimento: float | None
    total_entradas: float | None
    total_saidas: float | None
    saldo_final: float | None
    source: str = "llm"


@dataclass
class CaixinhaParsed:
    """Normalized fields extracted from the optional caixinha PDF."""

    entries: list[dict[str, str | float | None]]
    period_start: str | None
    period_end: str | None
    saldo_final: float | None
    source: str = "llm"


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _infer_period(entries: list[dict[str, str | float | None]]) -> tuple[str | None, str | None]:
    dates: list[datetime] = []
    for entry in entries:
        raw_date = entry.get("data")
        if not isinstance(raw_date, str):
            continue
        normalized = normalize_dd_mm_yyyy(raw_date)
        if not normalized:
            continue
        try:
            parsed = datetime.strptime(normalized, "%d/%m/%Y")
        except ValueError:
            continue
        dates.append(parsed)
    if not dates:
        return (None, None)
    dates.sort()
    return (
        dates[0].strftime("%d/%m/%Y"),
        dates[-1].strftime("%d/%m/%Y"),
    )


def parse_extrato_pdf(pdf_bytes: bytes, filename: str = "extrato.pdf") -> ExtratoParsed:
    """Extract and normalize extrato fields from PDF bytes."""
    llm_attempt = extract_extrato_pdf(pdf_bytes, filename=filename)
    llm_data = llm_attempt.data
    if llm_data is None:
        raise RuntimeError(llm_attempt.error or "Falha ao extrair os dados do extrato.")

    entries: list[dict[str, str | float | None]] = []
    for entry in getattr(llm_data, "entries", []):
        tipo = _clean_text(getattr(entry, "tipo", None))
        if tipo:
            tipo = tipo.lower()
        entries.append(
            {
                "data": normalize_dd_mm_yyyy(getattr(entry, "data", None)),
                "nome": _clean_text(getattr(entry, "nome", None)),
                "descricao": _clean_text(getattr(entry, "descricao", None)),
                "valor": getattr(entry, "valor", None),
                "tipo": tipo,
            }
        )

    period_start, period_end = _infer_period(entries)
    return ExtratoParsed(
        entries=entries,
        period_start=period_start,
        period_end=period_end,
        saldo_inicial=getattr(llm_data, "saldo_inicial", None),
        rendimento=getattr(llm_data, "rendimento", None),
        total_entradas=getattr(llm_data, "total_entradas", None),
        total_saidas=getattr(llm_data, "total_saidas", None),
        saldo_final=getattr(llm_data, "saldo_final", None),
        source="llm",
    )


def parse_caixinha_pdf(pdf_bytes: bytes, filename: str = "caixinha.pdf") -> CaixinhaParsed:
    """Extract and normalize caixinha fields from PDF bytes."""
    llm_attempt = extract_caixinha_pdf(pdf_bytes, filename=filename)
    llm_data = llm_attempt.data
    if llm_data is None:
        raise RuntimeError(llm_attempt.error or "Falha ao extrair os dados da caixinha.")

    entries: list[dict[str, str | float | None]] = []
    for entry in getattr(llm_data, "entries", []):
        entries.append(
            {
                "data": normalize_dd_mm_yyyy(getattr(entry, "data", None)),
                "movimentacao": _clean_text(getattr(entry, "movimentacao", None)),
                "rendimento": getattr(entry, "rendimento", None),
                "valor_bruto": getattr(entry, "valor_bruto", None),
                "imposto": getattr(entry, "imposto", None),
                "iof": getattr(entry, "iof", None),
                "valor_liquido": getattr(entry, "valor_liquido", None),
            }
        )

    period_start, period_end = _infer_period(entries)
    return CaixinhaParsed(
        entries=entries,
        period_start=period_start,
        period_end=period_end,
        saldo_final=getattr(llm_data, "saldo_final", None),
        source="llm",
    )
