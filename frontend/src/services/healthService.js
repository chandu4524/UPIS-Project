import axios from 'axios';
import { getApiBaseUrl } from '../config/apiConfig';

function getHealthUrl() {
  const base = getApiBaseUrl();
  if (base.startsWith('http://') || base.startsWith('https://')) {
    const apiRoot = base.endsWith('/api') ? base : `${base.replace(/\/$/, '')}/api`;
    return `${apiRoot}/health`;
  }
  return '/api/health';
}

let _abortController = null;

/**
 * Health check — no auth; non-blocking; cancels in-flight request on repeat calls.
 */
export async function fetchHealthStatus({ signal } = {}) {
  if (_abortController) {
    _abortController.abort();
  }
  _abortController = new AbortController();
  const mergedSignal = signal || _abortController.signal;

  const { data } = await axios.get(getHealthUrl(), {
    timeout: 8000,
    signal: mergedSignal,
    validateStatus: (status) => status < 600,
  });
  return data;
}

/**
 * Retry health once after a short delay (e.g. after backend restart).
 */
export async function fetchHealthStatusWithRetry(retries = 1, delayMs = 1500) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await fetchHealthStatus();
    } catch (err) {
      if (err?.code === 'ERR_CANCELED') throw err;
      lastError = err;
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
  }
  throw lastError;
}

export function healthBadgeStatus(payload) {
  if (!payload) return 'unknown';
  const app = payload.app_status || payload.status;
  const db = payload.database_status;

  if (app === 'healthy' && db === 'connected') return 'healthy';
  if (app === 'degraded' || db === 'connected') return 'degraded';
  if (app === 'unhealthy' || db === 'error') return 'unhealthy';
  return 'unknown';
}

export const HEALTH_STATUS_LABELS = {
  healthy: 'System online',
  degraded: 'Limited services',
  unhealthy: 'System issue',
  unknown: 'Checking…',
  checking: 'Checking…',
};

/**
 * Poll health in the background without blocking UI render.
 */
export function subscribeHealthPolling(onUpdate, intervalMs = 60000) {
  let cancelled = false;

  const run = async () => {
    if (cancelled) return;
    try {
      const data = await fetchHealthStatus();
      if (!cancelled) onUpdate({ status: healthBadgeStatus(data), payload: data, error: null });
    } catch (err) {
      if (err?.code === 'ERR_CANCELED') return;
      if (!cancelled) {
        onUpdate({
          status: 'unhealthy',
          payload: null,
          error: err,
        });
      }
    }
  };

  run();
  const id = setInterval(run, intervalMs);
  return () => {
    cancelled = true;
    clearInterval(id);
    if (_abortController) {
      _abortController.abort();
      _abortController = null;
    }
  };
}
