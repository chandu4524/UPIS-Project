import axios from 'axios';
import { getAuthLoginUrl } from '../config/apiConfig';
import { getRoleLabel as roleLabelFromConfig, normalizeRole } from '../config/rbac';
import { logoutAndRedirect } from '../auth/logoutAndRedirect';
import {
  getRole,
  getRoleLabel,
  getUsername,
  isLoggedIn,
  setRole,
  setToken,
  setUsername,
} from '../utils/authStorage';

export const loginUser = async (username, password) => {
  const response = await axios.post(getAuthLoginUrl(), null, {
    params: { username, password },
  });

  if (response.data.access_token) {
    setToken(response.data.access_token);
    setUsername(response.data.username || username);
    const role = normalizeRole(response.data.role);
    setRole(role, response.data.role_label || roleLabelFromConfig(role));
  }

  return response.data;
};

export const logout = () => {
  logoutAndRedirect();
};

export const isAuthenticated = () => isLoggedIn();

export const getStoredUsername = () => getUsername();

export const getStoredRole = () => normalizeRole(getRole());

export const getStoredRoleLabel = () => {
  const stored = getRoleLabel();
  if (stored) return stored;
  return roleLabelFromConfig(getStoredRole());
};
