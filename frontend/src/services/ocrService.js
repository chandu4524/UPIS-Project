import api from '../api/api';

export async function uploadOcrPdf(file, { onUploadProgress } = {}) {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post('/ocr/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
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
