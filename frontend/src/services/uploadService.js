import api from '../api/api';

const JOB_POLL_INTERVAL_MS = 2000;
const JOB_POLL_MAX_ATTEMPTS = 450;

const TERMINAL_JOB_STATUSES = new Set(['completed', 'partial_failure', 'failed']);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchUploadHistory({ page = 1, pageSize = 10 } = {}) {
  const { data } = await api.get('/uploads', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function fetchUploadJobStatus(jobId) {
  const { data } = await api.get(`/upload-jobs/${jobId}`);
  return data;
}

async function pollUploadJob(jobId, { onJobProgress } = {}) {
  for (let attempt = 0; attempt < JOB_POLL_MAX_ATTEMPTS; attempt += 1) {
    const data = await fetchUploadJobStatus(jobId);
    if (onJobProgress) {
      onJobProgress(data);
    }
    const status = data?.status || data?.batch?.status;
    if (TERMINAL_JOB_STATUSES.has(status)) {
      return data;
    }
    await sleep(JOB_POLL_INTERVAL_MS);
  }
  throw new Error('Upload job timed out while waiting for background processing.');
}

export const uploadCSV = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post('/upload-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return data;
};

export const uploadCSVWithProgress = async (file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post('/upload-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (!onProgress) return;
      const total = evt.total || 0;
      const loaded = evt.loaded || 0;
      const percent = total ? Math.round((loaded / total) * 100) : null;
      onProgress({ loaded, total, percent });
    },
  });

  return data;
};

export const uploadCSVFiles = async (files, { dataSourceId, onJobProgress } = {}) => {
  const formData = new FormData();
  (files || []).forEach((f) => formData.append('files', f));
  if (dataSourceId) {
    formData.append('data_source_id', String(dataSourceId));
  }

  const { data } = await api.post('/upload-files', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  });

  const jobId = data?.job_id || data?.batch_id;
  if (data?.async && jobId) {
    return pollUploadJob(jobId, { onJobProgress });
  }

  return data;
};
