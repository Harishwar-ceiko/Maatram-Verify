# Maatram Verify API — deterministic OCR pipeline
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Tesseract + OpenCV system libraries, plus DejaVu fonts used to render the
# deterministic synthetic documents when SEED_ON_START is enabled.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
                fonts-dejavu-core \
    && mkdir -p /usr/bin/tessdata \
    && ln -sf /usr/share/tesseract-ocr/5/tessdata/eng.traineddata /usr/bin/tessdata/eng.traineddata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY assets ./assets
COPY scripts ./scripts
COPY .env.example ./.env.example

# Local fallbacks; Render mounts a persistent disk over /var/data in production.
RUN mkdir -p /app/data /app/reports /app/synthetic

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
