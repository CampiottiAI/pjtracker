"""Boleto PDF parser: extract value (R$) and dates (DD/MM/YYYY) from boleto PDF text."""

import re
from dataclasses import dataclass
from datetime import datetime

from pdf2image import convert_from_bytes
import numpy as np
import easyocr


@dataclass
class BoletoParsed:
    """Extracted fields from the boleto PDF."""

    value: float | None
    emission_date: str | None  # DD/MM/YYYY
    deadline_date: str | None  # DD/MM/YYYY


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


# DD/MM/YYYY in boleto
_DATE_PATTERN = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

# R$ followed by number (BR format: 1.234,56 or 1234,56)
_VALUE_PATTERN = re.compile(
    r"Valor documento R\s*[\$,s]\s*([\d.,\s]+)",
    re.IGNORECASE,
)


def boleto_text_extractor(pdf_bytes: bytes):
    ocr = easyocr.Reader(["pt"])
    pages = convert_from_bytes(pdf_bytes)
    full_text = ""
    for page in pages:
        image = np.array(page)
        lines = ocr.readtext(
            image,
            detail=0,
            canvas_size=1280,
            mag_ratio=1,
            batch_size=1,
        )
        text = " ".join(lines)
        full_text += f"\n\n {text}"
    return full_text


def parse_boleto_pdf(pdf_bytes: bytes) -> BoletoParsed:
    """Extract value and emission/deadline dates from boleto PDF. Dates are sorted:
    first = emission_date, second = deadline_date."""
    text = boleto_text_extractor(pdf_bytes)
    value: float | None = None
    emission_date: str | None = None
    deadline_date: str | None = None

    # Value: take the first R$ amount that parses (often the main "Valor" line)
    for m in _VALUE_PATTERN.finditer(text):
        raw = m.group(1).strip()
        raw = re.sub(r"[.\s]+$", "", raw)
        if not raw:
            continue
        try:
            value = _normalize_br_number(raw)
            if value > 0:
                break
        except ValueError:
            continue

    # Dates: all DD/MM/YYYY, sort by date; first = emission, second = deadline
    date_strs: list[str] = list(_DATE_PATTERN.findall(text))
    parsed_dates: list[tuple[str, datetime]] = []
    for dstr in date_strs:
        try:
            dt = datetime.strptime(dstr, "%d/%m/%Y")
            parsed_dates.append((dstr, dt))
        except ValueError:
            continue
    parsed_dates = list(set(parsed_dates))
    parsed_dates.sort(key=lambda x: x[1])
    if len(parsed_dates) >= 2:
        emission_date = parsed_dates[0][0]
        deadline_date = parsed_dates[1][0]
    elif len(parsed_dates) == 1:
        emission_date = parsed_dates[0][0]
        deadline_date = None

    return BoletoParsed(
        value=value,
        emission_date=emission_date,
        deadline_date=deadline_date,
    )
