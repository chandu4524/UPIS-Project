import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import SensitiveAccessBadge from '../components/SensitiveAccessBadge';
import { fetchCitizenById } from '../services/citizenService';
import { formatError } from '../utils/formatError';
import { formatUploadedDate } from '../utils/formatDate';
import '../styles/personProfile.css';

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  return value;
}

export default function PersonProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [citizen, setCitizen] = useState(null);
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
      const data = await fetchCitizenById(id);
      setCitizen(data.citizen || null);
      setAccessFlags({
        can_view_sensitive_fields: data.can_view_sensitive_fields,
        sensitive_fields_masked: data.sensitive_fields_masked,
      });
      if (!data.citizen) {
        setError('Citizen profile not found');
      }
    } catch (err) {
      setError(formatError(err, 'Failed to load citizen profile'));
      setCitizen(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const district = citizen?.district || 'Not specified';

  return (
    <Layout>
      {loading && <Loader label="Loading person profile..." />}

      <div className="person-profile-page">
        <nav className="profile-breadcrumb" aria-label="Breadcrumb">
          <Link to="/citizens">← Back to citizen records</Link>
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
                <span className="profile-badge profile-badge-360">Person 360 Profile</span>
                <span className="profile-badge profile-badge-id">
                  ID #{citizen.id}
                </span>
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
              <h2>Profile summary</h2>
              <p>
                Unified intelligence view for{' '}
                <strong>{displayValue(citizen.full_name)}</strong> registered under GPIP.
                Review personal, contact, and location data below for field verification and
                officer reference.
              </p>
              {citizen.created_at && (
                <p className="profile-summary-meta">
                  Profile record created:{' '}
                  <time dateTime={citizen.created_at}>
                    {formatUploadedDate(citizen.created_at)}
                  </time>
                </p>
              )}
            </section>

            <div className="profile-sections-grid">
              <section className="profile-section card">
                <h3>Personal information</h3>
                <dl className="profile-detail-list">
                  <div className="profile-detail-item">
                    <dt>Full name</dt>
                    <dd>{displayValue(citizen.full_name)}</dd>
                  </div>
                  <div className="profile-detail-item">
                    <dt>Date of birth</dt>
                    <dd>{displayValue(citizen.dob)}</dd>
                  </div>
                  <div className="profile-detail-item">
                    <dt>Citizen ID</dt>
                    <dd className="profile-id-value">{citizen.id}</dd>
                  </div>
                </dl>
              </section>

              <section className="profile-section card">
                <h3>Contact information</h3>
                <dl className="profile-detail-list">
                  <div className="profile-detail-item">
                    <dt>Mobile number</dt>
                    <dd
                      className={
                        accessFlags.sensitive_fields_masked ? 'sensitive-field-masked' : ''
                      }
                    >
                      {displayValue(citizen.mobile)}
                    </dd>
                  </div>
                  {(citizen.aadhaar || citizen.pan) && (
                    <>
                      {citizen.aadhaar && (
                        <div className="profile-detail-item">
                          <dt>Aadhaar</dt>
                          <dd className={accessFlags.sensitive_fields_masked ? 'sensitive-field-masked' : ''}>
                            {displayValue(citizen.aadhaar)}
                          </dd>
                        </div>
                      )}
                      {citizen.pan && (
                        <div className="profile-detail-item">
                          <dt>PAN</dt>
                          <dd className={accessFlags.sensitive_fields_masked ? 'sensitive-field-masked' : ''}>
                            {displayValue(citizen.pan)}
                          </dd>
                        </div>
                      )}
                    </>
                  )}
                </dl>
              </section>

              <section className="profile-section card profile-section-wide">
                <h3>Location information</h3>
                <dl className="profile-detail-list profile-detail-list-grid">
                  <div className="profile-detail-item">
                    <dt>District</dt>
                    <dd>{displayValue(citizen.district)}</dd>
                  </div>
                  <div className="profile-detail-item">
                    <dt>Village</dt>
                    <dd>{displayValue(citizen.village)}</dd>
                  </div>
                </dl>
              </section>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
