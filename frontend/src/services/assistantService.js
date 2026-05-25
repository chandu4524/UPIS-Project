import api from '../api/api';

export const SUGGESTED_PROMPTS = [
  'Show top district',
  'Search Chandu',
  'OCR uploads today',
  'Manual review summary',
  'Dashboard analytics summary',
  'Recent audit activity',
];

/**
 * Normalize assistant API payload (handles axios response.data or direct body).
 */
export function parseAssistantResponse(raw) {
  const payload = raw?.data && typeof raw.data === 'object' && raw.data.answer != null
    ? raw.data
    : raw;

  if (!payload || typeof payload !== 'object') {
    return {
      answer: '',
      suggested_actions: [],
      related_links: [],
      intent: '',
      suggested_prompts: SUGGESTED_PROMPTS,
    };
  }

  const answer = payload.answer;
  return {
    answer: typeof answer === 'string' ? answer : answer != null ? String(answer) : '',
    suggested_actions: Array.isArray(payload.suggested_actions)
      ? payload.suggested_actions
      : [],
    related_links: Array.isArray(payload.related_links) ? payload.related_links : [],
    intent: payload.intent || '',
    suggested_prompts: Array.isArray(payload.suggested_prompts)
      ? payload.suggested_prompts
      : SUGGESTED_PROMPTS,
  };
}

export async function sendAssistantQuery(query) {
  const response = await api.post('/assistant/query', { query: query.trim() });
  return parseAssistantResponse(response?.data ?? response);
}
