import api from '../api/api';

export async function fetchAdminUsers({ page = 1, pageSize = 10 } = {}) {
  const { data } = await api.get('/users', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function createAdminUser(payload) {
  const { data } = await api.post('/users', payload);
  return data;
}

export async function updateAdminUser(userId, payload) {
  const { data } = await api.put(`/users/${userId}`, payload);
  return data;
}

export async function resetAdminUserPassword(userId, password) {
  const { data } = await api.post(`/users/${userId}/reset-password`, { password });
  return data;
}
