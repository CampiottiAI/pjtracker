"""Structured HTTP errors for API routes."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def conflict(code: str, detail: str, **extra: Any) -> HTTPException:
    body: dict[str, Any] = {"detail": detail, "code": code}
    for k, v in extra.items():
        if v is not None:
            body[k] = v
    return HTTPException(status_code=409, detail=body)
