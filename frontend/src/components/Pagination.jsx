import '../styles/components.css';

export default function Pagination({
  page,
  totalPages,
  total,
  onPageChange,
  disabled = false,
}) {
  if (totalPages <= 1 && total === 0) return null;

  const pages = [];
  const maxVisible = 5;
  let start = Math.max(1, page - Math.floor(maxVisible / 2));
  let end = Math.min(totalPages, start + maxVisible - 1);
  start = Math.max(1, end - maxVisible + 1);

  for (let i = start; i <= end; i += 1) pages.push(i);

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        type="button"
        className="btn btn-secondary pagination-btn"
        disabled={disabled || page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </button>
      <div className="pagination-pages">
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            className={`pagination-page ${p === page ? 'active' : ''}`}
            disabled={disabled}
            onClick={() => onPageChange(p)}
          >
            {p}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="btn btn-secondary pagination-btn"
        disabled={disabled || page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
      <span className="pagination-meta">
        Page {page} of {totalPages || 1} ({total} total)
      </span>
    </nav>
  );
}
