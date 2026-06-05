import { useCallback, useEffect, useState } from 'react';
import FileDropZone from '../components/FileDropZone';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import Pagination from '../components/Pagination';
import Spinner from '../components/Spinner';
import {
  fetchOcrDetail,
  fetchOcrHistory,
  fetchOcrHealth,
  fetchOcrStatus,
  parseOcrDocumentId,
  uploadOcrPdf,
  validateOcrFileClient,
} from '../services/ocrService';
import { formatError } from '../utils/formatError';
import { handleUnauthorizedIfNeeded } from '../auth/handleUnauthorized';
import { formatUploadedDate } from '../utils/formatDate';
import '../styles/ocrProcessing.css';

const PAGE_SIZE = 10;

function confidenceBadgeClass(score) {
  const value = Number(score) || 0;
  if (value >= 80) return 'ocr-confidence-badge ocr-confidence-high';
  if (value >= 50) return 'ocr-confidence-badge ocr-confidence-medium';
  return 'ocr-confidence-badge ocr-confidence-low';
}

function formatConfidence(score) {
  const value = Number(score);
  if (Number.isNaN(value)) return '—';
  return `${value.toFixed(1)}%`;
}

export default function OCRProcessing() {
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [result, setResult] = useState(null);

  const [history, setHistory] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPages, setHistoryPages] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [ocrReady, setOcrReady] = useState(null);
  const [ocrStatusNote, setOcrStatusNote] = useState('');

  const loadOcrRuntimeHealth = useCallback(async () => {
    try {
      const data = await fetchOcrHealth();
      setOcrReady(Boolean(data.ocr_ready));
      const notes = data.dependencies?.notes;
      setOcrStatusNote(Array.isArray(notes) && notes.length ? notes.join(' · ') : '');
    } catch {
      setOcrReady(null);
      setOcrStatusNote('');
    }
  }, []);

  const loadHistory = useCallback(async (pageNum = 1) => {
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const data = await fetchOcrHistory({ page: pageNum, pageSize: PAGE_SIZE });
      setHistory(data.items || []);
      setHistoryTotal(data.total ?? 0);
      setHistoryPages(data.total_pages ?? 0);
      setHistoryPage(data.page ?? pageNum);
    } catch (err) {
      if (handleUnauthorizedIfNeeded(err)) {
        return;
      }
      setHistoryError(formatError(err, 'Failed to load OCR history'));
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory(1);
    loadOcrRuntimeHealth();
  }, [loadHistory, loadOcrRuntimeHealth]);

  const loadDetail = async (documentId) => {
    setSelectedId(documentId);
    setDetailLoading(true);
    setError('');
    try {
      const data = await fetchOcrDetail(documentId);
      setResult({
        id: data.id,
        filename: data.filename,
        extracted_text: data.extracted_text,
        confidence_score: data.confidence_score,
        table_rows: data.table_rows || [],
        json_output: data.json_output,
        created_at: data.created_at,
      });
    } catch (err) {
      if (handleUnauthorizedIfNeeded(err)) {
        setDetailLoading(false);
        return;
      }
      setError(formatError(err, 'Failed to load OCR document'));
    } finally {
      setDetailLoading(false);
    }
  };

  const handleUpload = async () => {
    const validationError = validateOcrFileClient(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (ocrReady === false) {
      setError(
        'OCR is not available on this server (Tesseract/Poppler missing). '
        + 'Deploy the Docker backend image or check /api/health ocr_dependencies.',
      );
      return;
    }

    setError('');
    setSuccess('');
    setResult(null);
    setUploadProgress(0);
    setUploading(true);
    setProcessing(false);

    try {
      const data = await uploadOcrPdf(file, {
        onUploadProgress: (event) => {
          if (event.total) {
            const pct = Math.round((event.loaded * 100) / event.total);
            setUploadProgress(pct);
            if (pct >= 100) {
              setProcessing(true);
            }
          }
        },
      });
      setSuccess(data.message || 'PDF processed successfully');
      const uploadDocumentId = parseOcrDocumentId(data.id);
      setResult({
        id: data.id,
        filename: data.filename,
        extracted_text: data.extracted_text,
        confidence_score: data.confidence_score,
        table_rows: data.table_rows || [],
        pages_processed: data.pages_processed,
        ocr_engine: data.ocr_engine,
        json_output: data.json_output,
      });
      setFile(null);
      loadHistory(1);
      if (uploadDocumentId !== null) {
        try {
          await fetchOcrStatus(uploadDocumentId);
        } catch (statusErr) {
          if (!handleUnauthorizedIfNeeded(statusErr)) {
            console.warn('[OCR] post-upload status check failed', statusErr);
          }
        }
      }
    } catch (err) {
      if (handleUnauthorizedIfNeeded(err)) {
        return;
      }
      setError(formatError(err, 'OCR processing failed'));
    } finally {
      setUploading(false);
      setProcessing(false);
      setUploadProgress(0);
    }
  };

  const tableRows = result?.table_rows || [];
  const showBusy = uploading || processing;

  return (
    <Layout>
      {(historyLoading && history.length === 0) && (
        <Loader label="Loading OCR workspace..." />
      )}

      <div className="ocr-page">
        <section className="ocr-intro card">
          <h2>OCR processing</h2>
          <p>
            Upload PDF or scanned PDF documents for optical character recognition.
            Extracted text and table rows are returned as structured JSON.
          </p>
          {ocrReady === false && (
            <div className="alert alert-error" role="alert">
              OCR engine is not ready on this server.
              {ocrStatusNote ? ` ${ocrStatusNote}` : ' Install Tesseract and Poppler (use Docker on Render).'}
            </div>
          )}
          {ocrReady === true && (
            <p className="ocr-ready-hint" role="status">OCR engine ready on server.</p>
          )}
        </section>

        <section className="ocr-upload-card card">
          <header className="ocr-section-header">
            <h3>Upload document</h3>
            <span className="ocr-format-hint">PDF · scanned PDF · PNG · JPG</span>
          </header>

          {error && (
            <div className="alert alert-error" role="alert">
              {error}
            </div>
          )}

          {success && (
            <div className="alert alert-success" role="status">
              {success}
            </div>
          )}

          <FileDropZone
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            file={file}
            onFileSelect={setFile}
            hint="Drop a PDF or image here or click to browse"
          />

          {(uploading || uploadProgress > 0) && (
            <div className="ocr-progress-wrap" aria-live="polite">
              <div className="ocr-progress-label">
                <span>Upload progress</span>
                <strong>{uploadProgress}%</strong>
              </div>
              <div className="ocr-progress-bar" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100}>
                <div
                  className="ocr-progress-fill"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {processing && (
            <div className="ocr-processing-row" role="status">
              <Spinner />
              <span>Running OCR on document pages…</span>
            </div>
          )}

          <button
            type="button"
            className="btn btn-primary ocr-upload-btn"
            onClick={handleUpload}
            disabled={showBusy || !file}
          >
            {showBusy ? 'Processing…' : 'Process with OCR'}
          </button>
        </section>

        {result && (
          <section className="ocr-result-card card" aria-label="OCR result preview">
            <header className="ocr-result-header">
              <div>
                <h3>Result preview</h3>
                <p className="ocr-result-filename">{result.filename}</p>
              </div>
              <span className={confidenceBadgeClass(result.confidence_score)}>
                Confidence {formatConfidence(result.confidence_score)}
              </span>
            </header>

            {result.pages_processed != null && (
              <p className="ocr-meta-line">
                Pages processed: <strong>{result.pages_processed}</strong>
                {result.ocr_engine && (
                  <>
                    {' '}
                    · Engine: <strong>{result.ocr_engine}</strong>
                  </>
                )}
              </p>
            )}

            <div className="ocr-text-viewer">
              <h4>Extracted text</h4>
              <pre className="ocr-text-content">{result.extracted_text || 'No text extracted.'}</pre>
            </div>

            {tableRows.length > 0 && (
              <div className="ocr-table-preview">
                <h4>Detected table rows ({tableRows.length})</h4>
                <div className="ocr-table-scroll">
                  <table className="ocr-table">
                    <tbody>
                      {tableRows.slice(0, 25).map((row, idx) => (
                        <tr key={`row-${idx}`}>
                          {row.map((cell, cellIdx) => (
                            <td key={`cell-${idx}-${cellIdx}`}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {tableRows.length > 25 && (
                  <p className="ocr-table-more">Showing first 25 rows</p>
                )}
              </div>
            )}

            {result.json_output && (
              <details className="ocr-json-details">
                <summary>JSON output</summary>
                <pre className="ocr-json-block">
                  {JSON.stringify(result.json_output, null, 2)}
                </pre>
              </details>
            )}
          </section>
        )}

        <section className="ocr-history-card card table-card">
          <header className="table-header">
            <h3>OCR history</h3>
            <span className="ocr-history-count">{historyTotal} document(s)</span>
          </header>

          {historyError && (
            <div className="alert alert-error" role="alert">
              {historyError}
            </div>
          )}

          {detailLoading && <Loader label="Loading document…" />}

          {!historyLoading && !historyError && history.length === 0 && (
            <p className="ocr-empty-state">No OCR documents processed yet.</p>
          )}

          {history.length > 0 && (
            <div className="table-responsive">
              <table className="data-table ocr-history-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Filename</th>
                    <th>Confidence</th>
                    <th>Processed</th>
                    <th>Preview</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {history.map((row) => (
                    <tr
                      key={row.id}
                      className={selectedId === row.id ? 'ocr-row-selected' : ''}
                    >
                      <td>{row.id}</td>
                      <td>{row.filename}</td>
                      <td>
                        <span className={confidenceBadgeClass(row.confidence_score)}>
                          {formatConfidence(row.confidence_score)}
                        </span>
                      </td>
                      <td>{formatUploadedDate(row.created_at)}</td>
                      <td className="ocr-preview-cell">{row.text_preview || '—'}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => loadDetail(row.id)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {historyPages > 1 && (
            <Pagination
              page={historyPage}
              totalPages={historyPages}
              onPageChange={loadHistory}
            />
          )}
        </section>
      </div>
    </Layout>
  );
}
