"""Resolve stored file paths relative to project root."""

from __future__ import annotations

from pathlib import Path

from pjtracker.app import PROJECT_ROOT


def project_root() -> Path:
    return PROJECT_ROOT.resolve()


def resolve_stored_path(raw: str | None) -> Path | None:
    if not raw or not str(raw).strip():
        return None
    p = Path(raw)
    if p.is_absolute():
        return p
    return project_root() / raw
