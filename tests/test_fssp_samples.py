"""Реальные обезличенные примеры и известные расхождения исходного эталона."""
import contextlib
import io
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from app.services import document_store as store
from app.services.document_processor import process_document_background
from app.services.integrations.xml_parser import extract_xml
from app.services.xml_result_mapper import map_xml_result, serialize_xml_fields
from scripts.compare_xml_samples import FIXTURES, compare_samples
from scripts.recheck_results import main as recheck
from scripts.xml_address import parse_address


class FsspSampleTests(unittest.TestCase):
    def test_all_21_samples_against_24_columns(self):
        report = compare_samples()
        self.assertEqual(report["documents"], 21)
        self.assertEqual(report["checked_cells"], 504)
        self.assertEqual(report["matched_cells"], 500)
        self.assertEqual({(x["file"], x["field"]) for x in report["differences"]}, {
            ("fssp_004.xml", "street"), ("fssp_007.xml", "street"),
            ("fssp_011.xml", "street"),
            ("fssp_013.xml", "date_start"),
        })

    def test_debtor_direct_fields_and_total_not_remainder(self):
        raw = extract_xml(FIXTURES / "fssp_005.xml")
        result = map_xml_result(raw, "fssp_005.xml")
        self.assertEqual(result.enforcement.debt_sum, Decimal("227258.26"))
        self.assertEqual(result.debtor.birth_date, date(1988, 4, 7))
        self.assertEqual(result.debtor.inn, "814111514294")
        self.assertEqual(result.debtor.snils, "89378260718")
        self.assertEqual(result.debtor.last_name, "Регистрова")
        self.assertIsNone(result.debtor.passport)  # Текст содержит паспорта разных должников.
        self.assertEqual(len(serialize_xml_fields(raw)), 24)
        self.assertFalse(result.analysis.requires_review)

    def test_invalid_year_is_not_replaced_with_label(self):
        raw = extract_xml(FIXTURES / "fssp_013.xml")
        result = map_xml_result(raw, "fssp_013.xml")
        self.assertIsNone(result.debt.period_start)
        self.assertEqual(result.debt.period_end, date(2027, 4, 13))
        self.assertTrue(result.analysis.requires_review)
        self.assertTrue(any("нераспознанную дату" in r for r in result.analysis.review_reasons))

    def test_current_address_not_overwritten_by_quote(self):
        raw = extract_xml(FIXTURES / "fssp_001.xml")
        self.assertEqual(raw["street"], "г Тест, ул. 22 Пробная")
        raw = extract_xml(FIXTURES / "fssp_015.xml")
        self.assertEqual(raw["kv"], "22")
        self.assertEqual(parse_address("Россия, Пробная обл., г. Тест, Тест пр-кт, д. 38, корп. г, кв. 77"),
                         ("г Тест, пр-кт Тест", "38/г", "77"))

    def test_recheck_reads_source_and_preserves_mail(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(store, "DB_PATH", Path(temp) / "db.sqlite3"):
            source = FIXTURES / "fssp_005.xml"
            store.save_document({"document_id": "xml", "file_name": source.name,
                                 "file_type": "xml", "file_path": str(source)})
            process_document_background("xml", str(source), "xml")
            old = store.get_document_result("xml")
            old["xml_fields"]["IdDebtSum"] = "152832.96"
            old["mail_status"] = {"status": "SENT", "message_id": "unchanged"}
            store.save_document_result("xml", old)
            with contextlib.redirect_stdout(io.StringIO()): recheck()
            new = store.get_document_result("xml")
            self.assertEqual(new["enforcement"]["debt_sum"], "227258.26")
            self.assertEqual(new["debtor"]["inn"], "814111514294")
            self.assertEqual(new["mail_status"], old["mail_status"])
            self.assertEqual(len(new["xml_fields"]), 24)

    def test_missing_source_skipped_without_erasing_result(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(store, "DB_PATH", Path(temp) / "db.sqlite3"):
            store.save_document({"document_id": "xml", "file_name": "absent.xml", "file_type": "xml",
                                 "file_path": str(Path(temp) / "absent.xml"), "stage": "COMPLETED"})
            old = {"xml_fields": {"DbtrName": "Прежнее имя"}}
            store.save_document_result("xml", old)
            with contextlib.redirect_stdout(io.StringIO()): recheck()
            self.assertEqual(store.get_document_result("xml"), old)
