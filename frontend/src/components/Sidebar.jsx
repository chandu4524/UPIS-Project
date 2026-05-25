import { Link, useLocation } from 'react-router-dom';
import { getNavItemsForRole } from '../config/rbac';
import { getStoredRole } from '../services/authService';
import '../styles/layout.css';

export default function Sidebar({ onNavigate }) {
  const location = useLocation();
  const role = getStoredRole();
  const navItems = getNavItemsForRole(role);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-badge">GOV</span>
        <div>
          <h2>GPIP</h2>
          <p>Person Intelligence</p>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        {navItems.map(({ to, label, icon }) => {
          const active = location.pathname === to
            || (to !== '/dashboard' && location.pathname.startsWith(to));
          return (
            <Link
              key={to}
              to={to}
              onClick={onNavigate}
              className={`sidebar-link ${active ? 'active' : ''}`}
              aria-current={active ? 'page' : undefined}
            >
              <span className="sidebar-link-icon" aria-hidden="true">
                {icon}
              </span>
              {label}
            </Link>
          );
        })}
      </nav>

      <p className="sidebar-footer">Government of India — Secure Portal</p>
    </aside>
  );
}
