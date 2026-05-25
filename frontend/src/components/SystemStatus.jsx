import useHealthStatus from '../hooks/useHealthStatus';
import '../styles/systemStatus.css';

export default function SystemStatus({ compact = false }) {
  const { status, detail, label } = useHealthStatus();

  return (
    <span
      className={`system-status system-status-${status}${compact ? ' system-status-compact' : ''}`}
      title={detail || label}
      aria-label={`System status: ${label}. ${detail}`}
    >
      <span className="system-status-dot" aria-hidden="true" />
      {!compact && <span className="system-status-label">{label}</span>}
    </span>
  );
}
