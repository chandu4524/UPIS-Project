import { useLocation, useNavigate } from 'react-router-dom';
import SystemStatus from './SystemStatus';
import { getStoredRoleLabel, getStoredUsername, logout } from '../services/authService';

const PAGE_TITLES = {
  '/dashboard': 'Secure Dashboard',
  '/analytics-dashboard': 'Analytics Dashboard',
  '/upload': 'Intelligence File Upload',
  '/ocr-processing': 'OCR Processing',
  '/template-mapping': 'Template Mapping',
  '/data-sources': 'Data Sources',
  '/upload-history': 'Upload History',
  '/citizens': 'Citizen Records',
  '/intelligence-search': 'Intelligence Search',
  '/ai-assistant': 'AI Intelligence Assistant',
  '/manual-review': 'Manual Review Queue',
  '/audit-logs': 'Audit Logs',
  '/reports': 'Reports & Export',
};

export default function Navbar({ onMenuToggle, sidebarOpen = false }) {
  const location = useLocation();
  const navigate = useNavigate();
  const username = getStoredUsername() || 'Officer';
  const roleLabel = getStoredRoleLabel();
  const title = location.pathname.startsWith('/reports/preview')
    ? 'Report Preview'
    : location.pathname.startsWith('/relationships')
      ? 'Relationship Graph'
      : location.pathname.startsWith('/person-profile')
        ? 'Person 360 Profile'
        : PAGE_TITLES[location.pathname] || 'GPIP Portal';

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="top-navbar">
      <div className="top-navbar-left">
        <button
          type="button"
          className="btn-menu-toggle"
          aria-label="Toggle navigation menu"
          aria-expanded={sidebarOpen}
          onClick={onMenuToggle}
        >
          ☰
        </button>
        <div>
          <h1 className="top-navbar-title">{title}</h1>
          <p className="top-navbar-subtitle">Government Person Intelligence Platform</p>
        </div>
      </div>
      <div className="top-navbar-actions">
        <SystemStatus />
        <span className="top-navbar-user">
          <span className="top-navbar-role">{roleLabel}</span>
          Officer: <strong>{username}</strong>
        </span>
        <button type="button" className="btn btn-nav-logout" onClick={handleLogout}>
          <span className="btn-nav-logout-icon" aria-hidden="true">
            ⎋
          </span>
          Logout
        </button>
      </div>
    </header>
  );
}
