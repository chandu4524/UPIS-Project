import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Spinner from '../components/Spinner';
import { getDefaultRouteForRole } from '../config/rbac';
import { getStoredRole, loginUser } from '../services/authService';
import { formatError } from '../utils/formatError';
import '../styles/login.css';

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await loginUser(username, password);
      navigate(getDefaultRouteForRole(getStoredRole()), { replace: true });
    } catch (err) {
      setError(formatError(err, 'Invalid username or password'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">GPIP</div>
          <h1>Government Person Intelligence Platform</h1>
          <p>Secure officer access portal</p>
        </div>

        <div className="login-body">
          {error && (
            <div className="alert alert-error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                autoComplete="username"
                disabled={loading}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                autoComplete="current-password"
                disabled={loading}
                required
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary login-btn"
              disabled={loading}
            >
              {loading ? (
                <Spinner label="Logging in..." inline />
              ) : (
                'Login'
              )}
            </button>
          </form>

          <p className="login-footer-note">Authorized government personnel only</p>
        </div>
      </div>
    </div>
  );
}
