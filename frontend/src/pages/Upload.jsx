import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MultiFileDropZone from '../components/MultiFileDropZone';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import Spinner from '../components/Spinner';
import {
  SUPPORTED_FORMATS_MESSAGE,
  UPLOAD_ACCEPT,
  isAllowedUploadFile,
} from '../constants/uploadFormats';
import { fetchDataSources } from '../services/dataSourceService';
import { uploadCSVFiles } from '../services/uploadService';
import { triggerAppRefresh } from '../utils/appRefresh';
import { formatError } from '../utils/formatError';
import '../styles/upload.css';

export default function Upload() {
  const navigate = useNavigate();

  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState('');
  const [warning, setWarning] = useState('');
  const [validationNotice, setValidationNotice] = useState('');
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [dataSources, setDataSources] = useState([]);
  const [selectedSourceId, setSelectedSourceId] = useState('');

  useEffect(() => {
    let mounted = true;
    fetchDataSources({ activeOnly: true })
      .then((data) => {
        if (!mounted) return;
        setDataSources(Array.isArray(data?.items) ? data.items : []);
      })
      .catch(() => {
        if (mounted) setDataSources([]);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleUpload = async () => {
    if (!files?.length) {
      setError('Please select one or more files to upload');
      return;
    }

    const invalid = files.find((f) => !isAllowedUploadFile(f));

    if (invalid) {
      setError(SUPPORTED_FORMATS_MESSAGE);
      return;
    }

    if (files.length > 30) {
      setError('You can upload a maximum of 30 files at a time');
      return;
    }

    setError('');
    setMessage('');
    setWarning('');
    setValidationNotice('');
    setLoading(true);

    setResults(
      files.map((f, idx) => ({
        id: `${f.name}-${f.size}-${f.lastModified}-${idx}`,
        file: f,
        status: 'uploading',
        progress: 100,
        response: null,
        error: null,
      }))
    );

    try {
      setMessage('Uploading files and validating data...');

      const response = await uploadCSVFiles(files, {
        dataSourceId: selectedSourceId ? Number(selectedSourceId) : null,
      });
      const fileResults = Array.isArray(response?.items) ? response.items : [];

      setResults((prev) =>
        prev.map((r, idx) => {
          const item = fileResults[idx];
          const uploadOk = item?.upload_success === true || item?.status === 'success';
          return {
            ...r,
            status: uploadOk ? 'completed' : 'failed',
            progress: 100,
            response: item || null,
            error: uploadOk ? null : (item?.error || item?.message || 'Upload failed'),
            analyticsWarning: uploadOk ? (item?.analytics_warning || null) : null,
            validationWarning: uploadOk
              ? (item?.validation_warning || null)
              : null,
          };
        })
      );

      const succeeded = fileResults.filter(
        (item) => item?.upload_success === true || item?.status === 'success'
      ).length;
      const failed = fileResults.length - succeeded;
      const analyticsWarnings = fileResults
        .filter(
          (item) =>
            (item?.upload_success === true || item?.status === 'success') &&
            item?.analytics_warning
        )
        .map((item) => item.analytics_warning);
      const validationWarnings = fileResults
        .filter(
          (item) =>
            (item?.upload_success === true || item?.status === 'success') &&
            item?.validation_warning
        )
        .map((item) => item.validation_warning);

      if (failed > 0 && succeeded === 0) {
        setError(`All uploads failed (${failed} file(s)). See details below.`);
      } else if (failed > 0) {
        setMessage(`${succeeded} file(s) uploaded successfully, ${failed} failed.`);
      } else {
        setMessage(response?.message || 'All files uploaded successfully.');
      }

      if (validationWarnings.length > 0) {
        setValidationNotice(
          response?.validation_warning ||
            validationWarnings[0] ||
            'Some duplicate records were skipped during validation.'
        );
      }

      if (analyticsWarnings.length > 0) {
        setWarning(
          response?.analytics_warning ||
            analyticsWarnings[0] ||
            'Upload succeeded; analytics sync reported warnings.'
        );
      }

      triggerAppRefresh();
      setFiles([]);
    } catch (err) {
      setError(formatError(err, 'Upload failed'));

      setResults((prev) =>
        prev.map((r) => ({
          ...r,
          status: 'failed',
          error: formatError(err, 'Upload failed'),
        }))
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      {loading && <Loader label="Uploading files and validating data..." />}

      <div className="upload-page-wrap">
        <div className="upload-page card">
          <header className="upload-header">
            <h1>Data Quality Validation Upload</h1>
            <p>
              Upload multiple files for validation and processing.{' '}
              {SUPPORTED_FORMATS_MESSAGE}.
            </p>
          </header>

          {error && (
            <div className="alert alert-error">
              {error}
            </div>
          )}

          {message && (
            <div className="alert alert-success">
              {message}
            </div>
          )}

          {warning && (
            <div className="alert alert-warning">
              Upload completed. Analytics note: {warning}
            </div>
          )}

          {validationNotice && (
            <div className="alert alert-warning">
              {validationNotice}
            </div>
          )}

          <div className="upload-source-field" style={{ marginBottom: 16 }}>
            <label htmlFor="data-source-select" style={{ display: 'block', marginBottom: 6, fontWeight: 600 }}>
              Data source (optional)
            </label>
            <select
              id="data-source-select"
              value={selectedSourceId}
              onChange={(e) => setSelectedSourceId(e.target.value)}
              disabled={loading}
              style={{ width: '100%', maxWidth: 420, padding: '8px 10px', borderRadius: 8, border: '1px solid #d8dee9' }}
            >
              <option value="">— No source selected —</option>
              {dataSources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.source_name} ({source.source_code})
                </option>
              ))}
            </select>
          </div>

          <MultiFileDropZone
            accept={UPLOAD_ACCEPT}
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
                'Upload Files'
              )}
            </button>
          </div>

          {results.length > 0 && (
            <div style={{ marginTop: 20 }}>
              {results.map((r) => (
                <div
                  key={r.id}
                  className="card"
                  style={{
                    marginBottom: 12,
                    padding: 12,
                    border: '1px solid #ddd',
                    borderRadius: 8,
                  }}
                >
                  <strong>{r.file?.name}</strong>

                  <div style={{ marginTop: 8 }}>
                    Status:{' '}
                    {r.status === 'completed'
                      ? 'Completed'
                      : r.status === 'failed'
                      ? 'Failed'
                      : 'Uploading'}
                  </div>

                  {r.response?.rows_processed != null && r.status === 'completed' && (
                    <div style={{ marginTop: 8 }}>
                      Rows processed: {r.response.rows_processed}
                    </div>
                  )}

                  {r.response?.validation_results && r.status === 'completed' && (
                    <div style={{ marginTop: 8, opacity: 0.9 }}>
                      Inserted: {r.response.validation_results.inserted_records ?? r.response.validation_results.rows_imported ?? '—'} · Invalid:{' '}
                      {r.response.validation_results.invalid_rows ?? '—'} · Skipped duplicates:{' '}
                      {r.response.validation_results.skipped_duplicates ?? r.response.validation_results.duplicate_rows ?? '—'}
                    </div>
                  )}

                  {(r.validationWarning || r.response?.validation_warning) && r.status === 'completed' && (
                    <div
                      style={{
                        marginTop: 8,
                        color: '#854d0e',
                      }}
                    >
                      Validation: {r.validationWarning || r.response.validation_warning}
                    </div>
                  )}

                  {(r.analyticsWarning || r.response?.analytics_warning) && r.status === 'completed' && (
                    <div
                      style={{
                        marginTop: 8,
                        color: '#8a6d1f',
                      }}
                    >
                      Analytics: {r.analyticsWarning || r.response.analytics_warning}
                    </div>
                  )}

                  {r.response?.message && r.status === 'completed' && (
                    <div style={{ marginTop: 8, opacity: 0.85 }}>
                      {r.response.message}
                    </div>
                  )}

                  {r.error && (
                    <div
                      style={{
                        marginTop: 8,
                        color: 'red',
                      }}
                    >
                      {r.error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: 20 }}>
            <button
              className="btn btn-secondary"
              onClick={() => navigate('/upload-history')}
            >
              View Upload History
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
}