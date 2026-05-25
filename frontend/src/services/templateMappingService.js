import api from '../api/api';

export const STANDARD_FIELDS = [
  { key: 'full_name', label: 'Full name', required: true },
  { key: 'mobile', label: 'Mobile', required: true },
  { key: 'dob', label: 'Date of birth', required: true },
  { key: 'district', label: 'District', required: true },
  { key: 'village', label: 'Village', required: true },
  { key: 'father_name', label: 'Father name', required: false },
];

export const REQUIRED_FIELD_KEYS = STANDARD_FIELDS.filter((f) => f.required).map((f) => f.key);

export async function fetchTemplates() {
  const { data } = await api.get('/template-mapping');
  return data;
}

export async function fetchTemplateById(id) {
  const { data } = await api.get(`/template-mapping/${id}`);
  return data;
}

export async function saveTemplate(templateName, mapping) {
  const { data } = await api.post('/template-mapping/save', {
    template_name: templateName,
    mapping,
  });
  return data;
}

export function parseCsvHeadersFromText(text) {
  const firstLine = (text || '').split(/\r?\n/)[0];
  if (!firstLine) return [];
  const headers = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < firstLine.length; i += 1) {
    const char = firstLine[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      headers.push(current.trim().replace(/^"|"$/g, ''));
      current = '';
    } else {
      current += char;
    }
  }
  headers.push(current.trim().replace(/^"|"$/g, ''));
  return headers.filter(Boolean);
}

export async function parseCsvHeadersFromFile(file) {
  const chunk = file.slice(0, 8192);
  const text = await chunk.text();
  return parseCsvHeadersFromText(text);
}

export function getMissingRequiredMappings(mapping) {
  return REQUIRED_FIELD_KEYS.filter((key) => !(mapping[key] || '').trim());
}
