"""NF calculation overrides."""

from pydantic import BaseModel, Field


class PatchNfSpread(BaseModel):
    spread: float = Field(ge=0, le=100, allow_inf_nan=False)
