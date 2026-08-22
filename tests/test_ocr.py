from unittest.mock import patch

import easyocr.easyocr as easyocr_impl

from pjtracker.parsers.ocr import (
    get_easyocr_reader,
    image_to_text,
    pdf_to_text,
    reset_easyocr_reader,
)


def setup_function() -> None:
    reset_easyocr_reader()


def teardown_function() -> None:
    reset_easyocr_reader()


def test_easyocr_corrupt_msg_is_defined_on_module() -> None:
    assert easyocr_impl.corrupt_msg == "MD5 hash mismatch, possible file corruption"


def test_image_to_text_returns_empty_when_reader_raises_corrupt_msg() -> None:
    with patch(
        "pjtracker.parsers.ocr.easyocr.Reader",
        side_effect=NameError("name 'corrupt_msg' is not defined"),
    ):
        assert image_to_text(b"not-an-image") == ""


def test_pdf_to_text_returns_empty_when_reader_raises_corrupt_msg() -> None:
    with patch(
        "pjtracker.parsers.ocr.easyocr.Reader",
        side_effect=NameError("name 'corrupt_msg' is not defined"),
    ):
        assert pdf_to_text(b"%PDF-1.4") == ""


def test_failed_reader_init_is_cached() -> None:
    with patch(
        "pjtracker.parsers.ocr.easyocr.Reader",
        side_effect=NameError("name 'corrupt_msg' is not defined"),
    ) as reader_mock:
        assert get_easyocr_reader() is None
        assert get_easyocr_reader() is None
        reader_mock.assert_called_once()
