# GPIP FastAPI — production image with OCR (Tesseract + Poppler) for Render Docker deploy.
#
# Render dashboard:
#   Runtime: Docker
#   Dockerfile path: backend/Dockerfile  (or ./backend/Dockerfile from repo root)
#   Docker context: backend

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="GPIP API" \
      org.opencontainers.image.description="FastAPI backend with OCR support"

# System OCR dependencies (required for pytesseract + pdf2image)
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && tesseract --version \
    && pdftoppm -v 2>&1 | head -n 1 || true

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application code
COPY app ./app
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Verify OCR binaries at build time (fail build if missing)
RUN test -x /usr/bin/tesseract \
    && test -x /usr/bin/pdftoppm \
    && python -c "import pytesseract, pdf2image; from PIL import Image; print('OCR Python packages OK')"

ENV APP_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    POPPLER_PATH=/usr/bin \
    OCR_FOLDER=/tmp/ocr_uploads \
    UPLOAD_FOLDER=/tmp/uploads \
    OCR_PDF_DPI=150 \
    OCR_MAX_PAGES=15 \
    OCR_MAX_FILE_BYTES=15728640 \
    OCR_REQUEST_TIMEOUT_SECONDS=300 \
    OCR_USE_PADDLE=false \
    REQUEST_TIMEOUT_SECONDS=120

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-8000}/api/ocr/health" | grep -q "\"ocr_ready\":true"' || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
