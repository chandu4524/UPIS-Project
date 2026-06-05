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

/**
 * Parse and validate an OCR document id before calling the status API.
 * Returns null when id is undefined, null, empty string, NaN, or non-positive.
 */
export function parseOcrDocumentId(documentId) {
  if (documentId === undefined || documentId === null || documentId === '') {
    return null;
  }
  const parsed = Number(documentId);
  if (Number.isNaN(parsed) || !Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

/** Fetch processing status for one OCR document (requires valid integer id). */
export async function fetchOcrStatus(documentId) {
  const id = parseOcrDocumentId(documentId);
  if (id === null) {
    throw new Error('A valid OCR document id is required');
  }
  console.log('OCR document id:', id);
  const { data } = await api.get(`/ocr/status/${id}`);
  return data;
}

/** Alias for fetchOcrStatus. */
export const getOCRStatus = fetchOcrStatus;

/** Public probe (no auth) — runtime OCR readiness for page banner. */
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
  const id = parseOcrDocumentId(documentId);
  if (id === null) {
    throw new Error('A valid OCR document id is required');
  }
  console.log('OCR document id:', id);
  const { data } = await api.get(`/ocr/${id}`);
  return data;
}
