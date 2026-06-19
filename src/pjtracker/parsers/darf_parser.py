"""DARF extraction with LLM-first parsing and OCR fallback."""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from pjtracker.llm_extraction import (
    extract_darf_pdf,
    normalize_dd_mm_yyyy,
    normalize_digits,
    normalize_mm_yyyy,
)
from pjtracker.parsers.boleto_parser import _needs_ocr_fallback
from pjtracker.parsers.ocr import pdf_to_text
from pjtracker.parsers.parse_cache import cached_parse


@dataclass
class DarfParsed:
    """Extracted fields from the DARF PDF."""

    value: float | None
    emission_date: str | None  # MM/YYYY
    deadline_date: str | None  # DD/MM/YYYY
    codigo_barras_raw: str | None = None
    codigo_barras_digits: str | None = None
    source: str = "fallback"


def _normalize_br_number(s: str) -> float:
    """Parse Brazilian number: 1.234,56 or 1234,56."""
    s = s.strip().replace(" ", "")
    if "," in s and "." in s:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_dot > last_comma:
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if re.match(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    return float(s)


_VALUE_PATTERN = re.compile(
    r"Total\s+documento\s*[:\-]?\s*([\d.,\s]+)",
    re.IGNORECASE,
)
_TEXT_PERIOD_PATTERN = re.compile(
    r"\b([A-Za-zÀ-ÿ]{3,12})\s*[/\\|Il1]\s*(\d{4})\b",
    re.IGNORECASE,
)
_NUMERIC_PERIOD_PATTERN = re.compile(r"\b(0[1-9]|1[0-2])/\s*(\d{4})\b")
_FULL_DATE_PATTERN = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

_MONTH_NAMES = {
    "jan": 1,
    "janeiro": 1,
    "january": 1,
    "feb": 2,
    "fev": 2,
    "fevereiro": 2,
    "february": 2,
    "mar": 3,
    "marco": 3,
    "march": 3,
    "apr": 4,
    "abr": 4,
    "abril": 4,
    "april": 4,
    "may": 5,
    "mai": 5,
    "maio": 5,
    "jun": 6,
    "junho": 6,
    "june": 6,
    "jul": 7,
    "julho": 7,
    "july": 7,
    "aug": 8,
    "ago": 8,
    "agosto": 8,
    "august": 8,
    "sep": 9,
    "set": 9,
    "setembro": 9,
    "september": 9,
    "oct": 10,
    "out": 10,
    "outubro": 10,
    "october": 10,
    "nov": 11,
    "novembro": 11,
    "november": 11,
    "dec": 12,
    "dez": 12,
    "dezembro": 12,
    "december": 12,
}


def _normalize_word(s: str) -> str:
    normalized = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _parse_period_from_text(text: str) -> str | None:
    for match in _TEXT_PERIOD_PATTERN.finditer(text):
        month_token = _normalize_word(match.group(1))
        month = _MONTH_NAMES.get(month_token)
        if month is None:
            continue
        year = match.group(2)
        return f"{month:02d}/{year}"

    # Fallback for OCR that misses the month name but still captures PA:01/2026.
    for match in _NUMERIC_PERIOD_PATTERN.finditer(text):
        month = int(match.group(1))
        year = match.group(2)
        return f"{month:02d}/{year}"

    return None


def _score_deadline_candidate(text: str, match: re.Match[str]) -> tuple[int, int]:
    date_str = match.group(1)
    start, end = match.span(1)
    before = _normalize_word(text[max(0, start - 50):start])
    after = _normalize_word(text[end:min(len(text), end + 20)])

    score = 0
    if "vencimento" in before or "vencimento" in after:
        score += 3
    if "pagar ate" in before or "pagar ate" in after:
        score += 3
    if "data de vencimento" in before:
        score += 2
    if re.search(r"\s\d{2}[.:]\d{2}[.:]\d{2}", after):
        score -= 2

    return (score, Counter(_FULL_DATE_PATTERN.findall(text))[date_str])


def _parse_deadline_date(text: str) -> str | None:
    candidates: list[tuple[tuple[int, int], int, str]] = []

    for match in _FULL_DATE_PATTERN.finditer(text):
        date_str = match.group(1)
        try:
            datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            continue
        candidates.append((_score_deadline_candidate(text, match), match.start(1), date_str))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0][0], -item[0][1], item[1]))
    return candidates[0][2]


def _clean_text_field(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_darf_pdf_with_ocr(pdf_bytes: bytes) -> DarfParsed:
    """Extract total amount, period, and due date from DARF PDF OCR text."""
    text = pdf_to_text(pdf_bytes)
    value: float | None = None

    for match in _VALUE_PATTERN.finditer(text):
        raw = match.group(1).strip()
        raw = re.sub(r"[.\s]+$", "", raw)
        if not raw:
            continue
        try:
            value = _normalize_br_number(raw)
            if value > 0:
                break
        except ValueError:
            continue

    return DarfParsed(
        value=value,
        emission_date=_parse_period_from_text(text),
        deadline_date=_parse_deadline_date(text),
    )


def _parse_darf_pdf_inner(pdf_bytes: bytes, filename: str = "darf.pdf") -> DarfParsed:
    """Extract DARF fields using the LLM first and OCR as fallback."""
    llm_attempt = extract_darf_pdf(pdf_bytes, filename=filename)
    llm_data = llm_attempt.data

    llm_value = getattr(llm_data, "valor", None) if llm_data else None
    llm_period = normalize_mm_yyyy(
        getattr(llm_data, "periodo_apuracao", None) if llm_data else None
    )
    llm_deadline_date = normalize_dd_mm_yyyy(
        getattr(llm_data, "data_vencimento", None) if llm_data else None
    )
    llm_codigo_barras = _clean_text_field(
        getattr(llm_data, "codigo_barras", None) if llm_data else None
    )

    fallback: DarfParsed | None = None
    if _needs_ocr_fallback(llm_value, llm_period, llm_deadline_date):
        fallback = _parse_darf_pdf_with_ocr(pdf_bytes)

    used_fallback = False
    value = llm_value
    if value is None and fallback is not None:
        value = fallback.value
        used_fallback = used_fallback or value is not None

    emission_date = llm_period
    if emission_date is None and fallback is not None:
        emission_date = fallback.emission_date
        used_fallback = used_fallback or emission_date is not None

    deadline_date = llm_deadline_date
    if deadline_date is None and fallback is not None:
        deadline_date = fallback.deadline_date
        used_fallback = used_fallback or deadline_date is not None

    has_llm_data = any(
        (
            llm_value is not None,
            llm_period is not None,
            llm_deadline_date is not None,
            llm_codigo_barras is not None,
        )
    )
    source = "fallback"
    if has_llm_data and used_fallback:
        source = "merged"
    elif has_llm_data:
        source = "llm"

    return DarfParsed(
        value=value,
        emission_date=emission_date,
        deadline_date=deadline_date,
        codigo_barras_raw=llm_codigo_barras,
        codigo_barras_digits=normalize_digits(llm_codigo_barras),
        source=source,
    )


def parse_darf_pdf(pdf_bytes: bytes, filename: str = "darf.pdf") -> DarfParsed:
    """Extract DARF fields using the LLM first and OCR as fallback."""
    return cached_parse(
        pdf_bytes,
        f"darf:{filename}",
        lambda: _parse_darf_pdf_inner(pdf_bytes, filename=filename),
    )
