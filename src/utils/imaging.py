from pathlib import Path
import os
import numpy as np


def pdf_to_images(pdf_path: str | Path, dpi: int = 300) -> list[np.ndarray]:
    from pdf2image import convert_from_path

    poppler_path = os.getenv("POPPLER_PATH", "").strip() or None
    pil_images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_path)
    return [pil_to_numpy(img) for img in pil_images]


def pil_to_numpy(pil_image) -> np.ndarray:
    arr = np.array(pil_image)
    if len(arr.shape) == 3:
        arr = arr[:, :, ::-1]
    return arr
