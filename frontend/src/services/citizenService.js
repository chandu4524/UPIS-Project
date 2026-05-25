import api from '../api/api';

export async function fetchCitizens({
  name = '',
  mobile = '',
  district = '',
  village = '',
  page = 1,
  pageSize = 10,
  sortBy = 'full_name',
  sortOrder = 'asc',
} = {}) {
  const params = { page, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder };
  if (name?.trim()) params.name = name.trim();
  if (mobile?.trim()) params.mobile = mobile.trim();
  if (district?.trim()) params.district = district.trim();
  if (village?.trim()) params.village = village.trim();

  const { data } = await api.get('/citizens', { params });
  return data;
}

export async function fetchCitizenById(id) {
  const { data } = await api.get(`/citizens/${id}`);
  return data;
}

export async function fetchCitizenRelationships(id) {
  const { data } = await api.get(`/citizens/${id}/relationships`);
  return data;
}
