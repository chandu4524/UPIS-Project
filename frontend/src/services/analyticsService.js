import api from '../api/api';

function logLoaded(label, payload) {
  console.log(`[Analytics] ${label} loaded`, payload);
}

function logFailed(label, error) {
  console.warn(`[Analytics] ${label} failed`, error);
}

export async function fetchDashboardSummary() {
  const { data } = await api.get('/analytics/dashboard-summary');
  return data;
}

export async function fetchSourceDistribution() {
  const { data } = await api.get('/analytics/source-distribution');
  return data;
}

export async function fetchValidationDistribution() {
  const { data } = await api.get('/analytics/validation-distribution');
  return data;
}

export async function fetchUploadTrends() {
  const { data } = await api.get('/analytics/upload-trends');
  return data;
}

function normalizeSummary(data) {
  if (!data || typeof data !== 'object') {
    return null;
  }
  return {
    total_uploads: Number(data.total_uploads) || 0,
    total_records: Number(data.total_records) || 0,
    valid_records: Number(data.valid_records) || 0,
    invalid_records: Number(data.invalid_records) || 0,
    duplicate_records: Number(data.duplicate_records) || 0,
    success_rate: Number(data.success_rate) || 0,
  };
}

function toErrorMessage(reason) {
  if (!reason) return 'Request failed';
  if (typeof reason === 'string') return reason;
  if (reason.message) return reason.message;
  if (reason.response?.data?.message) return reason.response.data.message;
  return 'Request failed';
}

/**
 * Fetch all analytics endpoints independently so one failure does not block others.
 */
export async function fetchAnalyticsDashboard() {
  const results = await Promise.allSettled([
    fetchDashboardSummary(),
    fetchSourceDistribution(),
    fetchValidationDistribution(),
    fetchUploadTrends(),
  ]);

  const [summaryResult, sourcesResult, validationResult, trendsResult] = results;

  const errors = {
    summary: null,
    sources: null,
    validation: null,
    trends: null,
  };

  let summary = null;
  if (summaryResult.status === 'fulfilled') {
    summary = normalizeSummary(summaryResult.value);
    logLoaded('summary', summary);
  } else {
    errors.summary = toErrorMessage(summaryResult.reason);
    logFailed('summary', summaryResult.reason);
  }

  let sources = [];
  if (sourcesResult.status === 'fulfilled') {
    const payload = sourcesResult.value;
    sources = Array.isArray(payload?.items) ? payload.items : [];
    logLoaded('source', { count: sources.length });
  } else {
    errors.sources = toErrorMessage(sourcesResult.reason);
    logFailed('source', sourcesResult.reason);
  }

  let validation = [];
  if (validationResult.status === 'fulfilled') {
    const payload = validationResult.value;
    validation = Array.isArray(payload?.items) ? payload.items : [];
    logLoaded('validation', { count: validation.length });
  } else {
    errors.validation = toErrorMessage(validationResult.reason);
    logFailed('validation', validationResult.reason);
  }

  let trends = [];
  if (trendsResult.status === 'fulfilled') {
    const payload = trendsResult.value;
    trends = Array.isArray(payload?.items) ? payload.items : [];
    logLoaded('trends', { count: trends.length });
  } else {
    errors.trends = toErrorMessage(trendsResult.reason);
    logFailed('trends', trendsResult.reason);
  }

  return { summary, sources, validation, trends, errors };
}
