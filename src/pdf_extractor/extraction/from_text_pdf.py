from pathlib import Path

import pdfplumber

from src.schemas.pdf_parser import (
    ExtractionMetadata,
    ExtractionResult,
    PageText,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_from_text_pdf(pdf_path: str | Path) -> ExtractionResult:
    """Извлекает текст из PDF с текстовым слоем через pdfplumber."""
    pdf_path = Path(pdf_path)
    text_by_page: list[PageText] = []
    errors: list[str] = []
    pages_count = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                    text_by_page.append(PageText(page=i, text=page_text))
                except Exception as e:
                    logger.warning("Ошибка на странице {} файла {}: {}", i, pdf_path.name, e)
                    text_by_page.append(PageText(page=i, text=""))
                    errors.append(f"page_{i}_failed: {e}")
    except Exception as e:
        logger.error("Ошибка открытия PDF {}: {}", pdf_path, e)
        errors.append(f"open_failed: {e}")

    full_text = "\n\n".join(p.text for p in text_by_page)

    return ExtractionResult(
        file=str(pdf_path),
        has_text_layer=True,
        pages_count=pages_count,
        text=full_text,
        text_by_page=text_by_page,
        tables=[],
        metadata=ExtractionMetadata(extractor="pdfplumber", ocr_used=False),
        errors=errors,
    )