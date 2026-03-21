"""FastAPI app — run with: uv run uvicorn src.api.main:app --reload"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.app import init_db

from .routers import (
    analytics,
    boletos,
    darfs,
    extratos,
    fiscal_months,
    health,
    nfs,
    receipts,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="pjtracker API",
    lifespan=lifespan,
)

api_prefix = "/api/v1"

app.include_router(health.router, prefix=api_prefix)
app.include_router(receipts.router, prefix=api_prefix)
app.include_router(nfs.router, prefix=api_prefix)
app.include_router(boletos.router, prefix=api_prefix)
app.include_router(darfs.router, prefix=api_prefix)
app.include_router(extratos.router, prefix=api_prefix)
app.include_router(fiscal_months.router, prefix=api_prefix)
app.include_router(analytics.router, prefix=api_prefix)
