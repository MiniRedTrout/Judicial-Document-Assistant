"""Запуск из корня проекта: python scripts/check_storage.py

Читает существующую базу без создания новой и без изменения документов.
"""

import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.document_store import DB_PATH


def main() -> int:
    print("SQLite:", DB_PATH)
    if not DB_PATH.is_file():
        print("База не найдена. Запустите сервер и загрузите документ.")
        print("Если сервер использует JUDICIAL_DB_PATH, задайте тот же путь для этой команды.")
        return 1
    connection = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True)
    try:
        count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        print("Записей документов:", count)
        rows = connection.execute("""
            SELECT file_name, status, result_json IS NOT NULL
            FROM documents ORDER BY rowid DESC LIMIT 10
        """).fetchall()
        for file_name, status, has_result in rows:
            print(f"  {file_name} | {status} | результат: {'да' if has_result else 'нет'}")
    except sqlite3.Error as error:
        print("Не удалось прочитать таблицу documents:", error)
        return 1
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
