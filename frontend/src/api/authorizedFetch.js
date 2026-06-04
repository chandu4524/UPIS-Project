import { getToken } from '../utils/authStorage';
import { handleUnauthorizedIfNeeded } from '../auth/handleUnauthorized';

/**
 * fetch wrapper for non-axios calls — attaches JWT and handles 401 like the axios interceptor.
 */
export async function authorizedFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    handleUnauthorizedIfNeeded({ status: 401 });
    const error = new Error('Unauthorized');
    error.status = 401;
    throw error;
  }

  return response;
}
