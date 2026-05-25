const listeners = new Set();

export function subscribeNotify(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function notify(message, type = 'error', durationMs = 5000) {
  const payload = {
    id: `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    message: String(message || 'Something went wrong'),
    type,
    durationMs,
  };
  listeners.forEach((fn) => {
    try {
      fn(payload);
    } catch {
      /* ignore listener errors */
    }
  });
}
