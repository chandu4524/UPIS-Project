import api from '../api/api';

export const fetchDashboard = async () => {
  const { data } = await api.get('/dashboard');
  return data;
};

export const fetchDashboardAnalytics = async () => {
  const { data } = await api.get('/dashboard/analytics');
  return data;
};
