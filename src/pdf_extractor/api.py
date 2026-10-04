from pathlib import Path

from src.config import pdf_settings
from src.schemas.pdf_parser import (
    ExtractionResult,
    TableData,
    error_result,
)
from src.utils.logger import get_logger

from .detection import has_text_layer
from .extraction import extract_text_from_scan_pdf, extract_text_from_text_pdf

logger = get_logger(__name__)


def extract_text(pdf_path: str | Path) -> ExtractionResult:
    """Извлекает только текст из PDF."""
    pdf_path = Path(pdf_path)

    try:
        _validate_pdf(pdf_path)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Невалидный файл {}: {}", pdf_path, e)
        return error_result(pdf_path, str(e))

    try:
        text_layer = has_text_layer(pdf_path)
    except Exception as e:
        logger.error("Ошибка определения текстового слоя {}: {}", pdf_path, e)
        text_layer = False

    try:
        if text_layer:
            logger.info("Текстовый слой найден: {}", pdf_path.name)
            return extract_text_from_text_pdf(pdf_path)
        logger.info("Скан, запускаем OCR: {}", pdf_path.name)
        return extract_text_from_scan_pdf(pdf_path)
    except Exception as e:
        logger.exception("Критическая ошибка извлечения {}: {}", pdf_path, e)
        return error_result(pdf_path, f"extract_failed: {e}")


def extract_tables(pdf_path: str | Path) -> list[TableData]:
    """Извлекает только таблицы из PDF."""
    pdf_path = Path(pdf_path)

    try:
        _validate_pdf(pdf_path)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Невалидный файл {}: {}", pdf_path, e)
        return []

    if not pdf_settings.enable_table_extraction:
        return []

    try:
        if has_text_layer(pdf_path):
            from .tables import extract_tables_camelot
            return extract_tables_camelot(pdf_path)

        if pdf_settings.enable_pp_structure:
            from .tables import extract_tables_pp_structure
            return extract_tables_pp_structure(pdf_path)
    except Exception as e:
        logger.error("Ошибка извлечения таблиц {}: {}", pdf_path, e)

    return []


def extract_all(pdf_path: str | Path) -> ExtractionResult:
    """Основной вызов: извлекает текст + таблицы."""
    pdf_path = Path(pdf_path)

    result = extract_text(pdf_path)

    if not result.errors or result.text:
        try:
            result.tables = extract_tables(pdf_path)
        except Exception as e:
            logger.error("Ошибка таблиц {}: {}", pdf_path, e)
            result.errors.append(f"tables_failed: {e}")

    logger.info(
        "Готово: {} | страниц={} | OCR={} | таблиц={} | ошибок={}",
        pdf_path.name,
        result.pages_count,
        result.metadata.ocr_used,
        len(result.tables),
        len(result.errors),
    )
    return result


def _validate_pdf(pdf_path: Path) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF не найден: {pdf_path}")
    if not pdf_path.is_file():
        raise ValueError(f"Не файл: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Ожидался PDF, получен: {pdf_path.suffix}")
    if pdf_path.stat().st_size == 0:
        raise ValueError(f"Пустой файл: {pdf_path}")