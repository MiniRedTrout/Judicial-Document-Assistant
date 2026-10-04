import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.services import document_store as store


class DocumentStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "documents.sqlite3"
        self.patch = patch.object(store, "DB_PATH", self.db)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        store.init_db()

    def save(self, document_id="test", status="UPLOADED"):
        store.save_document({
            "document_id": document_id, "file_name": "пример.xml",
            "file_type": "xml", "file_path": "/test/file.xml",
            "status": status, "stage": status, "progress": 0,
        })

    def test_save_and_read(self):
        self.save()
        self.assertEqual(store.get_document("test")["file_name"], "пример.xml")
        self.assertEqual(len(store.get_documents()), 1)
        self.assertIsNone(store.get_document("missing"))
        self.assertIsNone(store.get_document_result("test"))

    def test_status_updates_do_not_erase_result(self):
        self.save()
        result = {"debtor": {"full_name": "Тестов Иван"}, "sum": "0.00"}
        store.save_document_result("test", result)
        store.update_document_status("test", "REQUIRES_REVIEW", "COMPLETED", "Готово", 100)
        self.assertEqual(store.get_document_result("test"), result)
        self.assertEqual(store.get_document("test")["result"], result)
        self.assertNotIn("result", store.get_documents()[0])

    def test_new_process_reads_the_same_database(self):
        self.save(status="REQUIRES_REVIEW")
        store.save_document_result("test", {"value": "Сохранено"})
        env = os.environ.copy()
        env["JUDICIAL_DB_PATH"] = str(self.db)
        code = (
            "import json; from app.services.document_store import get_document_result; "
            "print(json.dumps(get_document_result('test')))"
        )
        output = subprocess.check_output(
            [sys.executable, "-c", code], env=env,
            cwd=Path(__file__).resolve().parents[1], text=True,
        )
        self.assertEqual(json.loads(output), {"value": "Сохранено"})

    def test_recovery_marks_only_interrupted_documents(self):
        for document_id, status in (("a", "UPLOADED"), ("b", "PROCESSING"),
                                    ("c", "REQUIRES_REVIEW"), ("d", "ERROR")):
            self.save(document_id, status)
        self.assertEqual(store.mark_interrupted_documents(), 2)
        self.assertEqual(store.get_document("a")["status"], "ERROR")
        self.assertIn("перезапуском", store.get_document("b")["error"])
        self.assertEqual(store.get_document("c")["status"], "REQUIRES_REVIEW")
        self.assertEqual(store.mark_interrupted_documents(), 0)

    def test_concurrent_writes(self):
        def work(index):
            document_id = str(index)
            self.save(document_id)
            store.save_document_result(document_id, {"index": index})
            store.update_document_status(document_id, "REQUIRES_REVIEW", "COMPLETED", "Готово", 100)
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(work, range(20)))
        self.assertEqual(len(store.get_documents()), 20)
        for index in range(20):
            self.assertEqual(store.get_document_result(str(index)), {"index": index})

    def test_invalid_progress_rolls_back_status_update(self):
        self.save()
        with self.assertRaises(sqlite3.IntegrityError):
            store.update_document_status("test", "PROCESSING", "TEST", "test", 101)
        self.assertEqual(store.get_document("test")["status"], "UPLOADED")

    def test_ids_are_bound_parameters(self):
        document_id = "id' OR 1=1 --"
        self.save(document_id)
        self.assertEqual(store.get_document(document_id)["document_id"], document_id)
        self.assertIsNone(store.get_document("different"))


if __name__ == "__main__":
    unittest.main()
