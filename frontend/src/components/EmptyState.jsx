import '../styles/emptyState.css';

export default function EmptyState({
  icon = '◇',
  title = 'No records found',
  description,
  action,
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-icon" aria-hidden="true">
        {icon}
      </span>
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-desc">{description}</p>}
      {action}
    </div>
  );
}
