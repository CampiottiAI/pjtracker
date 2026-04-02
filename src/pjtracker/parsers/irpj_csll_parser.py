"""IRPJ/CSLL parsing reuses the DARF extraction flow."""

from pjtracker.parsers.darf_parser import DarfParsed, parse_darf_pdf


def parse_irpj_csll_pdf(pdf_bytes: bytes, filename: str = "irpj_csll.pdf") -> DarfParsed:
    """Parse IRPJ/CSLL PDFs using the same extraction pipeline as DARF."""
    return parse_darf_pdf(pdf_bytes, filename=filename)
