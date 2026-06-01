import { useCallback, useEffect, useState } from 'react';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import PageError from '../components/PageError';
import {
  createDataSource,
  deleteDataSource,
  fetchDataSources,
  updateDataSource,
} from '../services/dataSourceService';
import { formatUploadedDate } from '../utils/formatDate';
import { formatError } from '../utils/formatError';
import { notify } from '../utils/notify';
import '../styles/dataSources.css';

const EMPTY_FORM = {
  source_name: '',
  source_code: '',
  description: '',
  is_active: true,
};

function StatusBadge({ isActive }) {
  return (
    <span className={`ds-status-badge ${isActive ? 'ds-status-active' : 'ds-status-inactive'}`}>
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

function SourceModal({ title, form, setForm, onClose, onSubmit, saving }) {
  return (
    <div className="ds-modal-overlay" role="dialog" aria-modal="true">
      <div className="ds-modal">
        <h3>{title}</h3>
        <form
          className="ds-form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit();
          }}
        >
          <label>
            Source name
            <input
              value={form.source_name}
              onChange={(e) => setForm((prev) => ({ ...prev, source_name: e.target.value }))}
              required
            />
          </label>
          <label>
            Source code
            <input
              value={form.source_code}
              onChange={(e) => setForm((prev) => ({ ...prev, source_code: e.target.value }))}
              required
            />
          </label>
          <label>
            Description
            <textarea
              rows={3}
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            />
          </label>
          <label>
            <span>Status</span>
            <select
              value={form.is_active ? 'active' : 'inactive'}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, is_active: e.target.value === 'active' }))
              }
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
          <div className="ds-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function DataSources() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [createForm, setCreateForm] = useState(EMPTY_FORM);
  const [editForm, setEditForm] = useState(EMPTY_FORM);

  const loadSources = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchDataSources({ activeOnly: false });
      setSources(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      setError(formatError(err, 'Failed to load data sources'));
      setSources([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  const handleCreate = async () => {
    setSaving(true);
    try {
      await createDataSource({
        source_name: createForm.source_name.trim(),
        source_code: createForm.source_code.trim(),
        description: createForm.description.trim() || null,
        is_active: createForm.is_active,
      });
      notify('Data source created', 'success');
      setShowCreate(false);
      setCreateForm(EMPTY_FORM);
      loadSources();
    } catch (err) {
      notify(formatError(err, 'Failed to create data source'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (source) => {
    setEditTarget(source);
    setEditForm({
      source_name: source.source_name || '',
      source_code: source.source_code || '',
      description: source.description || '',
      is_active: Boolean(source.is_active),
    });
  };

  const handleEdit = async () => {
    if (!editTarget) return;
    setSaving(true);
    try {
      await updateDataSource(editTarget.id, {
        source_name: editForm.source_name.trim(),
        source_code: editForm.source_code.trim(),
        description: editForm.description.trim() || null,
        is_active: editForm.is_active,
      });
      notify('Data source updated', 'success');
      setEditTarget(null);
      loadSources();
    } catch (err) {
      notify(formatError(err, 'Failed to update data source'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (source) => {
    setSaving(true);
    try {
      await updateDataSource(source.id, { is_active: !source.is_active });
      notify(`Source marked ${source.is_active ? 'inactive' : 'active'}`, 'success');
      loadSources();
    } catch (err) {
      notify(formatError(err, 'Failed to update status'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (source) => {
    if (!window.confirm(`Delete data source "${source.source_name}"?`)) return;
    setSaving(true);
    try {
      await deleteDataSource(source.id);
      notify('Data source deleted', 'success');
      loadSources();
    } catch (err) {
      notify(formatError(err, 'Failed to delete data source'), 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      {loading && <Loader label="Loading data sources..." />}

      <div className="data-sources-page">
        <section className="data-sources-intro card">
          <h2>Data Sources</h2>
          <p>Manage ingestion sources used to classify and track uploaded files.</p>
        </section>

        {error && (
          <PageError
            message={error}
            onRetry={loadSources}
            retryLabel="Reload data sources"
          />
        )}

        <section className="card">
          <div className="data-sources-toolbar">
            <strong>{sources.length} source(s)</strong>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowCreate(true)}
              disabled={saving}
            >
              Add source
            </button>
          </div>

          {!loading && !error && sources.length === 0 ? (
            <div className="data-sources-empty">No data sources configured yet.</div>
          ) : (
            <div className="table-wrap">
              <table className="data-sources-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Code</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((source) => (
                    <tr key={source.id}>
                      <td>{source.source_name}</td>
                      <td><code>{source.source_code}</code></td>
                      <td>{source.description || '—'}</td>
                      <td><StatusBadge isActive={source.is_active} /></td>
                      <td>{formatUploadedDate(source.created_at)}</td>
                      <td>
                        <div className="ds-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => openEdit(source)}
                            disabled={saving}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleToggleActive(source)}
                            disabled={saving}
                          >
                            {source.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleDelete(source)}
                            disabled={saving}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {showCreate && (
        <SourceModal
          title="Add data source"
          form={createForm}
          setForm={setCreateForm}
          onClose={() => setShowCreate(false)}
          onSubmit={handleCreate}
          saving={saving}
        />
      )}

      {editTarget && (
        <SourceModal
          title={`Edit ${editTarget.source_name}`}
          form={editForm}
          setForm={setEditForm}
          onClose={() => setEditTarget(null)}
          onSubmit={handleEdit}
          saving={saving}
        />
      )}
    </Layout>
  );
}
