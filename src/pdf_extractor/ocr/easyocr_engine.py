import os
import os


os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import threading
import numpy as np
import threading

import numpy as np

from src.config import pdf_settings
from src.utils.logger import get_logger

from .base import OCREngine
from .postprocess import postprocess

logger = get_logger(__name__)


_MODEL_DIR = os.environ.get(
    "EASYOCR_MODULE_PATH",
    "/app/data/cache/easyocr",
)


class EasyOCREngine(OCREngine):

    name = "easyocr"

    _reader = None
    _reader_lock = threading.Lock()

    _infer_lock = threading.Lock()

    def __init__(self) -> None:
        if EasyOCREngine._reader is None:
            try:
                import easyocr  
            except ImportError as e:
                raise RuntimeError(
                    "EasyOCR не установлен. Выполните: pip install easyocr"
                ) from e

        self._ensure_reader()

    @classmethod
    def _ensure_reader(cls):
        if cls._reader is not None:
            return cls._reader

        with cls._reader_lock:
            if cls._reader is not None: 
                return cls._reader

            import easyocr
            import torch
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)

            logger.info(
                "Инициализация EasyOCR (языки: {}, GPU: {}, models: {})",
                pdf_settings.ocr_languages,
                pdf_settings.ocr_use_gpu,
                _MODEL_DIR,
            )

            os.makedirs(_MODEL_DIR, exist_ok=True)

            cls._reader = easyocr.Reader(
                pdf_settings.ocr_languages,
                gpu=pdf_settings.ocr_use_gpu,
                verbose=False,
                model_storage_directory=_MODEL_DIR,
                download_enabled=True,  
                                        
            )
            logger.info("EasyOCR Reader готов (singleton)")
            return cls._reader

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        import time
        import cv2

        reader = self._ensure_reader()

        h, w = image.shape[:2]
        max_side = 1600
        if max(h, w) > max_side:
            scale = max_side / max(h, w)
            image = cv2.resize(
                image,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_AREA,
            )
            logger.info(
                "Resize: {}x{} -> {}x{}", w, h, image.shape[1], image.shape[0]
            )

        t0 = time.perf_counter()
        try:
            with EasyOCREngine._infer_lock:
                results = reader.readtext(
                    image,
                    detail=1,
                    paragraph=False,
                    canvas_size=1280,
                    mag_ratio=1.0,
                    text_threshold=0.7,
                    low_text=0.4,
                    link_threshold=0.4,
                    batch_size=1,
                )
        except Exception as e:
            logger.error("EasyOCR ошибка распознавания: {}", e)
            return "", 0.0

        logger.info("readtext: {:.2f}s", time.perf_counter() - t0)

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
