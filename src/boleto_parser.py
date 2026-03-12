"""Boleto PDF parser: extract value (R$) and dates (DD/MM/YYYY) from boleto PDF text.
Receipt image parser: extract receipt date (DD MMM YYYY - HH:MM:SS) from receipt image via EasyOCR."""

import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

import numpy as np
import easyocr
from pdf2image import convert_from_bytes
from PIL import Image


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


# --- Receipt image: extract text and find date "03 MAR 2026 - 18:40:12" ---

# DD MMM YYYY - HH:MM:SS (month 3 letters: PT or EN)
_RECEIPT_DATE_PATTERN = re.compile(
    r"(\d{1,2}) ([A-Za-z]{3}) (\d{4})\s[-]?\s?(\d{2})[:,\.](\d{2})[:,\.](\d{2})",
    re.IGNORECASE,
)

_MONTH_NAMES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
    "feb": 2, "apr": 4, "may": 5, "aug": 8, "sep": 9, "oct": 10,
}


def receipt_text_extractor(image_bytes: bytes) -> str:
    """Extract text from receipt image using EasyOCR (same as boleto)."""
    ocr = easyocr.Reader(["pt"])
    img = Image.open(BytesIO(image_bytes))
    # Only keep the first third of the image vertically before running OCR
    width, height = img.size
    img = img.crop((0, 0, width, height // 3))
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = np.array(img)
    lines = ocr.readtext(
        arr,
        detail=0,
        canvas_size=1280,
        mag_ratio=1,
        batch_size=1,
    )
    return " ".join(lines)


def parse_receipt_date_from_text(text: str) -> str | None:
    """Find first date in receipt format '03 MAR 2026 - 18:40:12', return 'DD/MM/YYYY HH:MM:SS'."""
    for m in _RECEIPT_DATE_PATTERN.finditer(text):
        day_s, month_s, year_s = m.group(1), m.group(2).lower()[:3], m.group(3)
        h_s, min_s, sec_s = m.group(4), m.group(5), m.group(6)
        month = _MONTH_NAMES.get(month_s)
        if month is None:
            continue
        try:
            day = int(day_s)
            year = int(year_s)
            h, mn, sec = int(h_s), int(min_s), int(sec_s)
            if 1 <= day <= 31 and 1 <= month <= 12 and 0 <= h <= 23 and 0 <= mn <= 59 and 0 <= sec <= 59:
                return f"{day:02d}/{month:02d}/{year} {h:02d}:{mn:02d}:{sec:02d}"
        except ValueError:
            continue
    return None


def parse_receipt_image(image_bytes: bytes) -> str | None:
    """Extract text from receipt image with EasyOCR and parse date (e.g. 03 MAR 2026 - 18:40:12). Returns 'DD/MM/YYYY HH:MM:SS' or None."""
    text = receipt_text_extractor(image_bytes)
    return parse_receipt_date_from_text(text)
