# OCR on Render — technical reference

See **`DEPLOY_RENDER_OCR.md`** at the repository root for step-by-step deployment.

## Architecture

- **`app/services/ocr_runtime.py`** — discovers `/usr/bin/tesseract` and Poppler, configures `pytesseract`
- **`app/services/ocr_service.py`** — PDF/image processing
- **`app/api/ocr_api.py`** — `/api/ocr/health`, `/api/ocr/status`, `/api/ocr/upload`
- **`backend/Dockerfile`** — installs `tesseract-ocr` + `poppler-utils`
- **`docker-entrypoint.sh`** — sets env paths and starts uvicorn on `$PORT`

## API endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/ocr/health` | No | Render health; returns `ocr_ready`, `tesseract_binary`, `poppler_available` |
| GET | `/api/ocr/status` | Yes | Same fields for logged-in users |
| POST | `/api/ocr/upload` | Yes | Process PDF/PNG/JPG |

## Environment variables

- `OCR_REQUEST_TIMEOUT_SECONDS` (default 300)
- `OCR_PDF_DPI` (default 150 in production)
- `OCR_MAX_PAGES` (default 15 in Docker)
- `OCR_MAX_FILE_BYTES` (default 15728640)
- `TESSERACT_CMD` (default `/usr/bin/tesseract`)
- `POPPLER_PATH` (default `/usr/bin`)
