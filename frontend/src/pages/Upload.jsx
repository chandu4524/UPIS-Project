import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FileDropZone from '../components/FileDropZone';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import Spinner from '../components/Spinner';
import { uploadCSV } from '../services/uploadService';
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
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState('');
  const [validation, setValidation] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a CSV file');
      return;
    }

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Only CSV files are supported');
      return;
    }

    setError('');
    setMessage('');
    setValidation(null);
    setLoading(true);

    try {
      const res = await uploadCSV(file);
      setMessage(res.message || 'Upload completed with validation results');
      setValidation({
        total_rows: res.total_rows ?? 0,
        valid_rows: res.valid_rows ?? res.rows_imported ?? 0,
        invalid_rows: res.invalid_rows ?? 0,
        duplicate_rows: res.duplicate_rows ?? 0,
        errors: res.errors || [],
        normalization: res.normalization || null,
      });
      setFile(null);
      triggerAppRefresh();
    } catch (err) {
      setError(formatError(err, 'Upload failed'));
      setValidation(null);
    } finally {
      setLoading(false);
    }
  };

  const validationErrors = validation?.errors || [];
  const normalization = validation?.normalization;
  const normalizationPreview = normalization?.preview || [];

  return (
    <Layout>
      {loading && <Loader label="Validating and uploading CSV..." />}

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

          {message && validation && (
            <div className="upload-results" role="status">
              <div className="alert alert-success upload-success">
                <p className="upload-success-title">{message}</p>
              </div>

              <section className="validation-summary-card card" aria-label="Validation summary">
                <h2>Validation summary</h2>
                <div className="validation-stats-grid">
                  <div className="validation-stat">
                    <span className="validation-stat-label">Total rows</span>
                    <span className="validation-stat-value">{validation.total_rows}</span>
                  </div>
                  <div className="validation-stat">
                    <span className="validation-stat-label">Valid rows</span>
                    <span className="validation-badge validation-badge-valid">
                      {validation.valid_rows}
                    </span>
                  </div>
                  <div className="validation-stat">
                    <span className="validation-stat-label">Invalid rows</span>
                    <span className="validation-badge validation-badge-invalid">
                      {validation.invalid_rows}
                    </span>
                  </div>
                  <div className="validation-stat">
                    <span className="validation-stat-label">Duplicate rows</span>
                    <span className="validation-badge validation-badge-warning">
                      {validation.duplicate_rows}
                    </span>
                  </div>
                </div>
              </section>

              {normalization && (
                <section className="normalization-summary-card card" aria-label="Normalization summary">
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
                <section className="normalization-preview-card card" aria-label="Normalization preview">
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

          <FileDropZone
            accept=".csv"
            disabled={loading}
            file={file}
            onFileSelect={setFile}
          />

          <div className="upload-actions">
            <button
              type="button"
              className="btn btn-primary upload-btn"
              onClick={handleUpload}
              disabled={loading || !file}
            >
              {loading ? (
                <Spinner label="Uploading..." inline />
              ) : (
                'Upload CSV'
              )}
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
