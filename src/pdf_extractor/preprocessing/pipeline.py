import numpy as np

from src.config import pdf_settings
from src.utils.logger import get_logger

from .binarize import binarize
from .denoise import denoise
from .deskew import deskew

logger = get_logger(__name__)


def preprocess(
    image: np.ndarray,
    binarization_method: str | None = None,
) -> tuple[np.ndarray, list[str]]:
    method = binarization_method or pdf_settings.binarization_method
    steps: list[str] = []
    result = image

    if pdf_settings.enable_deskew:
        try:
            result = deskew(result)
            steps.append("deskew")
        except Exception as e:
            logger.warning("Deskew упал: {}", e)

    if pdf_settings.enable_denoise:
        try:
            result = denoise(result)
            steps.append("denoise")
        except Exception as e:
            logger.warning("Denoise упал: {}", e)

    if pdf_settings.enable_binarization:
        try:
            result = binarize(result, method=method)
            steps.append(f"binarize_{method}")
        except Exception as e:
            logger.warning("Binarize упал: {}", e)

    return result, steps