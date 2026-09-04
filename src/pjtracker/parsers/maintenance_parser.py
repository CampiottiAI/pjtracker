"""Car maintenance quote extraction helpers."""

from __future__ import annotations

from typing import Any

from pjtracker.casa.cars_storage import Car
from pjtracker.llm_extraction import (
    LLMExtractionResult,
    analyze_maintenance,
    extract_quote,
)


def parse_quote(
    file_bytes: bytes,
    *,
    filename: str = "orcamento.pdf",
    mime_type: str = "application/pdf",
) -> LLMExtractionResult:
    return extract_quote(file_bytes, filename=filename, mime_type=mime_type)


def apply_car_defaults(extracted: dict[str, Any], car: Car) -> dict[str, Any]:
    """Pre-fill vehicle fields from the selected car when missing in extraction."""
    out = dict(extracted)
    veiculo = dict(out.get("veiculo") or {})
    if car.get("placa") and not veiculo.get("placa"):
        veiculo["placa"] = car["placa"]
    if car.get("modelo") and not veiculo.get("modelo"):
        veiculo["modelo"] = car["modelo"]
    out["veiculo"] = veiculo
    return out


def analyze_quote(
    current: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> LLMExtractionResult:
    return analyze_maintenance(current, previous)
