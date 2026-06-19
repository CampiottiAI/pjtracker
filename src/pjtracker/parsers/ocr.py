"""Shared EasyOCR helpers with a cached reader and optional disable flag."""

from __future__ import annotations

import os
from functools import lru_cache
from io import BytesIO

import easyocr
import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image


def ocr_enabled() -> bool:
    """Return False when PJTRACKER_OCR is 0, false, or disabled."""
    value = os.getenv("PJTRACKER_OCR", "1").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


@lru_cache(maxsize=1)
def get_easyocr_reader() -> easyocr.Reader:
    return easyocr.Reader(["pt"])


def pdf_to_text(pdf_bytes: bytes) -> str:
    """OCR all pages of a PDF and return concatenated text."""
    ocr = get_easyocr_reader()
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


def image_to_text(image_bytes: bytes, *, crop_top_third: bool = False) -> str:
    """OCR an image and return extracted text."""
    ocr = get_easyocr_reader()
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
