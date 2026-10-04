import numpy as np

from src.config import pdf_settings
from src.utils.logger import get_logger

from .base import OCREngine
from .postprocess import postprocess

logger = get_logger(__name__)


class EasyOCREngine(OCREngine):

    name = "easyocr"

    def __init__(self) -> None:
        try:
            import easyocr
        except ImportError as e:
            raise RuntimeError(
                "EasyOCR не установлен. Выполните: pip install easyocr"
            ) from e

        logger.info(
            "Инициализация EasyOCR (языки: {}, GPU: {})",
            pdf_settings.ocr_languages,
            pdf_settings.ocr_use_gpu,
        )
        self._reader = easyocr.Reader(
            pdf_settings.ocr_languages,
            gpu=pdf_settings.ocr_use_gpu,
            verbose=False,
        )

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        try:
            results = self._reader.readtext(image, detail=1, paragraph=False)
        except Exception as e:
            logger.error("EasyOCR ошибка распознавания: {}", e)
            return "", 0.0

        if not results:
            return "", 0.0

        lines: list[str] = []
        confidences: list[float] = []

        for item in results:
            try:
                _, text, conf = item
                if conf >= pdf_settings.ocr_confidence_threshold:
                    lines.append(text)
                    confidences.append(conf)
            except Exception:
                continue

        full_text = "\n".join(lines)

        if pdf_settings.enable_postprocess:
            full_text = postprocess(full_text, dedup=False)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return full_text, avg_conf