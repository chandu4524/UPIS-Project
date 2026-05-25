import useHealthStatus from '../hooks/useHealthStatus';
import '../styles/systemStatus.css';

export default function DashboardStatus() {
  const { status, detail, label, payload } = useHealthStatus(90000);

  const db = payload?.database_status || '—';
  const env = payload?.environment || '—';
  const generated = payload?.generated_at
    ? new Date(payload.generated_at).toLocaleString()
    : null;

  return (
    <div
      className={`dashboard-status dashboard-status-${status}`}
      title={detail}
      aria-label={`Platform status: ${label}`}
    >
      <span className="system-status-dot" aria-hidden="true" />
      <div className="dashboard-status-text">
        <strong>{label}</strong>
        <span className="dashboard-status-meta">
          Database: {db} · Environment: {env}
          {generated ? ` · Checked ${generated}` : ''}
        </span>
      </div>
    </div>
  );
}
