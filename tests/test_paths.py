"""Tests for stored path resolution."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

import pjtracker.app as app_module
from pjtracker.api.services.paths import resolve_stored_path


@contextmanager
def temporary_app_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        original_db_path = app_module.DB_PATH
        original_pdf_dir = app_module.PDF_DIR
        original_images_dir = app_module.IMAGES_DIR
        app_module.DB_PATH = root / "pjtracker.db"
        app_module.PDF_DIR = root / "pdfs"
        app_module.IMAGES_DIR = root / "images"
        app_module.PDF_DIR.mkdir(parents=True)
        app_module.IMAGES_DIR.mkdir(parents=True)
        try:
            yield root
        finally:
            app_module.DB_PATH = original_db_path
            app_module.PDF_DIR = original_pdf_dir
            app_module.IMAGES_DIR = original_images_dir


def test_resolve_stored_path_relative_pdf():
    with temporary_app_paths() as root:
        pdf = root / "pdfs" / "nf_test.pdf"
        pdf.write_bytes(b"%PDF")
        resolved = resolve_stored_path("pdfs/nf_test.pdf")
        assert resolved is not None
        assert resolved.is_file()
        assert resolved.resolve() == pdf.resolve()


def test_resolve_stored_path_stale_absolute_pdf():
    with temporary_app_paths() as root:
        pdf = root / "pdfs" / "nf_stale.pdf"
        pdf.write_bytes(b"%PDF")
        resolved = resolve_stored_path("/other/host/pjtracker/pdfs/nf_stale.pdf")
        assert resolved is not None
        assert resolved.is_file()
        assert resolved.resolve() == pdf.resolve()


def test_resolve_stored_path_stale_absolute_image():
    with temporary_app_paths() as root:
        img = root / "images" / "nf_1.png"
        img.write_bytes(b"\x89PNG")
        resolved = resolve_stored_path("/other/host/pjtracker/images/nf_1.png")
        assert resolved is not None
        assert resolved.is_file()
        assert resolved.resolve() == img.resolve()
