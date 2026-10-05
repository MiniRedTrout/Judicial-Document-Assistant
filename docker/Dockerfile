FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EASYOCR_MODULE_PATH=/app/data/cache/easyocr

WORKDIR /app

# Системные зависимости:
# - libgomp1       — OpenMP для torch/easyocr
# - libglib2.0-0   — требуется opencv
# - ca-certificates — https
# poppler-utils БОЛЬШЕ НЕ НУЖЕН — конвертация PDF через PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libglib2.0-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements*.txt ./

# CPU-вариант torch без CUDA.
RUN python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install -r requirements.txt \
    && python -m pip install -r requirements-ocr.txt

# Предзагрузка моделей EasyOCR в образ (если используете EasyOCR)
RUN mkdir -p /app/data/cache/easyocr \
 && python -c "import easyocr; easyocr.Reader(['ru'], gpu=False, model_storage_directory='/app/data/cache/easyocr', download_enabled=True)" \
 && python -c "import os; assert os.listdir('/app/data/cache/easyocr'), 'EasyOCR models not downloaded!'"

COPY app ./app
COPY src ./src
COPY scripts ./scripts

RUN mkdir -p /app/storage /app/data/cache/easyocr

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
