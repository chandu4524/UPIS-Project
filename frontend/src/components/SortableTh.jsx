import '../styles/components.css';

export default function SortableTh({ label, field, sortBy, sortOrder, onSort }) {
  const active = sortBy === field || (field === 'full_name' && sortBy === 'name');
  const direction = active ? sortOrder : null;

  return (
    <th scope="col">
      <button
        type="button"
        className={`sortable-th ${active ? 'active' : ''}`}
        onClick={() => onSort(field)}
        aria-sort={
          active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'
        }
      >
        {label}
        <span className="sort-indicator" aria-hidden="true">
          {direction === 'asc' ? ' ▲' : direction === 'desc' ? ' ▼' : ' ⇅'}
        </span>
      </button>
    </th>
  );
}
