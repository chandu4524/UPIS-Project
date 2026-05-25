const citizenListeners = new Set();
const dashboardListeners = new Set();
const uploadHistoryListeners = new Set();

export function subscribeCitizenRefresh(callback) {
  citizenListeners.add(callback);
  return () => citizenListeners.delete(callback);
}

export function subscribeDashboardRefresh(callback) {
  dashboardListeners.add(callback);
  return () => dashboardListeners.delete(callback);
}

export function subscribeUploadHistoryRefresh(callback) {
  uploadHistoryListeners.add(callback);
  return () => uploadHistoryListeners.delete(callback);
}

/** Notify citizen list and dashboard to reload after upload or data changes. */
export function triggerAppRefresh() {
  citizenListeners.forEach((cb) => cb());
  dashboardListeners.forEach((cb) => cb());
  uploadHistoryListeners.forEach((cb) => cb());
}

/** @deprecated Use triggerAppRefresh — kept for existing imports */
export function triggerCitizenRefresh() {
  triggerAppRefresh();
}
