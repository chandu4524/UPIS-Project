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
