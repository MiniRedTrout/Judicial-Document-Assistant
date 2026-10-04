from pathlib import Path

import pdfplumber

from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_pages_count(pdf_path: str | Path) -> int:
    """Возвращает количество страниц в PDF. При ошибке — 0."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception as e:
        logger.error("Не удалось получить количество страниц {}: {}", pdf_path, e)
        return 0