import api from '../api/api';

export async function fetchDataSources({ activeOnly = false } = {}) {
  const { data } = await api.get('/data-sources', {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function createDataSource(payload) {
  const { data } = await api.post('/data-sources', payload);
  return data;
}

export async function updateDataSource(id, payload) {
  const { data } = await api.put(`/data-sources/${id}`, payload);
  return data;
}

export async function deleteDataSource(id) {
  const { data } = await api.delete(`/data-sources/${id}`);
  return data;
}
