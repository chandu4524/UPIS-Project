import { useCallback, useEffect, useState } from 'react';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import PageError from '../components/PageError';
import Pagination from '../components/Pagination';
import {
  fetchAuditLogs,
  formatActionType,
  formatEntity,
} from '../services/auditService';
import { formatUploadedDate } from '../utils/formatDate';
import { formatError } from '../utils/formatError';
import '../styles/auditLogs.css';

const PAGE_SIZE = 15;

function actionBadgeClass(actionType) {
  const key = (actionType || '').toLowerCase();
  if (key === 'login') return 'audit-action audit-action-login';
  if (key.includes('upload')) return 'audit-action audit-action-upload';
  if (key.includes('profile') || key.includes('relationship')) {
    return 'audit-action audit-action-profile';
  }
  if (key.includes('search')) return 'audit-action audit-action-search';
  return 'audit-action';
}

export default function AuditLogs() {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const loadLogs = useCallback(async (pageNum = 1) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchAuditLogs({ page: pageNum, pageSize: PAGE_SIZE });
      setRecords(data.items || []);
      setTotal(data.total ?? 0);
      setTotalPages(data.total_pages ?? 0);
      setPage(data.page ?? pageNum);
    } catch (err) {
      setError(formatError(err, 'Failed to load audit logs'));
      setRecords([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLogs(1);
  }, [loadLogs]);

  const handlePageChange = (nextPage) => {
    loadLogs(nextPage);
  };

  const showEmpty = !loading && !error && records.length === 0;

  return (
    <Layout>
      {loading && <Loader label="Loading audit logs..." />}

      <div className="audit-logs-page">
        <section className="audit-logs-intro card">
          <h2>Audit logs</h2>
          <p>
            Secure activity trail for officer actions across login, uploads, citizen
            search, profiles, and relationship graphs.
          </p>
        </section>

        {error && (
          <PageError
            message={error}
            onRetry={() => loadLogs(page)}
            retryLabel="Reload audit logs"
          />
        )}

        <div className="table-card card">
          <div className="table-header">
            <h3>Activity log</h3>
            <span className="record-count">{total} event(s)</span>
          </div>

          {showEmpty ? (
            <div className="empty-state">
              <div className="empty-state-icon" aria-hidden="true">
                ⊞
              </div>
              <h3>No audit events yet</h3>
              <p>
                Actions such as login, file upload, and citizen profile views will
                appear here automatically.
              </p>
            </div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="audit-logs-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Action</th>
                      <th>Entity</th>
                      <th>Date / time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((row) => (
                      <tr key={row.id}>
                        <td className="audit-user-cell">{row.username}</td>
                        <td>
                          <span className={actionBadgeClass(row.action_type)}>
                            {formatActionType(row.action_type)}
                          </span>
                        </td>
                        <td className="audit-entity-cell">{formatEntity(row)}</td>
                        <td>{formatUploadedDate(row.created_at)}</td>
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
