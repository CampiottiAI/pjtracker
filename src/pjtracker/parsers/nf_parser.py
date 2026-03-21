"""Nota Fiscal parser: PDF text extraction, description block parsing, BRL computation, validation."""

import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

from pjtracker.llm_extraction import (
    extract_nf_pdf,
    normalize_payment_datetime,
    normalize_payment_via,
)

# Markers for the service description block
START_MARKER = (
    "DESCRIÇÃO DO SERVIÇO PRESTADO (EM ACORDO COM A CNAE/CBO IDENTIFICADA NO CAMPO SERVIÇO "
    "PRESTADO, ESPECIFICANDO A QUANTIDADE E O PREÇO UNITÁRIO)"
)
END_MARKER = "TRIBUTAÇÃO MUNICIPAL"
# Anchors for PDF-extracted text: "Código de Verificação" is always present, next line is the code (varies), then description until "RETENÇÕES"
CODIGO_VERIFICACAO_LABEL = "Código de Verificação"
RETENCOES_MARKER = "RETENÇÕES"
VALOR_LIQUIDO_LABEL = "Valor Líquido da NFSe Campinas (R$)"
DEFAULT_SPREAD = 3.0
DEFAULT_TOLERANCE_BRL = 0.01
DEFAULT_TOLERANCE_PERCENT = 0.001


@dataclass
class ParsedFields:
    """Extracted fields from the description block."""

    company: str | None
    usd: float | None
    rate: float | None
    spread: float  # always set (default 3 if not found)
    spread_was_default: bool


@dataclass
class BRLResult:
    """BRL amounts with and without spread."""

    brl_no_spread: float
    brl_with_spread: float


@dataclass
class NFParsed:
    """Normalized NF fields used by the app."""

    company: str | None
    usd: float | None
    rate: float | None
    spread: float
    spread_was_default: bool
    nf_date: str | None
    verification_code: str | None
    payment_via: str | None
    source: str = "fallback"


def _normalize_br_number(s: str) -> float:
    """Parse Brazilian or US number: 1.234,56 or 1,234.56 or 4,779.17."""
    s = s.strip().replace(" ", "")
    if "," in s and "." in s:
        # Last occurrence is decimal separator: 4,779.17 -> US; 25.734,42 -> BR
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_dot > last_comma:
            # US: comma = thousands
            s = s.replace(",", "")
        else:
            # BR: dot = thousands, comma = decimal
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # only comma: 4,779 (US thousands) or 4779,17 (BR decimal)
        if re.match(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$", s):
            s = s.replace(",", "")  # US
        else:
            s = s.replace(",", ".")  # BR decimal
    return float(s)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract full text from a PDF. Returns empty string on failure."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


# Date format in NFSe PDF: DD/MM/YYYY HH:MM:SS
DATE_PATTERN = re.compile(r"\b(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\b")


def get_date_from_pdf(full_text: str) -> str | None:
    """Return the first date/time string in format DD/MM/YYYY HH:MM:SS found in the PDF text."""
    if not full_text:
        return None
    match = DATE_PATTERN.search(full_text)
    return match.group(1) if match else None


PAYMENT_VIA_PATTERN = re.compile(
    r"Pagamento via\s+(\w+)",
    re.IGNORECASE,
)


def get_payment_via(full_text: str) -> str | None:
    """Search for 'Pagamento via X' in the PDF text; return 'Higlobe' or 'Wise' if found, else None."""
    if not full_text:
        return None
    match = PAYMENT_VIA_PATTERN.search(full_text)
    if not match:
        return None
    word = match.group(1).strip()
    if word.lower() == "higlobe":
        return "Higlobe"
    if word.lower() == "wise":
        return "Wise"
    return None


def get_verification_code(full_text: str) -> str | None:
    """Return the verification code: the line immediately after 'Código de Verificação'."""
    if not full_text or CODIGO_VERIFICACAO_LABEL not in full_text:
        return None
    start = full_text.index(CODIGO_VERIFICACAO_LABEL) + len(CODIGO_VERIFICACAO_LABEL)
    rest = full_text[start:].lstrip()
    if not rest:
        return None
    first_line = rest.split("\n", 1)[0].strip()
    return first_line if first_line else None


def _get_description_block_from_verification_section(full_text: str) -> str | None:
    """Return description text between 'Código de Verificação' and 'RETENÇÕES'.
    The line right after 'Código de Verificação' is the verification code (skipped);
    the following lines up to 'RETENÇÕES' form the description block.
    """
    if not full_text or CODIGO_VERIFICACAO_LABEL not in full_text:
        return None
    start_idx = full_text.index(CODIGO_VERIFICACAO_LABEL) + len(
        CODIGO_VERIFICACAO_LABEL
    )
    if RETENCOES_MARKER not in full_text[start_idx:]:
        return None
    end_idx = full_text.index(RETENCOES_MARKER, start_idx)
    section = full_text[start_idx:end_idx].strip()
    if not section:
        return None
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    # First line is the verification code; rest is description + payment line
    return "\n".join(lines[1:])


def get_description_block(full_text: str) -> str | None:
    """Return description block: prefer section between 'Código de Verificação' and 'RETENÇÕES'
    (PDF-extracted order); fall back to text between START_MARKER and END_MARKER."""
    block = _get_description_block_from_verification_section(full_text)
    if block:
        return block
    if not full_text or START_MARKER not in full_text:
        return None
    start_idx = full_text.index(START_MARKER) + len(START_MARKER)
    if END_MARKER not in full_text[start_idx:]:
        return None
    end_idx = full_text.index(END_MARKER, start_idx)
    block = full_text[start_idx:end_idx].strip()
    return block if block else None


def parse_description_block(block_text: str) -> ParsedFields:
    """Parse company, USD, rate, and spread from the description block."""
    company: str | None = None
    usd: float | None = None
    rate: float | None = None
    spread: float = DEFAULT_SPREAD
    spread_was_default = True

    # Company: after "para a empresa" until "," or "localizada"
    company_match = re.search(
        r"para a empresa\s+([^,]+?)(?:\s*,\s*localizada|\s*,)",
        block_text,
        re.IGNORECASE | re.DOTALL,
    )
    if company_match:
        company = company_match.group(1).strip()

    # USD: "Valor em Dólar" then number (allow 4,779.17 or 4779.17); trim trailing punctuation
    usd_match = re.search(
        r"Valor em Dólar\s+([\d.,\s]+)",
        block_text,
        re.IGNORECASE,
    )
    if usd_match:
        raw_usd = re.sub(r"[.\s]+$", "", usd_match.group(1).strip())
        try:
            usd = _normalize_br_number(raw_usd)
        except ValueError:
            usd = None

    # Rate: "Cotação" then number (e.g. 5.2011 or 5,2011)
    rate_match = re.search(
        r"Cotação\s+([\d.,]+)",
        block_text,
        re.IGNORECASE,
    )
    if rate_match:
        try:
            rate = _normalize_br_number(rate_match.group(1))
        except ValueError:
            rate = None

    # Spread: "Spread de X%" (default 3)
    spread_match = re.search(
        r"Spread de\s+([\d.,]+)\s*%",
        block_text,
        re.IGNORECASE,
    )
    if spread_match:
        try:
            spread = float(spread_match.group(1).replace(",", "."))
            spread_was_default = False
        except ValueError:
            pass

    return ParsedFields(
        company=company,
        usd=usd,
        rate=rate,
        spread=spread,
        spread_was_default=spread_was_default,
    )


def compute_brl(usd: float, rate: float, spread: float) -> BRLResult:
    """Compute BRL without and with spread.
    Spread is applied to the rate: e.g. spread 3 means 0.3% deducted from the base rate
    (R$ 5.2011 - 0.30% = R$ 5.1854). So spread value is in tenths of percent."""
    brl_no_spread = round(usd * rate, 2)  # highest: full rate (e.g. 5.2011)
    effective_rate = rate * (1 - spread / 100)  # spread 3 → 0.3% off the rate
    brl_with_spread = round(
        usd * effective_rate, 2
    )  # smaller: rate after spread deduction
    return BRLResult(brl_no_spread=brl_no_spread, brl_with_spread=brl_with_spread)


def _clean_text_field(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_nf_pdf_with_text(pdf_bytes: bytes) -> NFParsed:
    """Fallback NF parsing using the current PDF text logic."""
    full_text = extract_text_from_pdf(pdf_bytes)
    block = get_description_block(full_text) if full_text else None
    parsed = (
        parse_description_block(block)
        if block
        else ParsedFields(
            company=None,
            usd=None,
            rate=None,
            spread=DEFAULT_SPREAD,
            spread_was_default=True,
        )
    )
    return NFParsed(
        company=parsed.company,
        usd=parsed.usd,
        rate=parsed.rate,
        spread=parsed.spread,
        spread_was_default=parsed.spread_was_default,
        nf_date=get_date_from_pdf(full_text),
        verification_code=get_verification_code(full_text),
        payment_via=get_payment_via(full_text),
        source="fallback",
    )


def parse_nf_pdf(pdf_bytes: bytes, filename: str = "nota_fiscal.pdf") -> NFParsed:
    """Extract NF fields using the LLM first and the text parser as fallback."""
    llm_attempt = extract_nf_pdf(pdf_bytes, filename=filename)
    llm_data = llm_attempt.data
    fallback = _parse_nf_pdf_with_text(pdf_bytes)

    llm_company = _clean_text_field(
        getattr(llm_data, "empresa", None) if llm_data else None
    )
    llm_usd = getattr(llm_data, "valor_usd", None) if llm_data else None
    llm_rate = getattr(llm_data, "cotacao", None) if llm_data else None
    llm_spread = getattr(llm_data, "spread", None) if llm_data else None
    llm_nf_date = normalize_payment_datetime(
        getattr(llm_data, "data_emissao", None) if llm_data else None
    )
    llm_verification_code = _clean_text_field(
        getattr(llm_data, "codigo_verificacao", None) if llm_data else None
    )
    llm_payment_via = normalize_payment_via(
        getattr(llm_data, "pagamento_via", None) if llm_data else None
    )

    used_fallback = False

    company = llm_company
    if company is None:
        company = fallback.company
        used_fallback = used_fallback or company is not None

    usd = llm_usd
    if usd is None:
        usd = fallback.usd
        used_fallback = used_fallback or usd is not None

    rate = llm_rate
    if rate is None:
        rate = fallback.rate
        used_fallback = used_fallback or rate is not None

    if llm_spread is None:
        spread = fallback.spread
        spread_was_default = fallback.spread_was_default
        used_fallback = True
    else:
        spread = llm_spread
        spread_was_default = False

    nf_date = llm_nf_date
    if nf_date is None:
        nf_date = fallback.nf_date
        used_fallback = used_fallback or nf_date is not None

    verification_code = llm_verification_code
    if verification_code is None:
        verification_code = fallback.verification_code
        used_fallback = used_fallback or verification_code is not None

    payment_via = llm_payment_via
    if payment_via is None:
        payment_via = fallback.payment_via
        used_fallback = used_fallback or payment_via is not None

    has_llm_data = any(
        (
            llm_company is not None,
            llm_usd is not None,
            llm_rate is not None,
            llm_spread is not None,
            llm_nf_date is not None,
            llm_verification_code is not None,
            llm_payment_via is not None,
        )
    )
    source = "fallback"
    if has_llm_data and used_fallback:
        source = "merged"
    elif has_llm_data:
        source = "llm"

    return NFParsed(
        company=company,
        usd=usd,
        rate=rate,
        spread=spread,
        spread_was_default=spread_was_default,
        nf_date=nf_date,
        verification_code=verification_code,
        payment_via=payment_via,
        source=source,
    )
