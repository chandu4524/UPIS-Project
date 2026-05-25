import '../styles/components.css';

export default function Spinner({ label, inline = false }) {
  if (inline) {
    return (
      <span className="spinner-inline" role="status" aria-live="polite">
        <span className="spinner-inline-ring" />
        {label && <span className="spinner-inline-label">{label}</span>}
      </span>
    );
  }

  return (
    <div className="spinner-block" role="status" aria-live="polite">
      <span className="spinner-inline-ring" />
      {label && <span className="spinner-inline-label">{label}</span>}
    </div>
  );
}
