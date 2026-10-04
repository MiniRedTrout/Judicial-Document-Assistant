from pathlib import Path
import os
from uuid import uuid4

from fastapi import UploadFile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = Path(os.environ.get(
    "JUDICIAL_STORAGE_DIR", str(PROJECT_ROOT / "storage")
)).expanduser().resolve()


def save_uploaded_file(file: UploadFile) -> tuple[str, str]:
    """
    Сохраняет загруженный файл на диск
    Возвращает:
        document_id — уникальный ID документа
        file_path — путь к сохранённому файлу
    """

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    document_id = str(uuid4())

    original_name = file.filename or "unknown"

    extension = Path(original_name).suffix.lower()

    new_file_name = f"{document_id}{extension}"

    file_path = STORAGE_DIR / new_file_name

    try:
        with file_path.open("wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                buffer.write(chunk)
    except OSError:
        file_path.unlink(missing_ok=True)
        raise

    return document_id, str(file_path)
