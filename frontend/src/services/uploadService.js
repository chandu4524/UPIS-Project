import api from '../api/api';

export async function fetchUploadHistory({ page = 1, pageSize = 10 } = {}) {
  const { data } = await api.get('/uploads', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export const uploadCSV = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post('/upload-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return data;
};

export const uploadCSVWithProgress = async (file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post('/upload-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (!onProgress) return;
      const total = evt.total || 0;
      const loaded = evt.loaded || 0;
      const percent = total ? Math.round((loaded / total) * 100) : null;
      onProgress({ loaded, total, percent });
    },
  });

  return data;
};

export const uploadCSVFiles = async (files, { dataSourceId } = {}) => {
  const formData = new FormData();
  (files || []).forEach((f) => formData.append('files', f));
  if (dataSourceId) {
    formData.append('data_source_id', String(dataSourceId));
  }

  const { data } = await api.post('/upload-files', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};
