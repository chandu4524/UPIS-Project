/**
 * @deprecated Import from ../auth/handleUnauthorized or ../auth/logoutAndRedirect instead.
 * Kept for backward-compatible imports across the app.
 */
export {
  SESSION_EXPIRED_MESSAGE,
  handleUnauthorizedIfNeeded,
  isUnauthorizedError,
} from '../auth/handleUnauthorized';

export {
  logoutAndRedirect,
  resetLogoutRedirect,
  resetLogoutRedirect as resetSessionExpiredHandling,
} from '../auth/logoutAndRedirect';
