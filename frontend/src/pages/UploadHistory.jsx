import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import PageError from '../components/PageError';
import Pagination from '../components/Pagination';
import { fetchUploadHistory } from '../services/uploadService';
import { subscribeUploadHistoryRefresh } from '../utils/appRefresh';
import { formatError } from '../utils/formatError';
import { formatUploadedDate } from '../utils/formatDate';
import '../styles/uploadHistory.css';

const PAGE_SIZE = 10;

function statusClass(status) {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'completed') return 'status-badge status-completed';
  if (normalized === 'no records') return 'status-badge status-empty';
  return 'status-badge';
}

export default function UploadHistory() {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const loadHistory = useCallback(async (pageNum = 1) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchUploadHistory({ page: pageNum, pageSize: PAGE_SIZE });
      const items = Array.isArray(data?.items) ? data.items : [];
      setRecords(items);
      setTotal(data.total ?? 0);
      setTotalPages(data.total_pages ?? 0);
      setPage(data.page ?? pageNum);
    } catch (err) {
      setError(formatError(err, 'Failed to load upload history'));
      setRecords([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory(1);
  }, [loadHistory]);

  useEffect(() => {
    return subscribeUploadHistoryRefresh(() => loadHistory(1));
  }, [loadHistory]);

  const handlePageChange = (nextPage) => {
    loadHistory(nextPage);
  };

  const showEmpty = !loading && !error && records.length === 0;

  return (
    <Layout>
      {loading && <Loader label="Loading upload history..." />}

      <div className="upload-history-page">
        <section className="upload-history-intro card">
          <h2>Upload history</h2>
          <p>
            Track CSV uploads, imported row counts, and processing status across your
            officer sessions.
          </p>
          <nav className="upload-history-quick-nav" aria-label="Related pages">
            <Link to="/dashboard" className="quick-nav-pill">
              ← Dashboard
            </Link>
            <Link to="/upload" className="quick-nav-pill">
              File upload
            </Link>
            <Link to="/citizens" className="quick-nav-pill">
              Citizen records
            </Link>
          </nav>
        </section>

        {error && (
          <PageError
            message={error}
            onRetry={() => loadHistory(page)}
            retryLabel="Reload upload history"
          />
        )}

        <div className="table-card card">
          <div className="table-header">
            <h3>All uploads</h3>
            <span className="record-count">{total} upload(s)</span>
          </div>

          {showEmpty ? (
            <div className="empty-state">
              <div className="empty-state-icon" aria-hidden="true">
                ◷
              </div>
              <h3>No uploads yet</h3>
              <p>
                CSV files uploaded from the File Upload page will appear here with
                row counts and timestamps.
              </p>
            </div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="upload-history-table">
                  <thead>
                    <tr>
                      <th>File name</th>
                      <th>Uploaded rows</th>
                      <th>Uploaded date</th>
                      <th>Status</th>
                      <th>Uploaded by</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((row) => (
                      <tr key={row.id}>
                        <td className="filename-cell" title={row.filename}>
                          {row.filename}
                        </td>
                        <td className="numeric-cell">{row.uploaded_rows}</td>
                        <td>{formatUploadedDate(row.uploaded_at)}</td>
                        <td>
                          <span className={statusClass(row.status)}>{row.status}</span>
                        </td>
                        <td>{row.uploaded_by || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                totalPages={totalPages}
                total={total}
                onPageChange={handlePageChange}
                disabled={loading}
              />
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
