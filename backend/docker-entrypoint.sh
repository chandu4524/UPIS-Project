#!/bin/sh
set -e

# Render sets PORT; default 8000 for local Docker runs.
export PORT="${PORT:-8000}"

# Debian Docker image paths (set in Dockerfile; allow override on Render).
export TESSERACT_CMD="${TESSERACT_CMD:-/usr/bin/tesseract}"
export POPPLER_PATH="${POPPLER_PATH:-/usr/bin}"

# Writable dirs on ephemeral Render disk
export OCR_FOLDER="${OCR_FOLDER:-/tmp/ocr_uploads}"
export UPLOAD_FOLDER="${UPLOAD_FOLDER:-/tmp/uploads}"

mkdir -p "$OCR_FOLDER" "$UPLOAD_FOLDER" /tmp/data 2>/dev/null || true
export DUCKDB_PATH="${DUCKDB_PATH:-/tmp/data/gpip_analytics.duckdb}"

echo "Starting GPIP API on port ${PORT}"
echo "TESSERACT_CMD=${TESSERACT_CMD}"
echo "POPPLER_PATH=${POPPLER_PATH}"

if command -v tesseract >/dev/null 2>&1; then
  tesseract --version 2>&1 | head -n 1 || true
else
  echo "WARNING: tesseract not in PATH"
fi

if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -v 2>&1 | head -n 1 || true
else
  echo "WARNING: pdftoppm not in PATH"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
