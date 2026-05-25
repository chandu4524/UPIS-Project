import api from '../api/api';

export async function fetchIntelligenceSearch(query, { limit = 25 } = {}) {
  const { data } = await api.get('/intelligence-search', {
    params: { q: query.trim(), limit },
  });
  return data;
}
