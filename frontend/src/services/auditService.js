import api from '../api/api';

export async function fetchAuditLogs({ page = 1, pageSize = 15 } = {}) {
  const { data } = await api.get('/audit-logs', {
    params: { page, page_size: pageSize },
  });
  return data;
}

const ACTION_LABELS = {
  LOGIN: 'Login',
  UPLOAD_FILE: 'Upload file',
  VIEW_PROFILE: 'View profile',
  OPEN_RELATIONSHIP_GRAPH: 'Open relationship graph',
  CITIZEN_SEARCH: 'Citizen search',
  CREATE_USER: 'Create user',
  UPDATE_USER: 'Update user',
  RESET_PASSWORD: 'Reset password',
  DISABLE_USER: 'Disable user',
};

export function formatActionType(actionType) {
  return ACTION_LABELS[actionType] || actionType?.replace(/_/g, ' ') || '—';
}

export function formatEntity(row) {
  const type = row.entity_type || '';
  const id = row.entity_id;
  if (!type) return '—';
  if (!id) return type;
  return `${type} (${id})`;
}
