"""Liveness and readiness."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter

from src.app import DB_PATH
from src.llm_extraction import TOKEN_PATH, _read_api_key

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, bool | str]:
    db_ok = False
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except (OSError, sqlite3.OperationalError):
        pass
    try:
        llm_configured = _read_api_key() is not None
    except OSError:
        llm_configured = False
    ok = db_ok
    return {
        "ready": ok,
        "database": db_ok,
        "llm_key_configured": llm_configured,
        "token_file_exists": TOKEN_PATH.exists(),
    }
