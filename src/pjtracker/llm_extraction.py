"""Shared Sabia/Maritaca extraction helpers and normalization utilities."""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = os.getenv("MARITACA_MODEL", "sabiazinho-4")
DEFAULT_BASE_URL = os.getenv("MARITACA_BASE_URL", "https://chat.maritaca.ai/api")
TOKEN_PATH = PROJECT_ROOT / ".token"


class BoletoPdfExtraido(BaseModel):
    valor: float | None = Field(
        default=None,
        description="Valor do boleto em reais.",
    )
    data_emissao: str | None = Field(
        default=None,
        description=(
            "Data de emissao, processamento ou documento no formato DD/MM/YYYY."
        ),
    )
    data_vencimento: str | None = Field(
        default=None,
        description="Data de vencimento no formato DD/MM/YYYY.",
    )
    codigo_barras: str | None = Field(
        default=None,
        description="Codigo de barras do boleto exatamente como estiver visivel.",
    )


class ComprovanteExtraido(BaseModel):
    valor: float | None = Field(
        default=None,
        description="Valor pago em reais.",
    )
    data_pagamento: str | None = Field(
        default=None,
        description=(
            "Data e hora do pagamento no formato DD/MM/YYYY HH:MM:SS ou DD/MM/YYYY - HH:MM:SS."
        ),
    )
    codigo_barras: str | None = Field(
        default=None,
        description=(
            "Codigo de barras do documento pago exatamente como estiver visivel."
        ),
    )


class DarfPdfExtraido(BaseModel):
    valor: float | None = Field(
        default=None,
        description="Valor total do DARF em reais.",
    )
    periodo_apuracao: str | None = Field(
        default=None,
        description="Periodo de apuracao do DARF no formato MM/YYYY.",
    )
    data_vencimento: str | None = Field(
        default=None,
        description="Data de vencimento do DARF no formato DD/MM/YYYY.",
    )
    codigo_barras: str | None = Field(
        default=None,
        description="Codigo de barras do DARF exatamente como estiver visivel.",
    )


class NfPdfExtraida(BaseModel):
    empresa: str | None = Field(
        default=None,
        description="Nome da empresa para qual o serviço foi prestado, não o nome da empresa emissora da nota fiscal",
    )
    valor_usd: float | None = Field(
        default=None,
        description="Valor em dolar americano.",
    )
    cotacao: float | None = Field(
        default=None,
        description="Cotacao usada na nota fiscal.",
    )
    spread: float | None = Field(
        default=None,
        description="Spread informado na nota fiscal.",
    )
    data_emissao: str | None = Field(
        default=None,
        description="Data e hora da nota fiscal no formato DD/MM/YYYY HH:MM:SS.",
    )
    codigo_verificacao: str | None = Field(
        default=None,
        description="Codigo de verificacao da nota fiscal.",
    )
    pagamento_via: str | None = Field(
        default=None,
        description="Nome da plataforma de pagamento, como Wise ou Higlobe.",
    )


class ExtratoEntryExtraida(BaseModel):
    data: str = Field(description="Data da transacao no formato DD/MM/YYYY.")
    nome: str = Field(description="Nome resumido da transacao.")
    descricao: str = Field(description="Descricao complementar da transacao.")
    valor: float = Field(description="Valor da transacao em reais.")
    tipo: Literal["entrada", "saida"] = Field(
        description="Tipo da transacao: entrada ou saida."
    )


class ExtratoPdfExtraido(BaseModel):
    entries: list[ExtratoEntryExtraida] = Field(
        description="Lista de transacoes presentes no extrato."
    )
    saldo_inicial: float | None = Field(
        default=None,
        description="Saldo inicial do periodo em reais.",
    )
    rendimento: float | None = Field(
        default=None,
        description="Rendimento liquido do periodo em reais.",
    )
    total_entradas: float | None = Field(
        default=None,
        description="Total de entradas do periodo em reais.",
    )
    total_saidas: float | None = Field(
        default=None,
        description="Total de saidas do periodo em reais.",
    )
    saldo_final: float | None = Field(
        default=None,
        description="Saldo final do periodo em reais.",
    )


class CaixinhaEntryExtraida(BaseModel):
    data: str = Field(description="Data da movimentacao no formato DD/MM/YYYY.")
    movimentacao: str = Field(description="Descricao da movimentacao da caixinha.")
    rendimento: float | None = Field(
        default=None,
        description="Rendimento da movimentacao em reais.",
    )
    valor_bruto: float | None = Field(
        default=None,
        description="Valor bruto da movimentacao em reais.",
    )
    imposto: float | None = Field(
        default=None,
        description="Imposto da movimentacao em reais.",
    )
    iof: float | None = Field(
        default=None,
        description="IOF da movimentacao em reais.",
    )
    valor_liquido: float | None = Field(
        default=None,
        description="Valor liquido da movimentacao em reais.",
    )


class CaixinhaPdfExtraido(BaseModel):
    entries: list[CaixinhaEntryExtraida] = Field(
        description="Lista de movimentacoes presentes no extrato de caixinha."
    )
    saldo_final: float | None = Field(
        default=None,
        description="Saldo final do periodo em reais.",
    )


class HiglobeTransaction(BaseModel):
    date: str = Field(
        description=(
            "Date and time exactly as shown in the PDF, preferably in the format "
            "DD/MM/YYYY - HH:MM."
        )
    )
    type: str = Field(
        description=(
            "Transaction type or status exactly as shown, such as Confirmed, "
            "Processing, Incoming Funds, Withdrawals or ACH."
        )
    )
    description: str = Field(
        description="Short transaction description exactly as shown in the PDF."
    )
    amount: float = Field(
        description="Transaction amount as a positive number, without currency symbols."
    )
    currency: str = Field(
        description="Currency code for the transaction, such as USD."
    )


class HiglobeTransactions(BaseModel):
    entries: list[HiglobeTransaction] = Field(
        description="List of transactions extracted from the Higlobe PDF."
    )


@dataclass
class LLMExtractionResult:
    data: BaseModel | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None


def normalize_digits(value: str | None) -> str | None:
    """Keep only digits from a barcode-like value."""
    if not value:
        return None
    digits = re.sub(r"\D+", "", value)
    return digits or None


def normalize_dd_mm_yyyy(value: str | None) -> str | None:
    """Normalize dates to DD/MM/YYYY when possible."""
    if not value:
        return None
    cleaned = value.strip().replace("-", "/").replace(".", "/")
    cleaned = re.sub(r"\s+", "", cleaned)
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return None


def normalize_mm_yyyy(value: str | None) -> str | None:
    """Normalize periods to MM/YYYY when possible."""
    if not value:
        return None
    cleaned = value.strip()
    match = re.search(r"(\d{1,2})\D+(\d{4})", cleaned)
    if not match:
        return None
    month = int(match.group(1))
    year = int(match.group(2))
    if 1 <= month <= 12:
        return f"{month:02d}/{year}"
    return None


def normalize_payment_datetime(value: str | None) -> str | None:
    """Normalize payment datetimes to DD/MM/YYYY HH:MM:SS."""
    if not value:
        return None
    cleaned = value.strip()
    cleaned = re.sub(r"\s*-\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    for fmt in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ):
        try:
            dt = datetime.strptime(cleaned, fmt)
            if fmt.endswith("%H:%M"):
                return dt.strftime("%d/%m/%Y %H:%M:00")
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            continue
    return None


def normalize_payment_via(value: str | None) -> str | None:
    """Normalize payment platform names from LLM output."""
    if not value:
        return None
    cleaned = value.strip().lower()
    if cleaned == "wise":
        return "Wise"
    if cleaned == "higlobe":
        return "Higlobe"
    return value.strip()


def _read_api_key() -> str | None:
    env_key = os.getenv("MARITACA_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text().strip()
        return token or None
    return None


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    api_key = _read_api_key()
    if not api_key:
        raise RuntimeError("API key da Maritaca nao configurada.")
    return OpenAI(api_key=api_key, base_url=DEFAULT_BASE_URL)


def _encode_file_data(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


def _extract_structured_data(
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
) -> LLMExtractionResult:
    try:
        client = _get_client()
    except Exception as exc:
        return LLMExtractionResult(data=None, error=str(exc))

    try:
        response = client.responses.parse(
            model=DEFAULT_MODEL,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "file": {
                                "filename": filename,
                                "file_data": (
                                    f"data:{mime_type};base64,{_encode_file_data(file_bytes)}"
                                ),
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                },
            ],
            text_format=schema,
        )
    except Exception as exc:
        return LLMExtractionResult(data=None, error=str(exc))

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        return LLMExtractionResult(
            data=None,
            error="A resposta do modelo nao retornou saida estruturada.",
        )
    return LLMExtractionResult(data=parsed)


def extract_boleto_pdf(
    file_bytes: bytes, filename: str = "boleto.pdf"
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type="application/pdf",
        system_prompt=(
            "Voce e um sistema de extracao de dados de boletos bancarios. "
            "Seja preciso e objetivo."
        ),
        user_prompt=(
            "Extraia os dados do boleto no formato JSON. "
            "Preciso saber o valor, a data de emissao, a data de vencimento "
            "e o codigo de barras."
        ),
        schema=BoletoPdfExtraido,
    )


def extract_boleto_receipt(
    file_bytes: bytes,
    filename: str = "comprovante.png",
    mime_type: str = "image/png",
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type,
        system_prompt=(
            "Voce e um sistema de extracao de dados de comprovantes de pagamento. "
            "Seja preciso e objetivo."
        ),
        user_prompt=(
            "Extraia os dados do comprovante no formato JSON. "
            "Preciso saber o valor, a data de pagamento e o codigo de barras "
            "do documento pago."
        ),
        schema=ComprovanteExtraido,
    )


def extract_darf_pdf(
    file_bytes: bytes, filename: str = "darf.pdf"
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type="application/pdf",
        system_prompt=(
            "Voce e um sistema de extracao de dados de DARF. Seja preciso e objetivo."
        ),
        user_prompt=(
            "Extraia os dados do DARF no formato JSON. "
            "Preciso saber o valor, o periodo de apuracao, a data de vencimento "
            "e o codigo de barras."
        ),
        schema=DarfPdfExtraido,
    )


def extract_darf_receipt(
    file_bytes: bytes,
    filename: str = "comprovante.png",
    mime_type: str = "image/png",
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type,
        system_prompt=(
            "Voce e um sistema de extracao de dados de comprovantes de pagamento de DARF. "
            "Seja preciso e objetivo."
        ),
        user_prompt=(
            "Extraia os dados do comprovante no formato JSON. "
            "Preciso saber o valor, a data de pagamento e o codigo de barras "
            "do DARF pago."
        ),
        schema=ComprovanteExtraido,
    )


def extract_extrato_pdf(
    file_bytes: bytes,
    filename: str = "extrato.pdf",
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type="application/pdf",
        system_prompt=(
            "Voce e um sistema de extracao de dados de extratos bancarios. "
            "Seja preciso e objetivo."
        ),
        user_prompt=(
            "Extraia os dados do extrato no formato JSON. "
            "Preciso da lista de transacoes com data, nome, descricao, valor e tipo, "
            "alem de saldo inicial, rendimento, total de entradas, total de saidas "
            "e saldo final."
        ),
        schema=ExtratoPdfExtraido,
    )


def extract_caixinha_pdf(
    file_bytes: bytes,
    filename: str = "caixinha.pdf",
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type="application/pdf",
        system_prompt=(
            "Voce e um sistema de extracao de dados de extratos bancarios de caixinha. "
            "Seja preciso e objetivo."
        ),
        user_prompt=(
            "Extraia os dados do extrato da caixinha no formato JSON. "
            "Preciso da lista de movimentacoes com data, movimentacao, rendimento, "
            "valor bruto, imposto, iof e valor liquido, alem do saldo final do periodo."
        ),
        schema=CaixinhaPdfExtraido,
    )


def extract_higlobe_transactions_pdf(
    file_bytes: bytes,
    filename: str = "statement.pdf",
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type="application/pdf",
        system_prompt=(
            "You extract structured transaction data from Higlobe PDF statements "
            "and transaction receipts. Be precise and objective."
        ),
        user_prompt=(
            "Extract every transaction row from the PDF into JSON. "
            "Return a list of entries with date, type, description, amount and currency. "
            "Use the values exactly as shown in the document whenever possible. "
            "Amount must be numeric and should not include currency symbols."
        ),
        schema=HiglobeTransactions,
    )


def extract_nf_pdf(
    file_bytes: bytes, filename: str = "nota_fiscal.pdf"
) -> LLMExtractionResult:
    return _extract_structured_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type="application/pdf",
        system_prompt=(
            "Voce e um sistema de extracao de dados de nota fiscal de servicos. "
            "Seja preciso e objetivo."
        ),
        user_prompt=(
            "Extraia os dados da nota fiscal no formato JSON. "
            "Preciso saber a empresa, o valor em USD, a cotacao, o spread, "
            "a data de emissao, o codigo de verificacao e o pagamento via."
        ),
        schema=NfPdfExtraida,
    )
