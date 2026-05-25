import { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { canAccessRoute, getDefaultRouteForRole } from '../config/rbac';
import { getStoredRole, isAuthenticated } from '../services/authService';
import { notify } from '../utils/notify';

export default function ProtectedRoute({ children }) {
  const location = useLocation();
  const role = getStoredRole();

  useEffect(() => {
    if (location.state?.unauthorized) {
      notify('You do not have permission to access that page.', 'warning');
    }
  }, [location.state]);

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  if (!canAccessRoute(role, location.pathname)) {
    const fallback = getDefaultRouteForRole(role);
    if (location.pathname === fallback) {
      return (
        <div className="card" style={{ margin: '2rem', padding: '1.5rem' }}>
          <h2 style={{ color: 'var(--gov-navy)' }}>Access restricted</h2>
          <p style={{ color: 'var(--gov-muted)' }}>
            Your role does not have permission to view any modules. Contact an administrator.
          </p>
        </div>
      );
    }
    return (
      <Navigate
        to={fallback}
        replace
        state={{ unauthorized: true }}
      />
    );
  }

  return children;
}
