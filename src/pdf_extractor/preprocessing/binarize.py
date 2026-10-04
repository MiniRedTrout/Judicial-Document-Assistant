import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


def binarize_otsu(image: np.ndarray) -> np.ndarray:
    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    except Exception as e:
        logger.warning("Binarize (otsu) ошибка: {}", e)
        return image


def binarize_adaptive(image: np.ndarray) -> np.ndarray:
    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2,
        )
        return binary
    except Exception as e:
        logger.warning("Binarize (adaptive) ошибка: {}", e)
        return image


def binarize(image: np.ndarray, method: str = "otsu") -> np.ndarray:
    if method == "adaptive":
        return binarize_adaptive(image)
    return binarize_otsu(image)