import '../styles/pageError.css';

export default function PageError({
  message = 'Something went wrong loading this page.',
  onRetry,
  retryLabel = 'Try again',
}) {
  return (
    <div className="page-error card" role="alert">
      <p className="page-error-message">{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}
