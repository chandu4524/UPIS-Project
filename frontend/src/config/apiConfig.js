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
 * Backend login POST URL (not a frontend route — do not use for 401 redirects).
 * FastAPI mounts user_router at app root: POST /login (see user_api.py).
 */
export function getAuthLoginUrl() {
  const apiBase = getApiBaseUrl();

  if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
    try {
      const url = new URL(apiBase);
      return `${url.origin}/login`;
    } catch {
      /* fall through */
    }
  }

  // Local dev: login is at backend root (/login), not under /api.
  // Avoid /api-auth/* — Vite's /api proxy prefix captures /api-auth and forwards 404.
  const backendOrigin = import.meta.env.VITE_BACKEND_ORIGIN;
  const origin =
    backendOrigin != null && String(backendOrigin).trim() !== ''
      ? String(backendOrigin).trim().replace(/\/$/, '')
      : 'http://127.0.0.1:8000';
  return `${origin}/login`;
}
