import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pjtracker.app as app
from pjtracker.parsers.boleto_parser import BoletoParsed, ReceiptParsed, parse_boleto_pdf, parse_receipt_image
from pjtracker.parsers.darf_parser import DarfParsed, parse_darf_pdf
from pjtracker.parsers.ocr import reset_easyocr_reader
from pjtracker.parsers.parse_cache import clear_parse_cache
from pjtracker.llm_extraction import (
    BoletoPdfExtraido,
    ComprovanteExtraido,
    DarfPdfExtraido,
    LLMExtractionResult,
    normalize_digits,
)
from pjtracker.parsers.nf_parser import NFParsed, parse_nf_pdf


@contextmanager
def temporary_app_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        original_db_path = app.DB_PATH
        original_pdf_dir = app.PDF_DIR
        original_images_dir = app.IMAGES_DIR
        app.DB_PATH = root / "pjtracker.db"
        app.PDF_DIR = root / "pdfs"
        app.IMAGES_DIR = root / "images"
        try:
            yield root
        finally:
            app.DB_PATH = original_db_path
            app.PDF_DIR = original_pdf_dir
            app.IMAGES_DIR = original_images_dir


class RefactorTests(unittest.TestCase):
    def setUp(self):
        clear_parse_cache()
        reset_easyocr_reader()

    def test_normalize_digits_strips_everything_but_numbers(self):
        self.assertEqual(
            normalize_digits("75691.32074 01232.820801 00018.620013 2 13810000056735"),
            "75691320740123282080100018620013213810000056735",
        )
        self.assertEqual(normalize_digits("abc-123.45"), "12345")
        self.assertIsNone(normalize_digits("abc"))

    def test_boleto_parser_merges_llm_and_fallback_fields(self):
        llm_result = LLMExtractionResult(
            data=BoletoPdfExtraido(
                valor=567.35,
                data_emissao=None,
                data_vencimento="10/03/2026",
                codigo_barras="75691.32074 01232.820801 00018.620013 2 13810000056735",
            )
        )
        fallback = BoletoParsed(
            value=567.35,
            emission_date="27/02/2026",
            deadline_date="10/03/2026",
        )

        with (
            patch("pjtracker.parsers.boleto_parser.extract_boleto_pdf", return_value=llm_result),
            patch("pjtracker.parsers.boleto_parser._parse_boleto_pdf_with_ocr", return_value=fallback),
        ):
            parsed = parse_boleto_pdf(b"fake-pdf")

        self.assertEqual(parsed.value, 567.35)
        self.assertEqual(parsed.emission_date, "27/02/2026")
        self.assertEqual(parsed.deadline_date, "10/03/2026")
        self.assertEqual(
            parsed.codigo_barras_digits,
            "75691320740123282080100018620013213810000056735",
        )
        self.assertEqual(parsed.source, "merged")

    def test_boleto_parser_runs_ocr_when_llm_missing_field(self):
        llm_result = LLMExtractionResult(
            data=BoletoPdfExtraido(
                valor=567.35,
                data_emissao=None,
                data_vencimento="10/03/2026",
                codigo_barras=None,
            )
        )
        fallback = BoletoParsed(
            value=567.35,
            emission_date="27/02/2026",
            deadline_date="10/03/2026",
        )

        with (
            patch("pjtracker.parsers.boleto_parser.extract_boleto_pdf", return_value=llm_result),
            patch(
                "pjtracker.parsers.boleto_parser._parse_boleto_pdf_with_ocr",
                return_value=fallback,
            ) as ocr_mock,
        ):
            parse_boleto_pdf(b"fake-pdf")

        ocr_mock.assert_called_once()

    def test_darf_parser_skips_ocr_when_llm_complete(self):
        llm_result = LLMExtractionResult(
            data=DarfPdfExtraido(
                valor=100.0,
                periodo_apuracao="03/2026",
                data_vencimento="31/03/2026",
                codigo_barras="123456789",
            )
        )

        with (
            patch("pjtracker.parsers.darf_parser.extract_darf_pdf", return_value=llm_result),
            patch("pjtracker.parsers.darf_parser._parse_darf_pdf_with_ocr") as ocr_mock,
        ):
            parsed = parse_darf_pdf(b"complete-darf")

        ocr_mock.assert_not_called()
        self.assertEqual(parsed.value, 100.0)
        self.assertEqual(parsed.emission_date, "03/2026")
        self.assertEqual(parsed.deadline_date, "31/03/2026")
        self.assertEqual(parsed.source, "llm")

    def test_parse_cache_returns_same_object_on_second_call(self):
        llm_result = LLMExtractionResult(
            data=DarfPdfExtraido(
                valor=50.0,
                periodo_apuracao="01/2026",
                data_vencimento="15/02/2026",
                codigo_barras=None,
            )
        )

        with patch(
            "pjtracker.parsers.darf_parser.extract_darf_pdf",
            return_value=llm_result,
        ) as extract_mock:
            first = parse_darf_pdf(b"cache-test")
            second = parse_darf_pdf(b"cache-test")

        extract_mock.assert_called_once()
        self.assertIs(first, second)

    @patch.dict(os.environ, {"PJTRACKER_OCR": "0"})
    def test_ocr_disabled_skips_fallback(self):
        llm_result = LLMExtractionResult(data=None, error="sem chave")

        with (
            patch("pjtracker.parsers.darf_parser.extract_darf_pdf", return_value=llm_result),
            patch("pjtracker.parsers.darf_parser._parse_darf_pdf_with_ocr") as ocr_mock,
        ):
            parsed = parse_darf_pdf(b"no-ocr")

        ocr_mock.assert_not_called()
        self.assertIsNone(parsed.value)
        self.assertIsNone(parsed.emission_date)
        self.assertIsNone(parsed.deadline_date)

    def test_receipt_parser_keeps_llm_barcode_and_fallback_datetime(self):
        llm_result = LLMExtractionResult(
            data=ComprovanteExtraido(
                valor=567.35,
                data_pagamento=None,
                codigo_barras="75691320740123282080100018620013213810000056735",
            )
        )

        with (
            patch("pjtracker.parsers.boleto_parser.extract_boleto_receipt", return_value=llm_result),
            patch(
                "pjtracker.parsers.boleto_parser._parse_receipt_datetime_with_ocr",
                return_value="03/03/2026 18:40:12",
            ),
        ):
            parsed = parse_receipt_image(
                b"fake-image",
                filename="comprovante.png",
                mime_type="image/png",
            )

        self.assertEqual(parsed.value, 567.35)
        self.assertEqual(parsed.payment_datetime, "03/03/2026 18:40:12")
        self.assertEqual(
            parsed.codigo_barras_digits,
            "75691320740123282080100018620013213810000056735",
        )
        self.assertEqual(parsed.source, "merged")

    def test_receipt_parser_keeps_llm_fields_when_easyocr_init_fails(self):
        llm_result = LLMExtractionResult(
            data=ComprovanteExtraido(
                valor=567.35,
                data_pagamento=None,
                codigo_barras="75691320740123282080100018620013213810000056735",
            )
        )

        with (
            patch("pjtracker.parsers.boleto_parser.extract_boleto_receipt", return_value=llm_result),
            patch(
                "pjtracker.parsers.ocr.easyocr.Reader",
                side_effect=NameError("name 'corrupt_msg' is not defined"),
            ),
        ):
            parsed = parse_receipt_image(
                b"fake-image",
                filename="comprovante.png",
                mime_type="image/png",
            )

        self.assertEqual(parsed.value, 567.35)
        self.assertIsNone(parsed.payment_datetime)
        self.assertEqual(
            parsed.codigo_barras_digits,
            "75691320740123282080100018620013213810000056735",
        )
        self.assertEqual(parsed.source, "llm")

    def test_darf_parser_uses_fallback_when_llm_returns_nothing(self):
        fallback = DarfParsed(
            value=100.0,
            emission_date="03/2026",
            deadline_date="31/03/2026",
        )
        llm_result = LLMExtractionResult(data=None, error="sem chave")

        with (
            patch("pjtracker.parsers.darf_parser.extract_darf_pdf", return_value=llm_result),
            patch("pjtracker.parsers.darf_parser._parse_darf_pdf_with_ocr", return_value=fallback),
        ):
            parsed = parse_darf_pdf(b"fake-darf")

        self.assertEqual(parsed.value, 100.0)
        self.assertEqual(parsed.emission_date, "03/2026")
        self.assertEqual(parsed.deadline_date, "31/03/2026")
        self.assertEqual(parsed.source, "fallback")

    def test_nf_parser_uses_fallback_when_llm_is_unavailable(self):
        fallback = NFParsed(
            company="ACME LLC",
            usd=1000.0,
            rate=5.2,
            spread=3.0,
            spread_was_default=True,
            nf_date="15/03/2026 10:00:00",
            verification_code="ABC123",
            payment_via="Wise",
            source="fallback",
        )
        llm_result = LLMExtractionResult(data=None, error="sem chave")

        with (
            patch("pjtracker.parsers.nf_parser.extract_nf_pdf", return_value=llm_result),
            patch("pjtracker.parsers.nf_parser._parse_nf_pdf_with_text", return_value=fallback),
        ):
            parsed = parse_nf_pdf(b"fake-nf")

        self.assertEqual(parsed.company, "ACME LLC")
        self.assertEqual(parsed.usd, 1000.0)
        self.assertEqual(parsed.payment_via, "Wise")
        self.assertEqual(parsed.source, "fallback")

    def test_init_db_and_boleto_updates_store_new_barcode_fields(self):
        with temporary_app_paths():
            app.init_db()
            pdf_path = app.save_boleto_pdf(b"%PDF-1.4", emission_date="27/02/2026", value=10.0)
            inserted, boleto_id = app.save_boleto_entry(
                pdf_path=str(pdf_path),
                value=10.0,
                emission_date="27/02/2026",
                deadline_date="10/03/2026",
                codigo_barras="123.456",
                codigo_barras_digits="123456",
            )

            self.assertTrue(inserted)
            self.assertIsNotNone(boleto_id)

            app.update_boleto_receipt(
                boleto_id,
                "images/receipt.png",
                "03/03/2026 18:40:12",
                receipt_value=10.0,
                receipt_codigo_barras="123 456",
                receipt_codigo_barras_digits="123456",
                receipt_match_status="match",
            )

            row = app.get_boleto_by_id(boleto_id)
            self.assertEqual(row["codigo_barras"], "123.456")
            self.assertEqual(row["codigo_barras_digits"], "123456")
            self.assertEqual(row["receipt_codigo_barras"], "123 456")
            self.assertEqual(row["receipt_match_status"], "match")

            with sqlite3.connect(app.DB_PATH) as conn:
                columns = {
                    col[1] for col in conn.execute("PRAGMA table_info(boletos)").fetchall()
                }
            self.assertIn("codigo_barras", columns)
            self.assertIn("receipt_codigo_barras_digits", columns)

    def test_init_db_and_darf_updates_store_new_barcode_fields(self):
        with temporary_app_paths():
            app.init_db()
            pdf_path = app.save_darf_pdf(b"%PDF-1.4", emission_date="03/2026", value=20.0)
            inserted, darf_id = app.save_darf_entry(
                pdf_path=str(pdf_path),
                value=20.0,
                emission_date="03/2026",
                deadline_date="31/03/2026",
                codigo_barras="999.888",
                codigo_barras_digits="999888",
            )

            self.assertTrue(inserted)
            self.assertIsNotNone(darf_id)

            app.update_darf_receipt(
                darf_id,
                "images/darf.png",
                "20/03/2026 12:00:00",
                receipt_value=20.0,
                receipt_codigo_barras="999 888",
                receipt_codigo_barras_digits="999888",
                receipt_match_status="match",
            )

            row = app.get_darf_by_id(darf_id)
            self.assertEqual(row["codigo_barras"], "999.888")
            self.assertEqual(row["codigo_barras_digits"], "999888")
            self.assertEqual(row["receipt_codigo_barras"], "999 888")
            self.assertEqual(row["receipt_match_status"], "match")

    def test_init_db_and_irpj_csll_updates_store_new_barcode_fields(self):
        with temporary_app_paths():
            app.init_db()
            pdf_path = app.save_irpj_csll_pdf(b"%PDF-1.4", emission_date="03/2026", value=30.0)
            inserted, irpj_csll_id = app.save_irpj_csll_entry(
                pdf_path=str(pdf_path),
                value=30.0,
                emission_date="03/2026",
                deadline_date="31/03/2026",
                codigo_barras="321.654",
                codigo_barras_digits="321654",
            )

            self.assertTrue(inserted)
            self.assertIsNotNone(irpj_csll_id)

            app.update_irpj_csll_receipt(
                irpj_csll_id,
                "images/irpj.png",
                "25/03/2026 12:00:00",
                receipt_value=30.0,
                receipt_codigo_barras="321 654",
                receipt_codigo_barras_digits="321654",
                receipt_match_status="match",
            )

            row = app.get_irpj_csll_by_id(irpj_csll_id)
            self.assertEqual(row["codigo_barras"], "321.654")
            self.assertEqual(row["codigo_barras_digits"], "321654")
            self.assertEqual(row["receipt_codigo_barras"], "321 654")
            self.assertEqual(row["receipt_match_status"], "match")

            with sqlite3.connect(app.DB_PATH) as conn:
                columns = {
                    col[1] for col in conn.execute("PRAGMA table_info(irpj_cslls)").fetchall()
                }
            self.assertIn("codigo_barras", columns)
            self.assertIn("receipt_codigo_barras_digits", columns)
            self.assertIn("attachment_pdf_path", columns)


if __name__ == "__main__":
    unittest.main()
