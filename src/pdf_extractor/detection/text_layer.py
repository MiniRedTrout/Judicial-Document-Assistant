from pathlib import Path

import pdfplumber

from src.config import pdf_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def has_text_layer(pdf_path: str | Path, sample_pages: int | None = None) -> bool:
    """
    Проверяет, есть ли текстовый слой в PDF.

    При ошибке открытия PDF возвращает False (значит, пойдём в OCR).
    """
    pdf_path = Path(pdf_path)
    sample_pages = sample_pages or pdf_settings.sample_pages
    min_len = pdf_settings.min_text_length

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                logger.warning("PDF без страниц: {}", pdf_path.name)
                return False

            pages_to_check = pdf.pages[:sample_pages]
            text_pages = 0

            for page in pages_to_check:
                try:
                    text = page.extract_text() or ""
                    if len(text.strip()) >= min_len:
                        text_pages += 1
                except Exception as e:
                    logger.debug("Ошибка на странице {}: {}", page, e)
                    continue

            has_layer = text_pages >= max(1, len(pages_to_check) // 2)
            logger.debug(
                "{}: текстовых страниц {} из {} → {}",
                pdf_path.name,
                text_pages,
                len(pages_to_check),
                has_layer,
            )
            return has_layer

    except Exception as e:
        logger.error("Не удалось открыть PDF {}: {}", pdf_path.name, e)
        return False