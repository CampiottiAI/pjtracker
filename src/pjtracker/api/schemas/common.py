"""Shared request/response models."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

FISCAL_MES_REGEX = re.compile(r"^\d{4}-\d{2}$")


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
