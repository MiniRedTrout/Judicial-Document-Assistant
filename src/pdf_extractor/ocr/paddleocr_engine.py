import numpy as np

from src.config import pdf_settings
from src.utils.logger import get_logger

from .base import OCREngine

logger = get_logger(__name__)


class PaddleOCREngine(OCREngine):
    """OCR через PaddleOCR 3.x."""

    name = "paddleocr"

    def __init__(self) -> None:
        import torch
        from paddleocr import PaddleOCR

        logger.info("Инициализация PaddleOCR (языки: {})", pdf_settings.ocr_languages)
        lang = pdf_settings.ocr_languages[0] if pdf_settings.ocr_languages else "ru"

        self._reader = PaddleOCR(
            lang=lang,
            use_textline_orientation=True,
            device="cpu",
        )
    

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        try:
            result = self._reader.ocr(image, cls=True)
        except Exception as e:
            logger.error("PaddleOCR ошибка ocr: {}", e)
            return "", 0.0

        if not result or not result[0]:
            return "", 0.0

        lines: list[str] = []
        confidences: list[float] = []

        for line in result[0]:
            try:
                text, conf = line[1]
            except (IndexError, TypeError):
                continue
            if float(conf) >= pdf_settings.ocr_confidence_threshold:
                lines.append(str(text))
                confidences.append(float(conf))

        full_text = "\n".join(lines)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return full_text, avg_conf

    @staticmethod
    def _get_field(obj, key: str):
        if isinstance(obj, dict):
            return obj.get(key, [])
        if hasattr(obj, "get"):
            value = obj.get(key)
            return value if value is not None else []
        if hasattr(obj, key):
            value = getattr(obj, key)
            return value if value is not None else []
        try:
            return obj[key]
        except (KeyError, TypeError, IndexError):
            return []