export const TOKEN_KEY = 'gpip_jwt_token';
export const USERNAME_KEY = 'gpip_username';
export const ROLE_KEY = 'gpip_role';
export const ROLE_LABEL_KEY = 'gpip_role_label';

const LEGACY_TOKEN_KEY = 'token';
const LEGACY_USERNAME_KEY = 'username';

const AUTH_STORAGE_KEYS = [
  TOKEN_KEY,
  LEGACY_TOKEN_KEY,
  USERNAME_KEY,
  LEGACY_USERNAME_KEY,
  ROLE_KEY,
  ROLE_LABEL_KEY,
];

export function getToken() {
  return (
    localStorage.getItem(TOKEN_KEY) ||
    localStorage.getItem(LEGACY_TOKEN_KEY) ||
    sessionStorage.getItem(TOKEN_KEY) ||
    sessionStorage.getItem(LEGACY_TOKEN_KEY)
  );
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(LEGACY_TOKEN_KEY);
}

export function getUsername() {
  return (
    localStorage.getItem(USERNAME_KEY) ||
    localStorage.getItem(LEGACY_USERNAME_KEY) ||
    sessionStorage.getItem(USERNAME_KEY) ||
    sessionStorage.getItem(LEGACY_USERNAME_KEY)
  );
}

export function setUsername(username) {
  localStorage.setItem(USERNAME_KEY, username);
  localStorage.removeItem(LEGACY_USERNAME_KEY);
  sessionStorage.removeItem(USERNAME_KEY);
  sessionStorage.removeItem(LEGACY_USERNAME_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY) || sessionStorage.getItem(ROLE_KEY) || '';
}

export function getRoleLabel() {
  return (
    localStorage.getItem(ROLE_LABEL_KEY) ||
    sessionStorage.getItem(ROLE_LABEL_KEY) ||
    ''
  );
}

export function setRole(role, roleLabel) {
  if (role) localStorage.setItem(ROLE_KEY, role);
  if (roleLabel) localStorage.setItem(ROLE_LABEL_KEY, roleLabel);
  sessionStorage.removeItem(ROLE_KEY);
  sessionStorage.removeItem(ROLE_LABEL_KEY);
}

export function clearAuth() {
  for (const key of AUTH_STORAGE_KEYS) {
    localStorage.removeItem(key);
    try {
      sessionStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  }
}

export function isLoggedIn() {
  return !!getToken();
}
