"""Запуск из корня Hakaton: python -m unittest discover -s tests -p test_xml_integration.py -v"""

import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from app.schemas.document_result import DocumentType
from app.services.document_processor import process_document_background
from app.services import document_store
from app.services.document_store import get_document, get_document_result, save_document
from app.services.xml_result_mapper import map_xml_result, serialize_xml_fields


class XmlMapperTests(unittest.TestCase):
    def test_fields_dates_money_and_zero(self):
        result = map_xml_result({
            "DocType2": "Постановление о возбуждении",
            "DocDate": "2026-10-03",
            "DbtrName": "Тестов Иван Иванович",
            "IdDeloNo": "001/2026",
            "IdDeloDate": "02.10.2026",
            "date_start": datetime(2026, 1, 1),
            "IdDocDate": date(2026, 9, 30),
            "IdDocNo": "000123",
            "IpNo": "00001/26/00001-ИП",
            "IdDebtSum": "1\xa0234,56",
            "rub_deb": 1200.56,
            "rub_peni": 0,
            "rub_poshlina": None,
            "rub_post": "34,00",
        }, "original.xml")

        self.assertEqual(result.document.document_type, DocumentType.FSSP_DECISION)
        self.assertEqual(result.document.file_name, "original.xml")
        self.assertEqual(result.document.document_date, date(2026, 10, 3))
        self.assertEqual(result.case.case_date, date(2026, 10, 2))
        self.assertEqual(result.debt.period_start, date(2026, 1, 1))
        self.assertEqual(result.enforcement.document_date, date(2026, 9, 30))
        self.assertEqual(result.enforcement.document_number, "000123")
        self.assertEqual(result.enforcement.debt_sum, Decimal("1234.56"))
        self.assertEqual(result.debt.principal, Decimal("1200.56"))
        self.assertEqual(result.debt.penalty, Decimal("0"))
        self.assertIsNone(result.debt.state_duty)
        self.assertEqual(result.debt.postal_expenses, Decimal("34.00"))
        self.assertIn("rub_poshlina", result.analysis.missing_fields)
        self.assertNotIn("rub_peni", result.analysis.missing_fields)
        payload = result.model_dump(mode="json")
        json.dumps(payload, allow_nan=False)
        self.assertEqual(payload["enforcement"]["debt_sum"], "1234.56")

    def test_bad_values_preserve_other_fields_and_request_review(self):
        result = map_xml_result({
            "DocType2": "Постановление о возбуждении",
            "DocDate": "2026-99-99",
            "IdDebtSum": "не число",
            "DbtrName": "Тестов Иван Иванович",
        }, "example.xml")
        self.assertIsNone(result.document.document_date)
        self.assertIsNone(result.enforcement.debt_sum)
        self.assertEqual(result.debtor.full_name, "Тестов Иван Иванович")
        self.assertTrue(result.analysis.requires_review)
        self.assertIn("DocDate", result.analysis.missing_fields)
        self.assertIn("IdDebtSum", result.analysis.missing_fields)
        self.assertTrue(any("Не извлечены обязательные поля" in reason for reason in result.analysis.review_reasons))

    def test_nonfinite_money_is_not_accepted(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                result = map_xml_result({"IdDebtSum": value}, "test.xml")
                self.assertIsNone(result.enforcement.debt_sum)
                self.assertIn("IdDebtSum", result.analysis.missing_fields)

    def test_unknown_document_is_not_classified_as_fssp(self):
        result = map_xml_result({"DocType2": "Неизвестный документ"}, "test.xml")
        self.assertEqual(result.document.document_type, DocumentType.UNKNOWN)

    def test_original_fields_are_serializable(self):
        raw = {"date_start": datetime(2026, 1, 1), "DocDate": "2026-10-03",
               "rub_deb": Decimal("1.23"), "rub_post": None}
        result = serialize_xml_fields(raw)
        self.assertEqual(set(result), set(raw))
        self.assertEqual(result["date_start"], "2026-01-01")
        self.assertIsInstance(raw["date_start"], datetime)
        json.dumps(result, allow_nan=False)


class DocumentProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Тесты используют отдельную базу, не трогая рабочие документы.
        self.store_patch = patch.object(
            document_store, "DB_PATH", Path(self.temp.name) / "test.sqlite3"
        )
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        self.path = Path(self.temp.name) / "saved-id.xml"
        save_document({"document_id": "test-id", "file_name": "uploaded.xml"})

    def test_real_parser_saves_fields_and_json(self):
        self.path.write_text('''<?xml version="1.0" encoding="UTF-8"?>
        <OIp xmlns="http://www.fssprus.ru/namespace/order/2017/2">
          <DocType>O_IP_ACT_START</DocType>
          <DocName>Постановление о возбуждении исполнительного производства</DocName>
          <DocDate>2026-10-03</DocDate><DebtorType>1</DebtorType>
          <DbtrName>Тестов Иван Иванович</DbtrName>
          <DbtrAdr>644000, Россия, г Тест, ул. Примерная, д. 10, кв. 2</DbtrAdr>
          <IdDocNo>000123</IdDocNo><IdDocDate>2026-10-01</IdDocDate>
          <IdDeloNo>2-001/2026</IdDeloNo><IdDeloDate>2026-09-30</IdDeloDate>
          <IdDebtSum>1050.50</IdDebtSum><IpNo>00001/26/00001-ИП</IpNo>
          <IdType>Судебный приказ</IdType>
          <IdDebtText>задолженность за период с 01.01.2026 по 31.08.2026
          в размере 1000,50 руб., пени в размере 0 руб.,
          государственной пошлины в размере 50 руб.</IdDebtText>
        </OIp>''', encoding="utf-8")
        process_document_background("test-id", str(self.path), "xml")
        document = get_document("test-id")
        result = get_document_result("test-id")
        self.assertEqual(document["status"], "COMPLETED")
        self.assertEqual(document["stage"], "COMPLETED")
        self.assertEqual(document["progress"], 100)
        self.assertEqual(result["document"]["file_name"], "uploaded.xml")
        self.assertEqual(result["debtor"]["full_name"], "Тестов Иван Иванович")
        self.assertEqual(result["debt"]["principal"], "1000.5")
        self.assertEqual(result["debt"]["penalty"], "0.0")
        self.assertEqual(result["debt"]["period_start"], "2026-01-01")
        self.assertEqual(result["enforcement"]["document_number"], "000123")
        self.assertEqual(len(result["xml_fields"]), 24)
        self.assertTrue(result["extracted_text"])
        json.dumps(result, allow_nan=False)

    def test_malformed_xml_sets_error(self):
        self.path.write_text("<broken>", encoding="utf-8")
        process_document_background("test-id", str(self.path), "xml")
        self.assertEqual(get_document("test-id")["status"], "ERROR")
        self.assertTrue(get_document("test-id")["error"])
        self.assertIsNone(get_document_result("test-id"))

    def test_unrelated_xml_sets_error(self):
        self.path.write_text("<root><foo>bar</foo></root>", encoding="utf-8")
        process_document_background("test-id", str(self.path), "xml")
        self.assertEqual(get_document("test-id")["status"], "ERROR")
        self.assertIsNone(get_document_result("test-id"))

    def test_missing_file_sets_error(self):
        process_document_background("test-id", str(self.path), "xml")
        self.assertEqual(get_document("test-id")["status"], "ERROR")
        self.assertIn("Файл не найден", get_document("test-id")["error"])

    def test_unsupported_type_sets_error(self):
        self.path.write_text("test", encoding="utf-8")
        process_document_background("test-id", str(self.path), "docx")
        self.assertEqual(get_document("test-id")["status"], "ERROR")

    def test_existing_pdf_flow_with_stub_extractor(self):
        # Проверяем маршрутизацию и сохранение PDF, не качество реального OCR.
        self.path.write_bytes(b"pdf-stub")
        module_name = "app.services.integrations.pdf_extractor"
        stub = ModuleType(module_name)
        stub.extract_pdf = Mock(return_value=SimpleNamespace(
            errors=[], text="Текст PDF", file=str(self.path), text_by_page=[]
        ))
        from app.services.integrations.llm import LLMUnavailable
        with patch.dict(sys.modules, {module_name: stub}), patch(
            "app.services.integrations.llm.extract_fields",
            side_effect=LLMUnavailable("LLM отключена в тесте"),
        ):
            process_document_background("test-id", str(self.path), "pdf")
        stub.extract_pdf.assert_called_once_with(self.path)
        self.assertEqual(get_document_result("test-id")["extracted_text"], "Текст PDF")
        self.assertEqual(get_document("test-id")["status"], "REQUIRES_REVIEW")
        self.assertNotIn("xml_fields", get_document_result("test-id"))


if __name__ == "__main__":
    unittest.main()
