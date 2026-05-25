import { useCallback, useEffect, useState } from 'react';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import PageError from '../components/PageError';
import Pagination from '../components/Pagination';
import {
  createAdminUser,
  fetchAdminUsers,
  resetAdminUserPassword,
  updateAdminUser,
} from '../services/adminUsersService';
import { getStoredUsername } from '../services/authService';
import { getRoleLabel, normalizeRole } from '../config/rbac';
import { formatUploadedDate } from '../utils/formatDate';
import { formatError } from '../utils/formatError';
import { notify } from '../utils/notify';
import '../styles/adminUsers.css';

const PAGE_SIZE = 10;

function RoleBadge({ role }) {
  return <span className="role-badge">{getRoleLabel(role)}</span>;
}

function StatusBadge({ isActive }) {
  const active = Boolean(isActive);
  return (
    <span className={`status-badge ${active ? 'status-badge-active' : 'status-badge-inactive'}`}>
      {active ? 'Active' : 'Inactive'}
    </span>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="admin-modal-overlay" role="dialog" aria-modal="true">
      <div className="admin-modal">
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  );
}

export default function AdminUsers() {
  const currentUsername = getStoredUsername();
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    username: '',
    password: '',
    role: 'district_officer',
  });

  const [resetTarget, setResetTarget] = useState(null);
  const [resetPassword, setResetPassword] = useState('');

  const [roleEdit, setRoleEdit] = useState(null);

  const loadUsers = useCallback(async (pageNum = 1) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchAdminUsers({ page: pageNum, pageSize: PAGE_SIZE });
      setUsers(data.items || []);
      setTotal(data.total ?? 0);
      setTotalPages(data.total_pages ?? 0);
      setPage(data.page ?? pageNum);
      if (data.assignable_roles?.length) {
        setRoles(data.assignable_roles);
      }
    } catch (err) {
      setError(formatError(err, 'Failed to load users'));
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers(1);
  }, [loadUsers]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await createAdminUser({
        username: createForm.username.trim(),
        password: createForm.password,
        role: createForm.role,
        is_active: true,
      });
      notify('User created successfully', 'success');
      setShowCreate(false);
      setCreateForm({ username: '', password: '', role: 'district_officer' });
      loadUsers(page);
    } catch (err) {
      notify(formatError(err, 'Failed to create user'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (user) => {
    if (user.username === currentUsername && user.is_active) {
      notify('You cannot deactivate your own account', 'warning');
      return;
    }
    setSaving(true);
    try {
      await updateAdminUser(user.id, { is_active: !user.is_active });
      notify(user.is_active ? 'User deactivated' : 'User activated', 'success');
      loadUsers(page);
    } catch (err) {
      notify(formatError(err, 'Failed to update user status'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleRoleSave = async () => {
    if (!roleEdit) return;
    setSaving(true);
    try {
      await updateAdminUser(roleEdit.id, { role: roleEdit.role });
      notify('Role updated', 'success');
      setRoleEdit(null);
      loadUsers(page);
    } catch (err) {
      notify(formatError(err, 'Failed to update role'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!resetTarget) return;
    setSaving(true);
    try {
      await resetAdminUserPassword(resetTarget.id, resetPassword);
      notify('Password reset successfully', 'success');
      setResetTarget(null);
      setResetPassword('');
    } catch (err) {
      notify(formatError(err, 'Failed to reset password'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const showEmpty = !loading && !error && users.length === 0;

  return (
    <Layout>
      {loading && <Loader label="Loading users..." />}

      <div className="admin-users-page">
        <section className="admin-users-intro card">
          <h2>Admin users</h2>
          <p>
            Manage GPIP officer accounts: create users, assign roles, reset passwords, and
            activate or deactivate access.
          </p>
        </section>

        {error && (
          <PageError
            message={error}
            onRetry={() => loadUsers(page)}
            retryLabel="Reload users"
          />
        )}

        <div className="table-card card">
          <div className="admin-users-toolbar">
            <div className="table-header" style={{ marginBottom: 0 }}>
              <h3>User accounts</h3>
              <span className="record-count">{total} user(s)</span>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowCreate(true)}
              disabled={loading || saving}
            >
              + Create user
            </button>
          </div>

          {showEmpty ? (
            <div className="empty-state">
              <div className="empty-state-icon" aria-hidden="true">
                👤
              </div>
              <h3>No users found</h3>
              <p>Create the first officer account to get started.</p>
            </div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="admin-users-table">
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id}>
                        <td className="username-cell">{user.username}</td>
                        <td>
                          <RoleBadge role={user.role} />
                        </td>
                        <td>
                          <StatusBadge isActive={user.is_active} />
                        </td>
                        <td>{formatUploadedDate(user.created_at)}</td>
                        <td>
                          <div className="admin-users-actions">
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() =>
                                setRoleEdit({
                                  id: user.id,
                                  username: user.username,
                                  role: normalizeRole(user.role),
                                })
                              }
                              disabled={saving}
                            >
                              Change role
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                setResetTarget(user);
                                setResetPassword('');
                              }}
                              disabled={saving}
                            >
                              Reset password
                            </button>
                            <button
                              type="button"
                              className={`btn btn-secondary btn-sm toggle-active-btn ${
                                user.is_active ? 'active-on' : 'active-off'
                              }`}
                              onClick={() => handleToggleActive(user)}
                              disabled={saving}
                            >
                              {user.is_active ? 'Deactivate' : 'Activate'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {totalPages > 1 && (
                <Pagination
                  page={page}
                  totalPages={totalPages}
                  onPageChange={(p) => loadUsers(p)}
                />
              )}
            </>
          )}
        </div>
      </div>

      {showCreate && (
        <Modal title="Create user" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <div className="form-group">
              <label htmlFor="create-username">Username</label>
              <input
                id="create-username"
                type="text"
                className="form-control"
                value={createForm.username}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, username: e.target.value }))
                }
                required
                minLength={2}
                autoComplete="off"
              />
            </div>
            <div className="form-group">
              <label htmlFor="create-password">Password</label>
              <input
                id="create-password"
                type="password"
                className="form-control"
                value={createForm.password}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, password: e.target.value }))
                }
                required
                minLength={4}
                autoComplete="new-password"
              />
            </div>
            <div className="form-group">
              <label htmlFor="create-role">Role</label>
              <select
                id="create-role"
                className="form-control"
                value={createForm.role}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, role: e.target.value }))
                }
              >
                {(roles.length ? roles : [{ value: 'district_officer', label: 'District Officer' }]).map(
                  (r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  )
                )}
              </select>
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowCreate(false)}
                disabled={saving}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : 'Create'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {roleEdit && (
        <Modal title={`Change role — ${roleEdit.username}`} onClose={() => setRoleEdit(null)}>
          <div className="form-group">
            <label htmlFor="edit-role">Role</label>
            <select
              id="edit-role"
              className="form-control"
              value={roleEdit.role}
              onChange={(e) =>
                setRoleEdit((r) => ({ ...r, role: e.target.value }))
              }
            >
              {(roles.length ? roles : [{ value: roleEdit.role, label: getRoleLabel(roleEdit.role) }]).map(
                (r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                )
              )}
            </select>
          </div>
          <div className="form-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setRoleEdit(null)}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleRoleSave}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </Modal>
      )}

      {resetTarget && (
        <Modal
          title={`Reset password — ${resetTarget.username}`}
          onClose={() => setResetTarget(null)}
        >
          <form onSubmit={handleResetPassword}>
            <div className="form-group">
              <label htmlFor="reset-password">New password</label>
              <input
                id="reset-password"
                type="password"
                className="form-control"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                required
                minLength={4}
                autoComplete="new-password"
              />
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setResetTarget(null)}
                disabled={saving}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : 'Reset'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </Layout>
  );
}
