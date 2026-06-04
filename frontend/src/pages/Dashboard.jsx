import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import PageError from '../components/PageError';
import StatCard from '../components/StatCard';
import DashboardAnalytics from '../components/DashboardAnalytics';
import DashboardStatus from '../components/DashboardStatus';
import { fetchDashboard, fetchDashboardAnalytics } from '../services/dashboardService';
import { getStoredUsername } from '../services/authService';
import { subscribeDashboardRefresh } from '../utils/appRefresh';
import { formatError } from '../utils/formatError';
import { handleUnauthorizedIfNeeded } from '../auth/handleUnauthorized';
import { formatUploadedDate } from '../utils/formatDate';
import '../styles/dashboard.css';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState('');
  const [analyticsError, setAnalyticsError] = useState('');
  const [loading, setLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setAnalyticsLoading(true);
    setError('');
    setAnalyticsError('');
    try {
      const [dashboardResult, analyticsResult] = await Promise.allSettled([
        fetchDashboard(),
        fetchDashboardAnalytics(),
      ]);

      for (const result of [dashboardResult, analyticsResult]) {
        if (result.status === 'rejected' && handleUnauthorizedIfNeeded(result.reason)) {
          setLoading(false);
          setAnalyticsLoading(false);
          return;
        }
      }

      if (dashboardResult.status === 'fulfilled') {
        setData(dashboardResult.value);
      } else {
        setError(formatError(dashboardResult.reason, 'Failed to load dashboard'));
        setData(null);
      }

      if (analyticsResult.status === 'fulfilled') {
        setAnalytics(analyticsResult.value?.analytics ?? null);
      } else {
        setAnalyticsError(
          formatError(analyticsResult.reason, 'Failed to load intelligence analytics'),
        );
        setAnalytics(null);
      }
    } finally {
      setLoading(false);
      setAnalyticsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    return subscribeDashboardRefresh(() => loadDashboard());
  }, [loadDashboard]);

  const username = data?.logged_in_user || getStoredUsername();
  const stats = data?.stats || {};
  const recentUploads = stats.recent_uploads || [];
  const totalUploads = stats.uploaded_files ?? 0;
  const lastUploadTime = stats.last_upload_at
    || recentUploads[0]?.uploaded_at
    || null;

  return (
    <Layout>
      {loading && <Loader label="Loading dashboard..." />}
      {error && (
        <PageError message={error} onRetry={loadDashboard} retryLabel="Reload dashboard" />
      )}

      {!loading && !error && (
        <div className="dashboard-page">
          <section className="welcome-card card">
            <div className="welcome-header">
              <div>
                <h2>Welcome back</h2>
                <p className="welcome-message">{data?.message}</p>
              </div>
              <DashboardStatus />
            </div>
            <div className="welcome-meta">
              <span>Logged-in officer</span>
              <strong>{username}</strong>
            </div>
          </section>

          <div className="dashboard-overview">
            <section className="activity-widget card" aria-label="Officer activity">
              <div className="activity-widget-header">
                <span className="activity-widget-icon" aria-hidden="true">
                  ◉
                </span>
                <h3>Officer activity</h3>
              </div>
              <dl className="activity-widget-list">
                <div className="activity-item">
                  <dt>Officer name</dt>
                  <dd>{username || '—'}</dd>
                </div>
                <div className="activity-item">
                  <dt>Total uploads</dt>
                  <dd className="activity-highlight">{totalUploads}</dd>
                </div>
                <div className="activity-item">
                  <dt>Last upload time</dt>
                  <dd>{formatUploadedDate(lastUploadTime)}</dd>
                </div>
              </dl>
              {totalUploads > 0 && (
                <Link to="/upload-history" className="activity-widget-link">
                  View full upload history →
                </Link>
              )}
            </section>

            <section className="stats-grid" aria-label="Dashboard statistics">
              <StatCard
                label="Intelligence records"
                value={stats.intelligence_records ?? stats.total_staging_rows ?? 0}
                icon="📊"
                accent="accent-blue"
                linkTo="/intelligence-search"
              />
              <StatCard
                label="Staging rows"
                value={stats.total_staging_rows ?? 0}
                icon="📋"
                accent="accent-navy"
              />
              <StatCard
                label="Analytics rows"
                value={stats.total_uploaded_data_rows ?? 0}
                icon="🗄"
                accent="accent-green"
              />
              <StatCard
                label="Citizen registry"
                value={stats.total_citizens ?? 0}
                icon="👥"
                accent="accent-gold"
                linkTo="/citizens"
              />
              <StatCard
                label="Uploaded files"
                value={totalUploads}
                icon="📁"
                accent="accent-gold"
                linkTo="/upload-history"
              />
              <StatCard
                label="Imported rows"
                value={stats.total_imported_rows ?? 0}
                icon="⬆"
                accent="accent-green"
              />
            </section>
          </div>

          <DashboardAnalytics
            analytics={analytics}
            loading={analyticsLoading}
            error={analyticsError}
          />

          <section className="recent-uploads card">
            <div className="recent-uploads-header">
              <div>
                <h3>Recent uploads</h3>
                <p className="recent-uploads-subtitle">Latest 5 files from upload history</p>
              </div>
              <Link to="/upload-history" className="btn btn-secondary recent-view-all">
                View all
              </Link>
            </div>

            {recentUploads.length ? (
              <ul className="recent-list">
                {recentUploads.map((item) => (
                  <li key={item.id ?? `${item.filename}-${item.uploaded_at}`}>
                    <Link
                      to="/upload-history"
                      className="recent-item-link"
                      title="View in upload history"
                    >
                    <div className="recent-item-main">
                      <span className="recent-file-icon" aria-hidden="true">
                        📄
                      </span>
                      <div className="recent-item-text">
                        <span className="recent-filename" title={item.filename}>
                          {item.filename}
                        </span>
                        <span className="recent-date">
                          <time dateTime={item.uploaded_at}>
                            {formatUploadedDate(item.uploaded_at)}
                          </time>
                        </span>
                      </div>
                    </div>
                    {item.rows != null && (
                      <span className="recent-rows-badge">
                        {item.rows} row{item.rows === 1 ? '' : 's'}
                      </span>
                    )}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="recent-empty">
                No uploads yet.{' '}
                <Link to="/upload">Upload a CSV</Link> to get started.
              </p>
            )}
          </section>
        </div>
      )}
    </Layout>
  );
}
