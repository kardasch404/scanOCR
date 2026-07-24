FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PADDLE_OCR_STRICT_OFFLINE=1
ENV PADDLE_OCR_MODEL_DIR=/app/models
ENV PADDLE_PDX_CACHE_HOME=/app/models/paddlex_cache
ENV PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False
ENV FLAGS_use_mkldnn=0

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    opencv-python-headless==4.8.1.78 \
    paddlepaddle==3.3.1 \
    paddleocr==3.4.0 \
    pyzbar==0.1.9 \
    fastapi==0.111.0 \
    uvicorn==0.30.1 \
    python-multipart==0.0.9

COPY scan_yolo.py api.py /app/
COPY models /app/models

RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
