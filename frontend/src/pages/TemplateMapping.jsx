import { useCallback, useEffect, useMemo, useState } from 'react';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import {
  REQUIRED_FIELD_KEYS,
  STANDARD_FIELDS,
  fetchTemplateById,
  fetchTemplates,
  getMissingRequiredMappings,
  parseCsvHeadersFromFile,
  saveTemplate,
} from '../services/templateMappingService';
import { formatError } from '../utils/formatError';
import { formatUploadedDate } from '../utils/formatDate';
import '../styles/templateMapping.css';

const EMPTY_MAPPING = STANDARD_FIELDS.reduce((acc, { key }) => {
  acc[key] = '';
  return acc;
}, {});

export default function TemplateMapping() {
  const [sourceColumns, setSourceColumns] = useState([]);
  const [mapping, setMapping] = useState({ ...EMPTY_MAPPING });
  const [templates, setTemplates] = useState([]);
  const [templateName, setTemplateName] = useState('');
  const [loadTemplateId, setLoadTemplateId] = useState('');
  const [dragSource, setDragSource] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const missingRequired = useMemo(() => getMissingRequiredMappings(mapping), [mapping]);

  const previewRows = useMemo(
    () =>
      STANDARD_FIELDS.filter(({ key }) => mapping[key]).map(({ key, label }) => ({
        standard: label,
        source: mapping[key],
      })),
    [mapping],
  );

  const loadTemplateList = useCallback(async () => {
    try {
      const data = await fetchTemplates();
      setTemplates(data.templates || []);
    } catch (err) {
      setError(formatError(err, 'Failed to load templates'));
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await loadTemplateList();
      setLoading(false);
    })();
  }, [loadTemplateList]);

  const handleCsvFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    try {
      const headers = await parseCsvHeadersFromFile(file);
      if (!headers.length) {
        setError('Could not read column headers from CSV');
        return;
      }
      setSourceColumns(headers);
      setSuccess(`Loaded ${headers.length} source column(s) from ${file.name}`);
    } catch (err) {
      setError(formatError(err, 'Failed to parse CSV headers'));
    }
    e.target.value = '';
  };

  const handleMappingChange = (fieldKey, sourceColumn) => {
    setMapping((prev) => ({ ...prev, [fieldKey]: sourceColumn }));
  };

  const handleDropOnField = (fieldKey) => {
    if (dragSource) {
      handleMappingChange(fieldKey, dragSource);
      setDragSource(null);
    }
  };

  const handleResetMapping = () => {
    setMapping({ ...EMPTY_MAPPING });
    setTemplateName('');
    setLoadTemplateId('');
    setSuccess('Mapping reset');
    setError('');
  };

  const handleLoadTemplate = async (id) => {
    const templateId = id || loadTemplateId;
    if (!templateId) {
      setError('Select a template to load');
      return;
    }
    setError('');
    setSuccess('');
    try {
      const data = await fetchTemplateById(templateId);
      const loaded = data.template?.mapping || {};
      const next = { ...EMPTY_MAPPING };
      STANDARD_FIELDS.forEach(({ key }) => {
        next[key] = loaded[key] || '';
      });
      setMapping(next);
      setTemplateName(data.template?.template_name || '');
      setSuccess(`Loaded template "${data.template?.template_name}"`);
    } catch (err) {
      setError(formatError(err, 'Failed to load template'));
    }
  };

  const handleSaveTemplate = async () => {
    const name = templateName.trim();
    if (!name) {
      setError('Enter a template name before saving');
      return;
    }
    if (missingRequired.length) {
      setError(`Map required fields before saving: ${missingRequired.join(', ')}`);
      return;
    }
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await saveTemplate(name, mapping);
      setSuccess(`Template "${name}" saved successfully`);
      await loadTemplateList();
    } catch (err) {
      setError(formatError(err, 'Failed to save template'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      {loading && <Loader label="Loading template mapping..." />}

      <div className="template-mapping-page">
        <section className="tm-intro card">
          <h2>Template mapping</h2>
          <p>
            Map uploaded CSV source columns to GPIP standard fields. Load a sample CSV to
            detect headers, then save reusable mapping templates.
          </p>
          <label className="tm-csv-upload">
            <span className="btn btn-secondary">Load source CSV columns</span>
            <input
              type="file"
              accept=".csv"
              onChange={handleCsvFile}
              className="tm-csv-input"
            />
          </label>
        </section>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {missingRequired.length > 0 && (
          <div className="tm-validation-warning" role="alert">
            <strong>Validation warning:</strong> Required field(s) not mapped —{' '}
            {missingRequired.join(', ')}
          </div>
        )}

        <div className="tm-panels">
          <section className="tm-panel tm-panel-source card">
            <h3>Source columns</h3>
            <p className="tm-panel-hint">
              From CSV preview — drag a column onto a standard field or use dropdowns.
            </p>
            {sourceColumns.length ? (
              <ul className="tm-source-list">
                {sourceColumns.map((col) => (
                  <li
                    key={col}
                    draggable
                    onDragStart={() => setDragSource(col)}
                    onDragEnd={() => setDragSource(null)}
                    className={`tm-source-chip ${dragSource === col ? 'dragging' : ''}`}
                  >
                    {col}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="tm-empty-hint">Load a CSV file to see source columns.</p>
            )}
          </section>

          <section className="tm-panel tm-panel-target card">
            <h3>Standard fields</h3>
            <p className="tm-panel-hint">Map each GPIP field to a source column.</p>
            <div className="tm-field-mappings">
              {STANDARD_FIELDS.map(({ key, label, required }) => (
                <div
                  key={key}
                  className={`tm-field-row ${required ? 'required' : ''}`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDropOnField(key)}
                >
                  <label htmlFor={`map-${key}`}>
                    {label}
                    {required && <span className="tm-required">*</span>}
                  </label>
                  <select
                    id={`map-${key}`}
                    value={mapping[key] || ''}
                    onChange={(e) => handleMappingChange(key, e.target.value)}
                    disabled={!sourceColumns.length}
                  >
                    <option value="">— Select column —</option>
                    {sourceColumns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </section>
        </div>

        {previewRows.length > 0 && (
          <section className="tm-preview card">
            <h3>Mapping preview</h3>
            <div className="tm-preview-table-wrap">
              <table className="tm-preview-table">
                <thead>
                  <tr>
                    <th>Standard field</th>
                    <th>Source column</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row) => (
                    <tr key={row.standard}>
                      <td>{row.standard}</td>
                      <td>
                        <code>{row.source}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <section className="tm-actions card">
          <h3>Template actions</h3>
          <div className="tm-actions-row">
            <label>
              Template name
              <input
                type="text"
                placeholder="e.g. Citizen CSV v1"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
              />
            </label>
            <label>
              Load template
              <select
                value={loadTemplateId}
                onChange={(e) => setLoadTemplateId(e.target.value)}
              >
                <option value="">— Select saved template —</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.template_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="tm-actions-buttons">
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSaveTemplate}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Save template'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleLoadTemplate()}
              disabled={!loadTemplateId}
            >
              Load template
            </button>
            <button type="button" className="btn btn-secondary" onClick={handleResetMapping}>
              Reset mapping
            </button>
          </div>
        </section>

        <section className="tm-list card">
          <h3>Saved templates</h3>
          {templates.length ? (
            <ul className="tm-template-list">
              {templates.map((t) => (
                <li key={t.id} className="tm-template-item">
                  <div>
                    <strong>{t.template_name}</strong>
                    <span className="tm-template-date">
                      {formatUploadedDate(t.created_at)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleLoadTemplate(String(t.id))}
                  >
                    Reuse
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="tm-empty-hint">No saved templates yet.</p>
          )}
        </section>
      </div>
    </Layout>
  );
}
