import api from '../api/api';

export async function fetchReviewQueue() {
  const { data } = await api.get('/review');
  return data;
}

export async function approveReview(id) {
  const { data } = await api.post(`/review/${id}/approve`);
  return data;
}

export async function rejectReview(id) {
  const { data } = await api.post(`/review/${id}/reject`);
  return data;
}

export async function mergeReview(id) {
  const { data } = await api.post(`/review/${id}/merge`);
  return data;
}

export function categoryBadgeClass(category) {
  const key = (category || '').toUpperCase();
  if (key.includes('CONFIRMED')) return 'review-badge review-badge-confirmed';
  if (key.includes('PROBABLE')) return 'review-badge review-badge-probable';
  if (key.includes('MANUAL')) return 'review-badge review-badge-manual';
  return 'review-badge';
}
