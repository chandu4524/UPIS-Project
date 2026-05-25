/**
 * API base URL from Vite env. Defaults to /api for local dev (Vite proxy).
 * Production example: VITE_API_BASE_URL=http://127.0.0.1:8000/api
 */
export function getApiBaseUrl() {
  const raw = import.meta.env.VITE_API_BASE_URL;
  if (raw != null && String(raw).trim() !== '') {
    return String(raw).trim().replace(/\/$/, '');
  }
  return '/api';
}

/**
 * Login endpoint base (not under /api prefix on the backend).
 */
export function getAuthLoginUrl() {
  const apiBase = getApiBaseUrl();
  if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
    try {
      const url = new URL(apiBase);
      return `${url.origin}/login`;
    } catch {
      return '/login';
    }
  }
  return '/login';
}
