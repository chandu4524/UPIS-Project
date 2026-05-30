export const UPLOAD_ACCEPT =
  '.csv,.xlsx,.xls,.pdf,.txt,.json,.xml,.png,.jpg,.jpeg';

export const UPLOAD_EXTENSIONS = [
  '.csv',
  '.xlsx',
  '.xls',
  '.pdf',
  '.txt',
  '.json',
  '.xml',
  '.png',
  '.jpg',
  '.jpeg',
];

export const SUPPORTED_FORMATS_MESSAGE =
  'Supported formats: CSV, Excel, PDF, TXT, JSON, XML, PNG, JPG';

export function isAllowedUploadFile(file) {
  const name = file?.name?.toLowerCase() || '';
  return UPLOAD_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function normalizeUploadTypeError(message) {
  if (!message || typeof message !== 'string') {
    return message;
  }
  const lower = message.toLowerCase();
  if (
    lower.includes('only csv') ||
    lower.includes('csv files are') ||
    lower.includes('unsupported file type') ||
    lower.includes('unsupported file format')
  ) {
    return SUPPORTED_FORMATS_MESSAGE;
  }
  return message;
}
