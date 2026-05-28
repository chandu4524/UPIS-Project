import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MultiFileDropZone from '../components/MultiFileDropZone';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import Spinner from '../components/Spinner';
import { uploadCSVWithProgress } from '../services/uploadService';
import { triggerAppRefresh } from '../utils/appRefresh';
import { formatError } from '../utils/formatError';
import '../styles/upload.css';

function errorTypeClass(errorType) {
  const key = (errorType || '').toUpperCase();
  if (key.includes('DUPLICATE')) return 'validation-badge validation-badge-warning';
  if (key.includes('INVALID') || key.includes('EMPTY') || key.includes('MISSING')) {
    return 'validation-badge validation-badge-invalid';
  }
  return 'validation-badge';
}

function formatErrorType(errorType) {
  return (errorType || 'ERROR').replace(/_/g, ' ');
}

export default function Upload() {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState('');
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const updateResult = (id, patch) => {
    setResults((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  };

  const handleUpload = async () => {
    if (!files?.length) {
      setError('Please select one or more CSV files');
      return;
    }

    const invalid = files.find((f) => !f?.name?.toLowerCase()?.endsWith('.csv'));
    if (invalid) {
      setError('Only CSV files are supported');
      return;
    }

    if (files.length > 30) {
      setError('You can upload a maximum of 30 files at a time');
      return;
    }

    setError('');
    setMessage('');
    setResults(
      files.map((f, idx) => ({
        id: `${f.name}-${f.size}-${f.lastModified}-${idx}`,
        file: f,
        status: 'queued',
        progress: 0,
        response: null,
        error: null,
      }))
    );
    setLoading(true);

    try {
      setMessage('Uploading files… per-file mapping/normalization/missing summaries will appear as each file finishes.');

      for (const item of files.map((f, idx) => ({
        id: `${f.name}-${f.size}-${f.lastModified}-${idx}`,
        file: f,
      }))) {
        updateResult(item.id, { status: 'uploading', progress: 0, error: null });
        try {
          const res = await uploadCSVWithProgress(item.file, ({ percent }) => {
            if (typeof percent === 'number') updateResult(item.id, { progress: percent });
          });
          updateResult(item.id, { status: 'completed', progress: 100, response: res });
          triggerAppRefresh();
        } catch (err) {
          updateResult(item.id, { status: 'failed', error: formatError(err, 'Upload failed') });
        }
      }

      setFiles([]);
    } catch (err) {
      setError(formatError(err, 'Upload failed'));
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const completedCount = results.filter((r) => r.status === 'completed').length;
  const failedCount = results.filter((r) => r.status === 'failed').length;

  return (
    <Layout>
      {loading && <Loader label="Uploading files and validating data..." />}

      <div className="upload-page-wrap">
        <div className="upload-page card">
          <header className="upload-header">
            <h1>Data quality validation upload</h1>
            <p>
              Upload citizen data in CSV format. Valid rows are imported; invalid and
              duplicate rows are reported in the validation summary.
            </p>
          </header>

          {error && (
            <div className="alert alert-error" role="alert">
              {error}
            </div>
          )}

          {message && results?.length > 0 && (
            <div className="upload-results" role="status">
              <div className="alert alert-success upload-success">
                <p className="upload-success-title">{message}</p>
                <p style={{ marginTop: 8, opacity: 0.85 }}>
                  Completed: {completedCount} • Failed: {failedCount} • Total: {results.length}
                </p>
              </div>

              {results.map((r) => {
                const res = r.response;
                const validationErrors = res?.errors || [];
                const normalization = res?.normalization;
                const normalizationPreview = normalization?.preview || [];
                const missingValues = res?.missing_values || null;
                const mapping = res?.column_mapping || null;

                return (
                  <section
                    key={r.id}
                    className="validation-summary-card card"
                    aria-label={`Upload result ${r.file?.name || ''}`}
                    style={{ marginTop: 12 }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                      <h2 style={{ margin: 0, fontSize: 18 }}>{r.file?.name}</h2>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        {r.status === 'uploading' && (
                          <span className="validation-badge">{r.progress ?? 0}%</span>
                        )}
                        {r.status === 'queued' && <span className="validation-badge">Queued</span>}
                        {r.status === 'completed' && (
                          <span className="validation-badge validation-badge-valid">Completed</span>
                        )}
                        {r.status === 'failed' && (
                          <span className="validation-badge validation-badge-invalid">Failed</span>
                        )}
                      </div>
                    </div>

                    {r.error && (
                      <div className="alert alert-error" role="alert" style={{ marginTop: 10 }}>
                        {r.error}
                      </div>
                    )}

                    {r.status === 'uploading' && (
                      <div style={{ marginTop: 10 }}>
                        <Spinner label="Uploading..." inline />
                      </div>
                    )}

                    {res && (
                      <>
                        <div className="validation-stats-grid" style={{ marginTop: 12 }}>
                          <div className="validation-stat">
                            <span className="validation-stat-label">Total rows</span>
                            <span className="validation-stat-value">{res.total_rows ?? 0}</span>
                          </div>
                          <div className="validation-stat">
                            <span className="validation-stat-label">Valid rows</span>
                            <span className="validation-badge validation-badge-valid">
                              {res.valid_rows ?? res.rows_imported ?? 0}
                            </span>
                          </div>
                          <div className="validation-stat">
                            <span className="validation-stat-label">Invalid rows</span>
                            <span className="validation-badge validation-badge-invalid">
                              {res.invalid_rows ?? 0}
                            </span>
                          </div>
                          <div className="validation-stat">
                            <span className="validation-stat-label">Duplicate rows</span>
                            <span className="validation-badge validation-badge-warning">
                              {res.duplicate_rows ?? 0}
                            </span>
                          </div>
                        </div>

                        {mapping && Object.keys(mapping).length > 0 && (
                          <section
                            className="normalization-preview-card card"
                            aria-label="Column mapping"
                            style={{ marginTop: 12 }}
                          >
                            <div className="normalization-preview-header">
                              <h2>Column mapping</h2>
                              <span className="normalization-preview-count">
                                {Object.keys(mapping).length} mapped
                              </span>
                            </div>
                            <div className="normalization-preview-table-wrap">
                              <table className="normalization-preview-table">
                                <thead>
                                  <tr>
                                    <th>CSV header</th>
                                    <th>Mapped to</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {Object.entries(mapping).map(([from, to]) => (
                                    <tr key={`${from}-${to}`}>
                                      <td className="norm-original">{from}</td>
                                      <td className="norm-normalized">{to}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}

                        {missingValues && (
                          <section
                            className="normalization-preview-card card"
                            aria-label="Missing values summary"
                            style={{ marginTop: 12 }}
                          >
                            <div className="normalization-preview-header">
                              <h2>Missing values</h2>
                              <span className="normalization-preview-count">Required fields only</span>
                            </div>
                            <div className="normalization-preview-table-wrap">
                              <table className="normalization-preview-table">
                                <thead>
                                  <tr>
                                    <th>Field</th>
                                    <th>Missing</th>
                                    <th>%</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {Object.entries(missingValues).map(([field, info]) => (
                                    <tr key={field}>
                                      <td>{field.replace(/_/g, ' ')}</td>
                                      <td className="norm-original">{info?.missing ?? 0}</td>
                                      <td className="norm-normalized">
                                        {typeof info?.percent === 'number'
                                          ? `${info.percent.toFixed(2)}%`
                                          : '0.00%'}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}

                        {normalization && (
                          <section
                            className="normalization-summary-card card"
                            aria-label="Normalization summary"
                            style={{ marginTop: 12 }}
                          >
                            <h2>Normalization summary</h2>
                            <div className="normalization-stats-grid">
                              <div className="normalization-stat">
                                <span className="normalization-stat-label">Names normalized</span>
                                <span className="normalization-badge normalization-badge-success">
                                  {normalization.names_normalized ?? 0}
                                </span>
                              </div>
                              <div className="normalization-stat">
                                <span className="normalization-stat-label">Phones normalized</span>
                                <span className="normalization-badge normalization-badge-success">
                                  {normalization.phones_normalized ?? 0}
                                </span>
                              </div>
                              <div className="normalization-stat">
                                <span className="normalization-stat-label">Dates normalized</span>
                                <span className="normalization-badge normalization-badge-success">
                                  {normalization.dates_normalized ?? 0}
                                </span>
                              </div>
                              <div className="normalization-stat">
                                <span className="normalization-stat-label">Matching keys generated</span>
                                <span className="normalization-badge normalization-badge-success">
                                  {normalization.matching_keys_generated ?? 0}
                                </span>
                              </div>
                            </div>
                          </section>
                        )}

                        {normalizationPreview.length > 0 && (
                          <section
                            className="normalization-preview-card card"
                            aria-label="Normalization preview"
                            style={{ marginTop: 12 }}
                          >
                            <div className="normalization-preview-header">
                              <h2>Normalization preview</h2>
                              <span className="normalization-preview-count">
                                {normalizationPreview.length} change(s) shown
                              </span>
                            </div>
                            <div className="normalization-preview-table-wrap">
                              <table className="normalization-preview-table">
                                <thead>
                                  <tr>
                                    <th>Row</th>
                                    <th>Field</th>
                                    <th>Original value</th>
                                    <th>Normalized value</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {normalizationPreview.map((item, idx) => (
                                    <tr key={`${item.row_number}-${item.field}-${idx}`}>
                                      <td>{item.row_number}</td>
                                      <td>{item.field?.replace(/_/g, ' ')}</td>
                                      <td className="norm-original">{item.original}</td>
                                      <td className="norm-normalized">{item.normalized}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}

                        {validationErrors.length > 0 && (
                          <section className="validation-errors-card card" aria-label="Error preview">
                            <div className="validation-errors-header">
                              <h2>Error preview</h2>
                              <span className="validation-errors-count">
                                {validationErrors.length} issue(s) shown
                              </span>
                            </div>
                            <div className="validation-errors-table-wrap">
                              <table className="validation-errors-table">
                                <thead>
                                  <tr>
                                    <th>Row number</th>
                                    <th>Error type</th>
                                    <th>Description</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {validationErrors.map((item, idx) => (
                                    <tr key={`${item.row_number}-${item.error_type}-${idx}`}>
                                      <td>{item.row_number}</td>
                                      <td>
                                        <span className={errorTypeClass(item.error_type)}>
                                          {formatErrorType(item.error_type)}
                                        </span>
                                      </td>
                                      <td>{item.description}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}
                      </>
                    )}
                  </section>
                );
              })}

              <div className="upload-success-actions">
                <button
                  type="button"
                  className="btn btn-primary upload-view-btn"
                  onClick={() => navigate('/upload-history')}
                >
                  View upload history
                </button>
                <button
                  type="button"
                  className="btn btn-secondary upload-view-btn"
                  onClick={() => navigate('/citizens')}
                >
                  View citizen records
                </button>
                <button
                  type="button"
                  className="btn btn-secondary upload-view-btn"
                  onClick={() => navigate('/dashboard')}
                >
                  Back to dashboard
                </button>
              </div>
            </div>
          )}

          <div className="upload-instructions">
            <strong>Required columns:</strong> full_name, mobile, district, village, dob
            <br />
            <strong>DOB format:</strong> DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD
          </div>

          <MultiFileDropZone
            accept=".csv"
            disabled={loading}
            files={files}
            onFilesChange={setFiles}
            maxFiles={30}
          />

          <div className="upload-actions">
            <button
              type="button"
              className="btn btn-primary upload-btn"
              onClick={handleUpload}
              disabled={loading || !files?.length}
            >
              {loading ? (
                <Spinner label="Uploading..." inline />
              ) : (
                'Upload CSV files'
              )}
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
