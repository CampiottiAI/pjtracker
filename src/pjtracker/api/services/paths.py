"""Resolve stored file paths relative to project root."""

from __future__ import annotations

from pathlib import Path

import pjtracker.app as app

_STORAGE_SUBDIRS = ("pdfs", "images")


def project_root() -> Path:
    return app.PROJECT_ROOT.resolve()


def _storage_dir(subdir: str) -> Path:
    if subdir == "pdfs":
        return app.PDF_DIR.resolve()
    if subdir == "images":
        return app.IMAGES_DIR.resolve()
    return project_root() / subdir


def resolve_stored_path(raw: str | None) -> Path | None:
    if not raw or not str(raw).strip():
        return None
    p = Path(raw)
    root = project_root()
    candidates: list[Path] = [p] if p.is_absolute() else [root / p]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    # Stale absolute paths from another host: remap pdfs/... or images/... to configured dirs.
    for subdir in _STORAGE_SUBDIRS:
        try:
            idx = p.parts.index(subdir)
            suffix_parts = p.parts[idx + 1 :]
            remapped = _storage_dir(subdir).joinpath(*suffix_parts) if suffix_parts else _storage_dir(subdir)
            if remapped not in candidates:
                candidates.append(remapped)
            if remapped.is_file():
                return remapped
        except ValueError:
            continue

    # Last resort: filename only in known storage dirs.
    name = p.name
    if name:
        for subdir in _STORAGE_SUBDIRS:
            fallback = _storage_dir(subdir) / name
            if fallback.is_file():
                return fallback

    return candidates[0]
