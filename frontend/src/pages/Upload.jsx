import { useState } from 'react';
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
import { uploadCSVFiles } from '../services/uploadService';
import { triggerAppRefresh } from '../utils/appRefresh';
import { formatError } from '../utils/formatError';
import '../styles/upload.css';

export default function Upload() {
  const navigate = useNavigate();

  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState('');
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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

      const response = await uploadCSVFiles(files);
      const fileResults = Array.isArray(response?.items) ? response.items : [];

      setResults((prev) =>
        prev.map((r, idx) => {
          const item = fileResults[idx];
          const failed = item?.status === 'failed';
          return {
            ...r,
            status: failed ? 'failed' : 'completed',
            progress: 100,
            response: item || null,
            error: failed ? (item?.error || item?.message || 'Upload failed') : null,
          };
        })
      );

      const succeeded = fileResults.filter((item) => item?.status === 'success').length;
      const failed = fileResults.filter((item) => item?.status === 'failed').length;

      if (failed > 0 && succeeded === 0) {
        setError(`All uploads failed (${failed} file(s)). See details below.`);
      } else if (failed > 0) {
        setMessage(`${succeeded} file(s) uploaded successfully, ${failed} failed.`);
      } else {
        setMessage(response?.message || 'All files uploaded successfully.');
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