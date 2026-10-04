import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from app.integration_settings import settings
from app.services import document_store as store
from app.services.document_processor import process_document_background
from app.services.integrations.llm import extract_fields, LLMUnavailable
from app.services.lawyer_mail import send_document_to_lawyer
from app.services.lawyer_review import review_pdf
from app.services.pdf_result_mapper import map_pdf_result
from src.schemas.pdf_parser.extraction import ExtractionResult, ExtractionMetadata, PageText


def source(text="В иске отказать."):
    return ExtractionResult(
        file="document.pdf", has_text_layer=True, pages_count=1, text=text,
        text_by_page=[PageText(page=1, text=text)],
        metadata=ExtractionMetadata(extractor="test"),
    )


@contextmanager
def llm_server(content, status=200):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            data = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch.object(settings, "llm_base", f"http://127.0.0.1:{server.server_port}/v1"), \
             patch.object(settings, "llm_key", "local-test-key"):
            yield requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class LlmMailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "saved-id.pdf"
        self.path.write_bytes(b"test-attachment")
        patches = [
            patch.object(store, "DB_PATH", self.root / "test.sqlite3"),
            patch.object(settings, "llm_key", ""),
            patch.object(settings, "mail_enabled", False),
            patch.object(settings, "mail_auto_send", False),
            patch.object(settings, "mail_from", "sender@example.test"),
            patch.object(settings, "mail_lawyer", "lawyer@example.test"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        store.save_document({"document_id": "test", "file_name": "original.pdf",
                             "file_type": "pdf", "file_path": str(self.path)})

    def process_pdf(self, fields=None):
        module = ModuleType("app.services.integrations.pdf_extractor")
        module.extract_pdf = Mock(return_value=source())
        import sys
        with patch.dict(sys.modules, {module.__name__: module}):
            if fields is None:
                process_document_background("test", str(self.path), "pdf")
            else:
                with patch("app.services.integrations.llm.extract_fields", return_value=fields):
                    process_document_background("test", str(self.path), "pdf")
        return store.get_document_result("test")

    def selected_document(self):
        store.save_document_result("test", {"lawyer_review": review_pdf(source())})

    def test_llm_openai_compatible_transport(self):
        content = json.dumps({"тип_документа": "Судебный приказ", "инн": "00123"})
        with llm_server(content) as requests:
            result = extract_fields(source())
        self.assertEqual(result["инн"], "00123")
        self.assertEqual(requests[0][0], "/v1/chat/completions")
        self.assertEqual(requests[0][1]["messages"][1]["content"], source().text)

    def test_invalid_json_and_http_error(self):
        for content, status in (("not JSON", 200), ('{"дз_осн": NaN}', 200), ("{}", 503)):
            with self.subTest(content=content), llm_server(content, status):
                with self.assertRaises(LLMUnavailable):
                    extract_fields(source())

    def test_missing_llm_key_keeps_text_and_marker_candidates(self):
        result = self.process_pdf()
        self.assertEqual(store.get_document("test")["status"], "REQUIRES_REVIEW")
        self.assertEqual(result["extracted_text"], source().text)
        self.assertEqual(result["document"]["file_name"], "original.pdf")
        self.assertTrue(result["lawyer_review"]["requires_context_review"])
        self.assertEqual(store.get_mail_status("test")["status"], "NOT_REQUESTED")

    def test_pdf_fields_are_mapped_and_saved(self):
        result = self.process_pdf({"тип_документа": "ИЛ", "фио": "Тестов Иван",
            "инн": "000012345678", "дз_осн": "1234,56", "дз_пени": 0,
            "дата_рождения": "2000-01-01", "дело_номер": "0001/2026",
            "соответчики_кол-во": 1, "соответчики_фио": "Тестов Иван"})
        self.assertEqual(result["document"]["document_type"], "Исполнительный лист")
        self.assertEqual(result["debtor"]["inn"], "000012345678")
        self.assertEqual(result["debt"]["principal"], "1234.56")
        self.assertEqual(result["debt"]["penalty"], "0")
        self.assertEqual(store.get_document_result("test"), result)

    def test_invalid_fields_do_not_destroy_other_fields(self):
        result = map_pdf_result({"фио": "Тестов Иван", "дз_осн": "bad",
                                 "дело_дата": "2026-99-99"}, "test.pdf")
        self.assertEqual(result.debtor.full_name, "Тестов Иван")
        self.assertIsNone(result.debt.principal)
        self.assertIn("дело_дата", result.analysis.missing_fields)

    def test_page_contract_and_confirmation(self):
        review = review_pdf(source(), {"matched_phrase": "в иске отказать",
                                      "lawyer_evidence": "В иске отказать."})
        self.assertEqual(review["matches"][0]["page"], 1)
        self.assertFalse(review["requires_context_review"])
        invented = review_pdf(source("Иск удовлетворить."), {
            "matched_phrase": "в иске отказать", "lawyer_evidence": "В иске отказать."})
        self.assertFalse(invented["needs_lawyer"])

    def test_disabled_mail_does_not_connect(self):
        self.selected_document()
        with patch("app.services.integrations.mailer.smtplib.SMTP_SSL") as smtp, \
             self.assertLogs("app.services.lawyer_mail", level="ERROR"):
            response = send_document_to_lawyer("test")
        self.assertEqual(response["status"], "ERROR")
        smtp.assert_not_called()
        self.assertIsNotNone(store.get_document_result("test"))

    def test_smtp_attachment_original_name_and_deduplication(self):
        self.selected_document()
        smtp = Mock()
        smtp.__enter__ = Mock(return_value=smtp)
        smtp.__exit__ = Mock(return_value=False)
        smtp.send_message.return_value = {}
        with patch.object(settings, "mail_enabled", True), \
             patch.object(settings, "mail_user", ""), \
             patch("app.services.integrations.mailer.smtplib.SMTP_SSL", return_value=smtp):
            first = send_document_to_lawyer("test")
            second = send_document_to_lawyer("test")
        self.assertEqual(first["status"], "SENT")
        self.assertEqual(first, second)
        self.assertIsNotNone(first["sent_at"])
        smtp.send_message.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        attachment = next(message.iter_attachments())
        self.assertEqual(attachment.get_filename(), "original.pdf")
        self.assertEqual(attachment.get_payload(decode=True), b"test-attachment")

    def test_smtp_failure_can_be_retried(self):
        self.selected_document()
        with patch("app.services.lawyer_mail.send_message", side_effect=RuntimeError("SMTP")), \
             self.assertLogs("app.services.lawyer_mail", level="ERROR"):
            self.assertEqual(send_document_to_lawyer("test")["status"], "ERROR")
        with patch("app.services.lawyer_mail.send_message") as send:
            self.assertEqual(send_document_to_lawyer("test")["status"], "SENT")
            send.assert_called_once()

    def test_unselected_document_is_not_sent(self):
        store.save_document_result("test", {"lawyer_review": {"needs_lawyer": False}})
        with patch("app.services.lawyer_mail.send_message") as send:
            with self.assertRaises(ValueError):
                send_document_to_lawyer("test")
            send.assert_not_called()

    def test_interrupted_mail_has_explicit_error(self):
        self.assertTrue(store.claim_mail_delivery("test"))
        self.assertFalse(store.claim_mail_delivery("test"))
        store.mark_interrupted_documents()
        self.assertEqual(store.get_mail_status("test")["status"], "ERROR")

    def test_auto_mail_requires_confirmation(self):
        with patch.object(settings, "mail_enabled", True), \
             patch.object(settings, "mail_auto_send", True), \
             patch("app.services.lawyer_mail.send_document_to_lawyer") as send:
            self.process_pdf({})
            send.assert_not_called()
            self.process_pdf({"matched_phrase": "в иске отказать",
                              "lawyer_evidence": "В иске отказать."})
            send.assert_called_once_with("test")

    def test_missing_attachment_is_not_silently_skipped(self):
        self.selected_document()
        self.path.unlink()
        with patch("app.services.lawyer_mail.send_message") as send, \
             self.assertLogs("app.services.lawyer_mail", level="ERROR"):
            self.assertEqual(send_document_to_lawyer("test")["status"], "ERROR")
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
