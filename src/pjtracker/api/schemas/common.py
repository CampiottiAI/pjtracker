"""Shared request/response models."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

FISCAL_MES_REGEX = re.compile(r"^\d{4}-\d{2}$")
DATE_OR_DATETIME_BR_REGEX = re.compile(r"^\d{2}/\d{2}/\d{4}(?: \d{2}:\d{2}:\d{2})?$")


class PatchFiscalMes(BaseModel):
    fiscal_mes: str | None = Field(
        default=None,
        description="YYYY-MM or null to clear",
    )

    @field_validator("fiscal_mes", mode="before")
    @classmethod
    def normalize_fiscal_mes(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        s = str(value).strip()
        if not FISCAL_MES_REGEX.match(s):
            raise ValueError("fiscal_mes must be YYYY-MM")
        return s


class CreateFiscalMonthRequest(BaseModel):
    fiscal_mes: str = Field(description="YYYY-MM")

    @field_validator("fiscal_mes", mode="before")
    @classmethod
    def normalize_fiscal_mes(cls, value: str) -> str:
        s = str(value).strip()
        if not FISCAL_MES_REGEX.match(s):
            raise ValueError("fiscal_mes must be YYYY-MM")
        return s


class FiscalMonthResponse(BaseModel):
    fiscal_mes: str
    created: bool


class PatchBoletoLikeFields(BaseModel):
    value: float | None = Field(default=None)
    emission_date: str | None = Field(default=None)
    deadline_date: str | None = Field(default=None)
    codigo_barras: str | None = Field(default=None)
    codigo_barras_digits: str | None = Field(default=None)
    receipt_date: str | None = Field(default=None)
    receipt_value: float | None = Field(default=None)
    receipt_codigo_barras: str | None = Field(default=None)
    receipt_codigo_barras_digits: str | None = Field(default=None)
    fiscal_mes: str | None = Field(default=None)

    @field_validator(
        "emission_date",
        "deadline_date",
        "receipt_date",
        mode="before",
    )
    @classmethod
    def normalize_date_or_datetime_br(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        s = str(value).strip()
        if not DATE_OR_DATETIME_BR_REGEX.match(s):
            raise ValueError("date fields must be DD/MM/YYYY or DD/MM/YYYY HH:MM:SS")
        return s

    @field_validator(
        "codigo_barras_digits",
        "receipt_codigo_barras_digits",
        mode="before",
    )
    @classmethod
    def normalize_digit_barcodes(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        s = str(value).strip()
        if not s.isdigit():
            raise ValueError("barcode digit fields must contain only digits")
        return s

    @field_validator(
        "codigo_barras",
        "receipt_codigo_barras",
        mode="before",
    )
    @classmethod
    def normalize_text_barcodes(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return str(value).strip()

    @field_validator("fiscal_mes", mode="before")
    @classmethod
    def normalize_fiscal_mes(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        s = str(value).strip()
        if not FISCAL_MES_REGEX.match(s):
            raise ValueError("fiscal_mes must be YYYY-MM")
        return s
