import { logoutAndRedirect } from './logoutAndRedirect';

export const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please sign in again.';

export function isUnauthorizedError(error) {
  return error?.response?.status === 401 || error?.status === 401;
}

/** Returns true when a 401 was handled (redirect triggered). */
export function handleUnauthorizedIfNeeded(error) {
  if (!isUnauthorizedError(error)) {
    return false;
  }
  logoutAndRedirect();
  return true;
}
