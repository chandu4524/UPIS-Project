# Deploy GPIP with OCR on Render

## Why Docker is required

OCR uses **system binaries**, not only Python packages:

| Capability | Python package | System binary |
|------------|----------------|---------------|
| Images (JPG/PNG) | `pytesseract` | `tesseract` |
| Scanned PDF | `pdf2image` | Poppler `pdftoppm` |

Render **Python** runtime does not include these → status shows:

- `Tesseract binary not found on PATH`
- `Poppler utilities not detected on PATH`

**Solution:** deploy using `backend/Dockerfile` (Docker runtime).

---

## Step 1 — Create Render Web Service (Docker)

1. [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**
2. Connect your Git repository
3. Settings:
   - **Name:** `gpip-api`
   - **Runtime:** `Docker`
   - **Dockerfile Path:** `backend/Dockerfile`
   - **Docker Context:** `backend`
   - **Health Check Path:** `/api/ocr/health`
4. **Instance type:** at least **Starter** (512MB+; OCR needs memory for PDFs)

Or use the repo root **`render.yaml`** blueprint (Render → New → Blueprint).

---

## Step 2 — Environment variables

Set in Render → Environment:

| Variable | Value |
|----------|--------|
| `APP_ENV` | `production` |
| `TESSERACT_CMD` | `/usr/bin/tesseract` |
| `POPPLER_PATH` | `/usr/bin` |
| `OCR_FOLDER` | `/tmp/ocr_uploads` |
| `UPLOAD_FOLDER` | `/tmp/uploads` |
| `SECRET_KEY` | (generate strong secret) |
| `DATABASE_URL` | (Postgres connection string) |
| `OCR_REQUEST_TIMEOUT_SECONDS` | `300` |
| `OCR_PDF_DPI` | `150` |
| `OCR_MAX_PAGES` | `15` |
| `OCR_MAX_FILE_BYTES` | `15728640` |
| `REQUEST_TIMEOUT_SECONDS` | `120` |
| `OCR_USE_PADDLE` | `false` |

---

## Step 3 — Verify OCR after deploy

### Public health (no login)

```bash
curl -s https://YOUR-SERVICE.onrender.com/api/ocr/health
```

Expected:

```json
{
  "success": true,
  "ocr_ready": true,
  "tesseract_binary": true,
  "poppler_available": true
}
```

### Authenticated status

```bash
curl -s -H "Authorization: Bearer YOUR_JWT" \
  https://YOUR-SERVICE.onrender.com/api/ocr/status
```

### Upload test

```bash
curl -X POST "https://YOUR-SERVICE.onrender.com/api/ocr/upload" \
  -H "Authorization: Bearer YOUR_JWT" \
  -F "file=@sample.pdf"
```

---

## Step 4 — Frontend

Build static site with:

```env
VITE_API_BASE_URL=https://YOUR-SERVICE.onrender.com/api
```

OCR page will show **"OCR engine ready on server"** when `/api/ocr/status` reports `ocr_ready: true`.

---

## Local Docker test (before Render)

```bash
cd backend
docker build -t gpip-api .
docker run --rm -p 8000:8000 -e APP_ENV=production gpip-api
```

In another terminal:

```bash
curl http://localhost:8000/api/ocr/health
docker run --rm gpip-api python scripts/verify_ocr_runtime.py
```

---

## Render logs

Filter logs for:

- `gpip.ocr.runtime` — binary paths at startup
- `gpip.ocr.api` — upload start/complete/fail with filename, size, elapsed time
- `gpip.ocr` — per-page PDF OCR

---

## Supported file types

- PDF (text and scanned)
- JPG / JPEG
- PNG

Max size default: **15 MB** (`OCR_MAX_FILE_BYTES`).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| OCR not ready on status page | Switch service to **Docker** runtime, redeploy |
| 503 on `/api/ocr/health` | Check build logs — `tesseract` / `pdftoppm` must install |
| Upload timeout | Increase `OCR_REQUEST_TIMEOUT_SECONDS`; use Starter+ plan |
| OOM on large PDF | Lower `OCR_PDF_DPI` to `120`, `OCR_MAX_PAGES` to `10` |

See also: `backend/docs/RENDER_OCR.md`
