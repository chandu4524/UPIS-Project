import '../styles/loader.css';

export default function Loader({ label = 'Loading...', inline = false }) {
  if (inline) {
    return (
      <div className="loader-inline" role="status" aria-live="polite">
        <div className="loader-spinner loader-spinner-inline" />
        <p className="loader-label-inline">{label}</p>
      </div>
    );
  }

  return (
    <div className="loader-overlay" role="status" aria-live="polite" aria-busy="true">
      <div className="loader-spinner" />
      <p className="loader-label">{label}</p>
    </div>
  );
}
