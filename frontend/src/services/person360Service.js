import api from '../api/api';

export async function fetchPerson360Profile(citizenId) {
  const { data } = await api.get(`/citizens/${citizenId}/profile-360`);
  return data;
}

export async function searchPersons(params = {}) {
  const { data } = await api.get('/persons/search', { params });
  return data;
}
