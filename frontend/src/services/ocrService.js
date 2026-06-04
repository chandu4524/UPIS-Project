import api from '../api/api';

/** OCR can run several minutes on large scanned PDFs (Render Docker + Poppler). */
const OCR_UPLOAD_TIMEOUT_MS = 300000;
const OCR_MAX_FILE_BYTES = 15 * 1024 * 1024;

export function validateOcrFileClient(file) {
  if (!file) {
    return 'Please select a PDF or image file';
  }
  const lower = file.name.toLowerCase();
  const ok =
    lower.endsWith('.pdf') ||
    lower.endsWith('.png') ||
    lower.endsWith('.jpg') ||
    lower.endsWith('.jpeg');
  if (!ok) {
    return 'Only PDF or image files are supported (PDF, PNG, JPG, JPEG)';
  }
  if (file.size > OCR_MAX_FILE_BYTES) {
    return `File is too large (max ${OCR_MAX_FILE_BYTES / (1024 * 1024)} MB)`;
  }
  return null;
}

export async function fetchOcrStatus() {
  const { data } = await api.get('/ocr/status');
  return data;
}

/** Public probe (no auth) — same fields as Render health check. */
export async function fetchOcrHealth() {
  const base = api.defaults.baseURL || '/api';
  const url = `${base.replace(/\/$/, '')}/ocr/health`;
  const res = await fetch(url);
  return res.json();
}

export async function uploadOcrPdf(file, { onUploadProgress } = {}) {
  const validationError = validateOcrFileClient(file);
  if (validationError) {
    throw new Error(validationError);
  }

  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post('/ocr/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: OCR_UPLOAD_TIMEOUT_MS,
    onUploadProgress,
  });
  return data;
}

export async function fetchOcrHistory({ page = 1, pageSize = 10 } = {}) {
  const { data } = await api.get('/ocr/history', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function fetchOcrDetail(documentId) {
  const { data } = await api.get(`/ocr/${documentId}`);
  return data;
}
