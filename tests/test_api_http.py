"""HTTP-тесты Uvicorn, multipart-загрузки и перезапуска сервера.
Тесты используют временную папку и отдельную SQLite-базу.
Запуск: python -m unittest discover -s tests -p test_api_http.py -v
"""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from app.services import document_store


XML_SAMPLE = b'''<?xml version="1.0" encoding="UTF-8"?>
<OIp xmlns="http://www.fssprus.ru/namespace/order/2017/2">
<DocType>O_IP_ACT_START</DocType>
<DocName>\xd0\x9f\xd0\xbe\xd1\x81\xd1\x82\xd0\xb0\xd0\xbd\xd0\xbe\xd0\xb2\xd0\xbb\xd0\xb5\xd0\xbd\xd0\xb8\xd0\xb5 \xd0\xbe \xd0\xb2\xd0\xbe\xd0\xb7\xd0\xb1\xd1\x83\xd0\xb6\xd0\xb4\xd0\xb5\xd0\xbd\xd0\xb8\xd0\xb8</DocName>
<DocDate>2026-10-03</DocDate><DbtrName>Test Debtor</DbtrName>
<IdDebtSum>123.45</IdDebtSum><IpNo>00001/26/00001</IpNo>
</OIp>'''


def multipart(files):
    boundary = "test" + uuid4().hex
    chunks = []
    for field, filename, content, mime in files:
        chunks.append((
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
        ).encode("utf-8"))
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


@unittest.skipUnless(importlib.util.find_spec("uvicorn") and importlib.util.find_spec("fastapi"),
                     "HTTP-тесты требуют установленных FastAPI и Uvicorn")
class ApiHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        self.env["JUDICIAL_DB_PATH"] = str(self.root / "documents.sqlite3")
        self.env["JUDICIAL_STORAGE_DIR"] = str(self.root / "uploads")
        # Не используем реальные интеграции из пользовательского .env.
        self.env["LLM_API_KEY"] = ""
        self.env["MAIL_ENABLED"] = "false"
        self.env["MAIL_AUTO_SEND"] = "false"
        self.process = None
        self.output_thread = None
        self.server_output = []
        self.addCleanup(self.stop_server)
        self.start_server()

    def start_server(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        self.server_output = []
        self.process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port),
            "--loop", "asyncio", "--http", "h11", "--ws", "none",
        ], cwd=Path(__file__).resolve().parents[1], env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        # Постоянно читаем PIPE, чтобы журнал не блокировал сервер.
        stream = self.process.stdout
        output = self.server_output
        def read_output():
            try:
                for line in stream:
                    output.append(line)
                    if len(output) > 200:
                        del output[:-200]
            finally:
                stream.close()
        self.output_thread = threading.Thread(target=read_output, daemon=True)
        self.output_thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                if self.request("/health")[0] == 200:
                    return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            time.sleep(0.05)
        self.stop_server()
        self.fail("Сервер не запустился:\n" + "".join(self.server_output))

    def stop_server(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            if self.output_thread is not None:
                self.output_thread.join(timeout=5)
                if self.output_thread.is_alive():
                    raise RuntimeError("Поток чтения журнала сервера не завершился")
            self.process = None
            self.output_thread = None

    def request(self, path, files=None):
        headers = {}
        data = None
        if files is not None:
            data, content_type = multipart(files)
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def completed(self, document_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            code, status = self.request(f"/api/documents/{document_id}/status")
            self.assertEqual(code, 200)
            if status["status"] not in ("UPLOADED", "PROCESSING"):
                return status
            time.sleep(0.05)
        self.fail("Обработка документа не завершилась")

    def upload_one(self, name="fssp_006 (4).xml", content=XML_SAMPLE):
        code, response = self.request("/api/documents/upload", [
            ("file", name, content, "text/xml"),
        ])
        self.assertEqual(code, 202, response)
        return response["document_id"]

    def test_frontend_and_export_http(self):
        import csv
        import io
        with urllib.request.urlopen(self.base_url + "/") as response:
            self.assertIn('вставьте ваш(и) файл(ы)', response.read().decode('utf-8'))
        with urllib.request.urlopen(self.base_url + "/static/app.js") as response:
            self.assertEqual(response.status, 200)
        identifier = self.upload_one()
        self.completed(identifier)
        with urllib.request.urlopen(self.base_url + "/api/exports/xml.csv?document_id=" + identifier) as response:
            rows = list(csv.reader(io.StringIO(response.read().decode('utf-8-sig'))))
            self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertEqual(rows[0][0], 'FileName')
        self.assertEqual(rows[1][0], 'fssp_006 (4).xml')
        self.assertEqual(rows[1][10], '123.45')
        self.assertEqual(self.request('/api/exports/pdf.csv')[0], 409)
        self.assertEqual(self.request('/api/exports/xml.csv?document_id=unknown')[0], 404)

    def test_single_upload_preserves_filename(self):
        document_id = self.upload_one()
        self.assertEqual(self.completed(document_id)["status"], "REQUIRES_REVIEW")
        code, result = self.request(f"/api/documents/{document_id}/result")
        self.assertEqual(code, 200)
        self.assertEqual(result["document"]["file_name"], "fssp_006 (4).xml")
        self.assertEqual(result["enforcement"]["debt_sum"], "123.45")

    def test_openapi_file_inputs_are_binary(self):
        code, schema = self.request("/openapi.json")
        self.assertEqual(code, 200)
        for path, field in (("/api/documents/upload", "file"),
                            ("/api/documents/upload-batch", "files")):
            body = schema["paths"][path]["post"]["requestBody"]
            ref = body["content"]["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
            value = schema["components"]["schemas"][ref]["properties"][field]
            if field == "files":
                self.assertEqual(value["type"], "array")
                value = value["items"]
            self.assertEqual(value["type"], "string")
            self.assertEqual(value["format"], "binary")
            self.assertEqual(value["contentMediaType"], "application/octet-stream")

    def test_batch_two_xml_and_temp_file(self):
        code, response = self.request("/api/documents/upload-batch", [
            ("files", "first.xml", XML_SAMPLE, "text/xml"),
            ("files", "второй.XML", XML_SAMPLE, "text/xml"),
            ("files", "temp.tmp", b"test", "application/octet-stream"),
        ])
        self.assertEqual(code, 202, response)
        self.assertEqual([d["file_name"] for d in response["documents"]], ["first.xml", "второй.XML"])
        self.assertEqual(response["errors"][0]["file_name"], "temp.tmp")
        for document in response["documents"]:
            self.assertEqual(self.completed(document["document_id"])["status"], "REQUIRES_REVIEW")
        code, documents = self.request("/api/documents")
        self.assertEqual(code, 200)
        self.assertEqual(len(documents), 2)
        self.assertFalse(any(d["file_name"] == "temp.tmp" for d in documents))

    def test_only_unsupported_files_are_rejected(self):
        code, response = self.request("/api/documents/upload-batch", [
            ("files", "notes.txt", b"test", "text/plain"),
        ])
        self.assertEqual(code, 400)
        self.assertEqual(len(response["detail"]["errors"]), 1)
        self.assertEqual(self.request("/api/documents")[1], [])

    def test_wrong_multipart_field_is_rejected(self):
        code, _ = self.request("/api/documents/upload-batch", [
            ("file", "first.xml", XML_SAMPLE, "text/xml"),
        ])
        self.assertEqual(code, 422)

    def test_bad_xml_does_not_stop_next_file_in_batch(self):
        code, response = self.request("/api/documents/upload-batch", [
            ("files", "broken.xml", b"<broken>", "text/xml"),
            ("files", "good.xml", XML_SAMPLE, "text/xml"),
        ])
        self.assertEqual(code, 202)
        statuses = [self.completed(d["document_id"])["status"] for d in response["documents"]]
        self.assertEqual(statuses, ["ERROR", "REQUIRES_REVIEW"])

    def test_results_and_list_survive_server_restart(self):
        document_id = self.upload_one()
        self.completed(document_id)
        before = self.request(f"/api/documents/{document_id}/result")[1]
        self.stop_server()
        self.start_server()
        code, after = self.request(f"/api/documents/{document_id}/result")
        self.assertEqual(code, 200)
        self.assertEqual(after, before)
        self.assertEqual(self.request("/api/documents")[1][0]["document_id"], document_id)
        self.assertEqual(self.completed(document_id)["status"], "REQUIRES_REVIEW")

    def test_interrupted_task_is_marked_after_restart(self):
        with patch.object(document_store, "DB_PATH", Path(self.env["JUDICIAL_DB_PATH"])):
            document_store.save_document({
                "document_id": "interrupted", "file_name": "unfinished.xml",
                "file_type": "xml", "status": "PROCESSING",
            })
        self.stop_server()
        self.start_server()
        status = self.completed("interrupted")
        self.assertEqual(status["status"], "ERROR")
        self.assertIn("перезапуском", status["error"])

    def test_lawyer_routes_and_xml_not_selected(self):
        document_id = self.upload_one()
        self.completed(document_id)
        code, status = self.request(f"/api/documents/{document_id}/mail-status")
        self.assertEqual(code, 200)
        self.assertEqual(status["status"], "NOT_REQUESTED")
        request = urllib.request.Request(
            self.base_url + f"/api/documents/{document_id}/send-to-lawyer",
            data=b"", method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(error.exception.code, 409)
        error.exception.close()
        self.assertEqual(self.request("/api/documents/missing/mail-status")[0], 404)


if __name__ == "__main__":
    unittest.main()
