"""Постоянное хранилище документов на SQLite со старым интерфейсом функций."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get(
    "JUDICIAL_DB_PATH", str(PROJECT_ROOT / "storage" / "documents.sqlite3")
)).expanduser().resolve()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    message TEXT NOT NULL,
    progress INTEGER NOT NULL CHECK (progress BETWEEN 0 AND 100),
    error TEXT,
    result_json TEXT
)
"""

_MAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS mail_deliveries (
    document_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    error TEXT,
    sent_at TEXT,
    message_id TEXT
)
"""


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    # Каждая операция получает своё соединение, в том числе из фонового потока.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(_SCHEMA)
        connection.execute(_MAIL_SCHEMA)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    """Создаёт таблицу и включает WAL для чтения во время записи."""
    with _connection() as connection:
        connection.execute("PRAGMA journal_mode=WAL")


def _row_to_document(row: sqlite3.Row) -> dict[str, Any]:
    document = dict(row)
    result_json = document.pop("result_json")
    if result_json is not None:
        document["result"] = json.loads(result_json)
    return document


def save_document(document: dict[str, Any]) -> None:
    """Сохраняет запись документа; результат обновляется отдельной функцией."""
    values = (
        document["document_id"], document["file_name"],
        document.get("file_type", ""), document.get("file_path", ""),
        document.get("status", "UPLOADED"), document.get("stage", "UPLOADED"),
        document.get("message", "Файл успешно загружен"),
        document.get("progress", 0), document.get("error"),
    )
    with _connection() as connection:
        connection.execute("""
            INSERT INTO documents (
                document_id, file_name, file_type, file_path,
                status, stage, message, progress, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                file_name=excluded.file_name, file_type=excluded.file_type,
                file_path=excluded.file_path, status=excluded.status,
                stage=excluded.stage, message=excluded.message,
                progress=excluded.progress, error=excluded.error
        """, values)


def get_document(document_id: str) -> Optional[dict[str, Any]]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE document_id = ?", (document_id,)
        ).fetchone()
    return _row_to_document(row) if row is not None else None


def get_documents() -> list[dict[str, Any]]:
    # Для списка не загружаем большие результаты OCR из базы.
    with _connection() as connection:
        rows = connection.execute("""
            SELECT document_id, file_name, file_type, file_path,
                   status, stage, message, progress, error
            FROM documents ORDER BY rowid
        """).fetchall()
    return [dict(row) for row in rows]


def update_document_status(
    document_id: str, status: str, stage: str, message: str,
    progress: int, error: Optional[str] = None,
) -> None:
    with _connection() as connection:
        connection.execute("""
            UPDATE documents
            SET status = ?, stage = ?, message = ?, progress = ?, error = ?
            WHERE document_id = ?
        """, (status, stage, message, progress, error, document_id))


def save_document_result(document_id: str, result: dict[str, Any]) -> None:
    # Обработчик уже переводит date и Decimal в JSON-совместимые значения.
    result_json = json.dumps(result, ensure_ascii=False, allow_nan=False)
    with _connection() as connection:
        connection.execute(
            "UPDATE documents SET result_json = ? WHERE document_id = ?",
            (result_json, document_id),
        )


def get_document_result(document_id: str) -> Optional[dict[str, Any]]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT result_json FROM documents WHERE document_id = ?", (document_id,)
        ).fetchone()
    if row is None or row["result_json"] is None:
        return None
    return json.loads(row["result_json"])


def mark_interrupted_documents() -> int:
    """На старте одного сервера отмечает задачи, прерванные прошлым запуском."""
    message = "Обработка прервана перезапуском сервера. Загрузите документ повторно."
    with _connection() as connection:
        connection.execute("""
            UPDATE mail_deliveries SET status = 'ERROR',
                error = 'Отправка прервана. Перед повтором проверьте почтовый ящик получателя.'
            WHERE status = 'SENDING'
        """)
        cursor = connection.execute("""
            UPDATE documents SET status = 'ERROR', stage = 'ERROR',
                message = ?, progress = 100, error = ?
            WHERE status IN ('UPLOADED', 'PROCESSING')
        """, (message, message))
        return cursor.rowcount


def get_mail_status(document_id: str) -> dict[str, Any]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM mail_deliveries WHERE document_id = ?", (document_id,)
        ).fetchone()
    return dict(row) if row else {
        "document_id": document_id, "status": "NOT_REQUESTED",
        "error": None, "sent_at": None, "message_id": None,
    }


def claim_mail_delivery(document_id: str) -> bool:
    # INSERT/UPDATE атомарны: повторный запрос не начинает вторую отправку.
    with _connection() as connection:
        cursor = connection.execute("""
            INSERT INTO mail_deliveries(document_id, status) VALUES (?, 'SENDING')
            ON CONFLICT(document_id) DO UPDATE SET status = 'SENDING', error = NULL
            WHERE mail_deliveries.status NOT IN ('SENT', 'SENDING')
        """, (document_id,))
        return cursor.rowcount == 1


def finish_mail_delivery(document_id: str, status: str, error=None, message_id=None) -> None:
    sent_at = datetime.now(timezone.utc).isoformat() if status == "SENT" else None
    with _connection() as connection:
        connection.execute("""
            UPDATE mail_deliveries SET status = ?, error = ?, sent_at = ?, message_id = ?
            WHERE document_id = ?
        """, (status, error, sent_at, message_id, document_id))
