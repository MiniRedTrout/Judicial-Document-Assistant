from pathlib import Path

from src.pdf_extractor import extract_all
from src.schemas.pdf_parser import ExtractionResult


def extract_pdf(pdf_path: str | Path) -> ExtractionResult:
    """
    Адаптер между FastAPI  и модулем pdfext
    Принимает путь к PDF и возвращает
    стандартный ExtractionResult
    """
    return extract_all(pdf_path)