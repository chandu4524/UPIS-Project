import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import SensitiveAccessBadge from '../components/SensitiveAccessBadge';
import { fetchPerson360Profile } from '../services/person360Service';
import { formatError } from '../utils/formatError';
import { formatUploadedDate } from '../utils/formatDate';
import '../styles/personProfile.css';

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  return value;
}

function ProfileSection({ section, defaultOpen = false, masked }) {
  const [open, setOpen] = useState(defaultOpen);
  const fields = Array.isArray(section?.fields) ? section.fields : [];

  if (!fields.length) {
    return null;
  }

  return (
    <section className={`profile-360-section card ${open ? 'is-open' : ''}`}>
      <button
        type="button"
        className="profile-360-section-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div className="profile-360-section-heading">
          <h3>{section.title || 'Source data'}</h3>
          <p className="profile-360-section-meta">
            {section.source_type === 'registry' && 'Master registry'}
            {section.source_type === 'staging' &&
              `Staging row ${section.row_number ?? '—'} · ${section.confidence_level || '—'}`}
            {section.source_type === 'duckdb' &&
              `Upload ${section.upload_id ?? '—'} · ${section.source_file || 'file'}`}
            {section.field_count != null && ` · ${section.field_count} fields`}
          </p>
        </div>
        <span className="profile-360-chevron" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
      </button>

      {open && (
        <dl className="profile-detail-list profile-detail-list-grid profile-360-fields">
          {fields.map((field) => (
            <div key={`${section.section_id}-${field.key}-${field.value}`} className="profile-detail-item">
              <dt>{field.label || field.key}</dt>
              <dd
                className={
                  masked &&
                  ['mobile', 'aadhaar', 'aadhar', 'pan', 'account_no'].includes(
                    (field.key || '').toLowerCase()
                  )
                    ? 'sensitive-field-masked'
                    : ''
                }
              >
                {displayValue(field.value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

export default function PersonProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [citizen, setCitizen] = useState(null);
  const [profile360, setProfile360] = useState(null);
  const [meta, setMeta] = useState({});
  const [accessFlags, setAccessFlags] = useState({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const loadProfile = useCallback(async () => {
    if (!id) {
      setError('Invalid citizen ID');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await fetchPerson360Profile(id);
      setCitizen(data.citizen || null);
      setProfile360(data.profile_360 || null);
      setMeta({
        profile_confidence: data.profile_confidence,
        source_count: data.source_count,
        linked_departments: data.linked_departments || [],
        relationship_summary: data.relationship_summary || {},
        staging_row_count: data.profile_360?.staging_row_count,
        duckdb_row_count: data.profile_360?.duckdb_row_count,
        total_field_count: data.profile_360?.total_field_count,
      });
      setAccessFlags({
        can_view_sensitive_fields: data.can_view_sensitive_fields,
        sensitive_fields_masked: data.sensitive_fields_masked,
      });
      if (!data.citizen) {
        setError('Citizen profile not found');
      }
    } catch (err) {
      setError(formatError(err, 'Failed to load person 360 profile'));
      setCitizen(null);
      setProfile360(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const sections = Array.isArray(profile360?.sections) ? profile360.sections : [];
  const district = citizen?.district || 'Not specified';

  return (
    <Layout>
      {loading && <Loader label="Loading person 360 profile..." />}

      <div className="person-profile-page">
        <nav className="profile-breadcrumb" aria-label="Breadcrumb">
          <Link to="/intelligence-search">← Intelligence search</Link>
          <span className="profile-breadcrumb-sep"> / </span>
          <Link to="/citizens">Citizen records</Link>
        </nav>

        {error && (
          <div className="alert alert-error">
            {error}
            <button
              type="button"
              className="btn btn-secondary profile-retry-btn"
              onClick={() => navigate('/citizens')}
            >
              Return to list
            </button>
          </div>
        )}

        {!loading && !error && citizen && (
          <>
            <header className="profile-header-card card">
              <div className="profile-header-main">
                <div className="profile-avatar" aria-hidden="true">
                  {citizen.full_name?.charAt(0)?.toUpperCase() || '?'}
                </div>
                <div className="profile-header-text">
                  <span className="profile-eyebrow">Person 360</span>
                  <h1>{displayValue(citizen.full_name)}</h1>
                  <p className="profile-header-district">{displayValue(district)}</p>
                </div>
              </div>
              <div className="profile-header-badges">
                <span className="profile-badge profile-badge-360">360° Intelligence Profile</span>
                <span className="profile-badge profile-badge-id">ID #{citizen.id}</span>
                {meta.profile_confidence && (
                  <span className="profile-badge">Confidence: {meta.profile_confidence}</span>
                )}
                <SensitiveAccessBadge {...accessFlags} />
                <button
                  type="button"
                  className="btn btn-primary profile-relationships-btn"
                  onClick={() => navigate(`/relationships/${citizen.id}`)}
                >
                  View Relationships
                </button>
              </div>
            </header>

            <section className="profile-summary-card card" aria-label="Profile summary">
              <h2>Unified intelligence view</h2>
              <p>
                Merged data from citizen registry, upload staging, and analytics stores.
                {meta.total_field_count != null && (
                  <>
                    {' '}
                    <strong>{meta.total_field_count}</strong> fields across{' '}
                    <strong>{sections.length}</strong> sections.
                  </>
                )}
              </p>
              {meta.linked_departments?.length > 0 && (
                <p className="profile-360-dept-tags">
                  Sources:{' '}
                  {meta.linked_departments.map((dept) => (
                    <span key={dept} className="profile-360-dept-tag">
                      {dept}
                    </span>
                  ))}
                </p>
              )}
              {citizen.created_at && (
                <p className="profile-summary-meta">
                  Registry created:{' '}
                  <time dateTime={citizen.created_at}>{formatUploadedDate(citizen.created_at)}</time>
                </p>
              )}
            </section>

            {sections.length === 0 ? (
              <div className="card profile-360-empty">
                <p>No extended upload fields linked to this person yet.</p>
              </div>
            ) : (
              <div className="profile-360-sections">
                {sections.map((section, idx) => (
                  <ProfileSection
                    key={section.section_id || idx}
                    section={section}
                    defaultOpen={idx === 0}
                    masked={accessFlags.sensitive_fields_masked}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
