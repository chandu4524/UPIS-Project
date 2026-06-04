import axios from 'axios';
import { getApiBaseUrl } from '../config/apiConfig';
import { getToken } from '../utils/authStorage';
import { formatError } from '../utils/formatError';
import { notify } from '../utils/notify';
import { logoutAndRedirect } from '../auth/logoutAndRedirect';

const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      logoutAndRedirect();
      return Promise.reject(error);
    }

    const status = error.response?.status;
    if (status === 504) {
      notify(
        formatError(error, 'Request timed out. Please try again.'),
        'warning',
      );
    } else if (status === 403) {
      notify(
        formatError(error, 'You do not have permission for this action.'),
        'warning',
      );
    } else if (status && status >= 500) {
      notify(formatError(error, 'Server error. Please try again shortly.'), 'error');
    } else if (!error.response && error.code === 'ECONNABORTED') {
      notify('Request timed out. Please try again.', 'warning');
    } else if (!error.response) {
      notify('Unable to reach the server. Check your connection.', 'error');
    }
    return Promise.reject(error);
  },
);

export default api;
