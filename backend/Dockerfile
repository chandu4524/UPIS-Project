# GPIP FastAPI — production image with OCR (Tesseract + Poppler) for Render Docker deploy.
#
# Render Web Service settings:
#   Runtime:          Docker
#   Dockerfile path:  backend/Dockerfile
#   Docker context:   backend
#
# Do NOT use Render "Python" native runtime — apt-get fails (read-only filesystem)
# and Tesseract/Poppler are not preinstalled.

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
COPY scripts ./scripts
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Fail the image build if OCR stack is incomplete (same checks as /api/ocr/health)
RUN test -x /usr/bin/tesseract \
    && test -x /usr/bin/pdftoppm \
    && python -c "\
import os; \
import pytesseract; \
from pdf2image import convert_from_path; \
from PIL import Image; \
pytesseract.pytesseract.tesseract_cmd = os.environ.get('TESSERACT_CMD', '/usr/bin/tesseract'); \
v = pytesseract.get_tesseract_version(); \
assert v, 'tesseract version empty'; \
assert os.path.isfile('/usr/bin/pdftoppm'), 'pdftoppm missing'; \
print('OCR build verification OK — tesseract', v)\
"

ENV APP_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000 \
    TESSERACT_CMD=/usr/bin/tesseract \
    POPPLER_PATH=/usr/bin \
    OCR_FOLDER=/tmp/ocr_uploads \
    UPLOAD_FOLDER=/tmp/uploads \
    OCR_PDF_DPI=150 \
    OCR_MAX_PAGES=15 \
    OCR_MAX_FILE_BYTES=15728640 \
    OCR_REQUEST_TIMEOUT_SECONDS=300 \
    OCR_USE_PADDLE=false \
    REQUEST_TIMEOUT_SECONDS=120 \
    DUCKDB_PATH=/tmp/data/gpip_analytics.duckdb \
    ENABLE_DEMO_SEED=false

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-10000}/api/ocr/health" | grep -q "\"ocr_ready\":true"' || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
