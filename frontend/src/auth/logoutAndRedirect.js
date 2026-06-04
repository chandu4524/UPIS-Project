/** Frontend login route — never use backend /login for navigation. */
export const FRONTEND_LOGIN_ROUTE = '/';

let redirecting = false;

/**
 * Clear all client auth state and hard-navigate to the SPA login route (/).
 * Safe to call multiple times (parallel 401 responses).
 */
export function logoutAndRedirect() {
  if (redirecting || typeof window === 'undefined') {
    return;
  }
  redirecting = true;

  localStorage.removeItem('token');
  localStorage.removeItem('access_token');
  localStorage.removeItem('authToken');
  localStorage.removeItem('user');
  localStorage.clear();
  sessionStorage.clear();

  window.location.replace(FRONTEND_LOGIN_ROUTE);
}

/** Call after a successful login so future 401s can redirect again. */
export function resetLogoutRedirect() {
  redirecting = false;
}
