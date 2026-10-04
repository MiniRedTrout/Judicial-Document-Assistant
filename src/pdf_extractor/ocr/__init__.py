from src.config import pdf_settings
from src.utils.logger import get_logger

from .base import OCREngine

logger = get_logger(__name__)

_engine: OCREngine | None = None


def get_ocr_engine() -> OCREngine:
    """Возвращает singleton OCR-движка согласно настройкам."""
    global _engine
    if _engine is not None:
        return _engine

    engine_name = pdf_settings.ocr_engine.lower()

    try:
        if engine_name == "easyocr":
            from .easyocr_engine import EasyOCREngine
            _engine = EasyOCREngine()
        elif engine_name == "paddleocr":
            from .paddleocr_engine import PaddleOCREngine
            _engine = PaddleOCREngine()
        else:
            raise ValueError(f"Неизвестный OCR-движок: {engine_name}")
    except Exception as e:
        logger.error("Ошибка инициализации OCR '{}': {}", engine_name, e)
        if engine_name != "easyocr":
            logger.info("Fallback на EasyOCR")
            from .easyocr_engine import EasyOCREngine
            _engine = EasyOCREngine()
        else:
            raise

    return _engine


__all__ = ["OCREngine", "get_ocr_engine"]