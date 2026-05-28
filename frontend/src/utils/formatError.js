/**
 * Extract a user-friendly message from API / network errors.
 */
export function formatError(err, fallback = 'Something went wrong. Please try again.') {
  if (!err) return fallback;

  if (err.code === 'ECONNABORTED') {
    return 'The request timed out. Please check your connection and try again.';
  }

  if (!err.response) {
    if (err.message?.includes('Network Error')) {
      return 'Unable to reach the server. Check your connection and try again.';
    }
    return err.message || fallback;
  }

  const data = err.response?.data;
  if (data?.message && typeof data.message === 'string') {
    const detail = data?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const missingCols = detail.missing_columns;
      const ambiguousCols = detail.ambiguous_columns;
      const foundCols = detail.found_columns;
      if (Array.isArray(missingCols) && missingCols.length) {
        return `${data.message} (Missing: ${missingCols.join(', ')})`;
      }
      if (Array.isArray(ambiguousCols) && ambiguousCols.length) {
        return `${data.message} (Ambiguous: ${ambiguousCols.join(', ')})`;
      }
      if (Array.isArray(foundCols) && foundCols.length && data.message?.toLowerCase().includes('missing')) {
        return `${data.message} (Found: ${foundCols.join(', ')})`;
      }
    }
    return data.message;
  }

  const detail = data?.detail;
  if (!detail) {
    return fallback;
  }

  if (typeof detail === 'string') {
    return detail;
  }

  if (typeof detail === 'object' && detail.message) {
    return detail.message;
  }

  if (Array.isArray(detail)) {
    const parts = detail.map(
      (item) => item.message || item.msg || (typeof item === 'string' ? item : null),
    ).filter(Boolean);
    if (parts.length) return parts.join(', ');
  }

  return fallback;
}
