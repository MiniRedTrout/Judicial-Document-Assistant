from pathlib import Path
import os
import numpy as np


def pdf_to_images(pdf_path, dpi=300):
    import fitz  # PyMuPDF
    import numpy as np

    doc = fitz.open(str(pdf_path))
    images = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        arr = np.frombuffer(pix.samples, dtype=np.uint8)
        arr = arr.reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            arr = arr[:, :, :3]
        if arr.shape[2] == 3:
            arr = arr[:, :, ::-1]  # RGB → BGR

        images.append(arr)

    doc.close()
    return images


def pil_to_numpy(pil_image) -> np.ndarray:
    arr = np.array(pil_image)
    if len(arr.shape) == 3:
        arr = arr[:, :, ::-1]
    return arr
