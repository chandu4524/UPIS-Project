import { Link } from 'react-router-dom';
import '../styles/components.css';

export default function StatCard({ label, value, icon, accent, linkTo }) {
  const card = (
    <article className={`stat-card-modern ${accent || ''}`}>
      <div className="stat-card-icon" aria-hidden="true">
        {icon}
      </div>
      <div className="stat-card-body">
        <span className="stat-card-label">{label}</span>
        <strong className="stat-card-value">{value}</strong>
      </div>
    </article>
  );

  if (linkTo) {
    return (
      <Link to={linkTo} className="stat-card-link" title={`Go to ${label}`}>
        {card}
      </Link>
    );
  }

  return card;
}
