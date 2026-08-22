"""Shared EasyOCR helpers with a cached reader and optional disable flag."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from io import BytesIO

import easyocr
import easyocr.easyocr as easyocr_impl
import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

logger = logging.getLogger(__name__)

# EasyOCR 1.7.2 references `corrupt_msg` in Reader.__init__ without defining it
# when a cached recognition model fails the MD5 check (JaidedAI/EasyOCR#1119).
# Setting it on the module lets EasyOCR warn, delete the stale file, and re-download.
if getattr(easyocr_impl, "corrupt_msg", None) is None:
    easyocr_impl.corrupt_msg = "MD5 hash mismatch, possible file corruption"


def ocr_enabled() -> bool:
    """Return False when PJTRACKER_OCR is 0, false, or disabled."""
    value = os.getenv("PJTRACKER_OCR", "1").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


@lru_cache(maxsize=1)
def get_easyocr_reader() -> easyocr.Reader | None:
    """Return a cached EasyOCR reader, or None if initialization failed."""
    try:
        return easyocr.Reader(["pt"], verbose=False)
    except Exception:
        logger.exception("EasyOCR failed to initialize; OCR fallback disabled")
        return None


def reset_easyocr_reader() -> None:
    """Drop the cached reader (mainly for tests)."""
    get_easyocr_reader.cache_clear()


def pdf_to_text(pdf_bytes: bytes) -> str:
    """OCR all pages of a PDF and return concatenated text."""
    try:
        ocr = get_easyocr_reader()
        if ocr is None:
            return ""
        pages = convert_from_bytes(pdf_bytes)
        full_text = ""
        for page in pages:
            image = np.array(page)
            lines = ocr.readtext(
                image,
                detail=0,
                canvas_size=1280,
                mag_ratio=1,
                batch_size=1,
            )
            text = " ".join(lines)
            full_text += f"\n\n {text}"
        return full_text
    except Exception:
        logger.exception("PDF OCR failed")
        return ""


def image_to_text(image_bytes: bytes, *, crop_top_third: bool = False) -> str:
    """OCR an image and return extracted text."""
    try:
        ocr = get_easyocr_reader()
        if ocr is None:
            return ""
        img = Image.open(BytesIO(image_bytes))
        if crop_top_third:
            width, height = img.size
            img = img.crop((0, 0, width, height // 3))
        if img.mode != "RGB":
            img = img.convert("RGB")
        arr = np.array(img)
        lines = ocr.readtext(
            arr,
            detail=0,
            canvas_size=1280,
            mag_ratio=1,
            batch_size=1,
        )
        return " ".join(lines)
    except Exception:
        logger.exception("Image OCR failed")
        return ""
