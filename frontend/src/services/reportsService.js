import api from '../api/api';

export async function fetchReports() {
  const { data } = await api.get('/reports');
  return data;
}

export async function fetchReportData(reportKey) {
  const { data } = await api.get(`/reports/${reportKey}`);
  return data;
}

function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function filenameFromDisposition(header, fallback) {
  if (!header) return fallback;
  const match = header.match(/filename="?([^"]+)"?/i);
  return match ? match[1] : fallback;
}

export async function exportReportPdf(reportKey) {
  const response = await api.get('/reports/export/pdf', {
    params: { report: reportKey },
    responseType: 'blob',
  });
  const filename = filenameFromDisposition(
    response.headers['content-disposition'],
    `gpip_${reportKey}_report.pdf`,
  );
  triggerBlobDownload(new Blob([response.data], { type: 'application/pdf' }), filename);
}

export async function exportReportExcel(reportKey) {
  const response = await api.get('/reports/export/excel', {
    params: { report: reportKey },
    responseType: 'blob',
  });
  const filename = filenameFromDisposition(
    response.headers['content-disposition'],
    `gpip_${reportKey}_report.xlsx`,
  );
  triggerBlobDownload(
    new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }),
    filename,
  );
}

export const REPORT_TYPES = ['citizen', 'upload', 'audit', 'district'];

export const REPORT_ICONS = {
  citizen: '👥',
  upload: '📁',
  audit: '⊞',
  district: '🗺',
};

export function isValidReportType(type) {
  return REPORT_TYPES.includes((type || '').toLowerCase());
}
