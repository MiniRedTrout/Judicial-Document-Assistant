from pathlib import Path

import numpy as np


import pymupdf


def _pdf_to_images(pdf_path: str, dpi: int = 200) -> list[np.ndarray]:
    doc = pymupdf.open(pdf_path)
    zoom = dpi / 72
    matrix = pymupdf.Matrix(zoom, zoom)
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        if pix.n == 4:
            img = img[:, :, :3]
        images.append(img)
    doc.close()
    return images



def pil_to_numpy(pil_image) -> np.ndarray:
    arr = np.array(pil_image)
    if len(arr.shape) == 3:
        arr = arr[:, :, ::-1]
    return arr
