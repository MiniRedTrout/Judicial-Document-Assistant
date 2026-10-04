import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


def deskew(image: np.ndarray) -> np.ndarray:

    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        h, w = gray.shape[:2]
        scale = 1000 / max(h, w) if max(h, w) > 1000 else 1.0
        if scale < 1.0:
            small = cv2.resize(gray, None, fx=scale, fy=scale)
        else:
            small = gray

        edges = cv2.Canny(small, 50, 150, apertureSize=3)

        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        if lines is None:
            return image

        angles = []
        for line in lines[:50]:
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:
                angles.append(angle)

        if not angles:
            return image

        median_angle = float(np.median(angles))
        if abs(median_angle) < 0.5:
            return image

        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        return cv2.warpAffine(
            image,
            matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    except Exception as e:
        logger.warning("Deskew ошибка: {}", e)
        return image