import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import {
  approveReview,
  categoryBadgeClass,
  fetchReviewQueue,
  mergeReview,
  rejectReview,
} from '../services/reviewService';
import { formatError } from '../utils/formatError';
import '../styles/manualReview.css';

function PersonCard({ person, label }) {
  if (!person) {
    return (
      <div className="review-person-card">
        <span className="review-person-label">{label}</span>
        <p className="review-person-missing">Record unavailable</p>
      </div>
    );
  }
  return (
    <div className="review-person-card">
      <span className="review-person-label">{label}</span>
      <h3>{person.full_name || '—'}</h3>
      <dl className="review-person-details">
        <div>
          <dt>Mobile</dt>
          <dd>{person.mobile || '—'}</dd>
        </div>
        <div>
          <dt>DOB</dt>
          <dd>{person.dob || '—'}</dd>
        </div>
        <div>
          <dt>District</dt>
          <dd>{person.district || '—'}</dd>
        </div>
        <div>
          <dt>Village</dt>
          <dd>{person.village || '—'}</dd>
        </div>
        {person.father_name && (
          <div>
            <dt>Father name</dt>
            <dd>{person.father_name}</dd>
          </div>
        )}
      </dl>
      <Link to={`/person-profile/${person.id}`} className="review-profile-link">
        View Person 360 →
      </Link>
    </div>
  );
}

export default function ManualReview() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState(null);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchReviewQueue();
      setItems(data.items || []);
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(formatError(err, 'Failed to load review queue'));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const handleAction = async (action, reviewId) => {
    setActingId(reviewId);
    setError('');
    setSuccess('');
    try {
      if (action === 'approve') {
        await approveReview(reviewId);
        setSuccess('Match approved successfully');
      } else if (action === 'reject') {
        await rejectReview(reviewId);
        setSuccess('Match rejected successfully');
      } else if (action === 'merge') {
        const res = await mergeReview(reviewId);
        setSuccess(res.message || 'Profiles merged successfully');
      }
      await loadQueue();
    } catch (err) {
      setError(formatError(err, `Failed to ${action} match`));
    } finally {
      setActingId(null);
    }
  };

  return (
    <Layout>
      {loading && <Loader label="Loading manual review queue..." />}

      <div className="manual-review-page">
        <section className="review-intro card">
          <h2>Manual review queue</h2>
          <p>
            Entity resolution matches citizen records by mobile, name, date of birth, and
            related attributes. Review probable duplicates and take action.
          </p>
          <div className="review-legend">
            <span className="review-badge review-badge-confirmed">90+ Confirmed</span>
            <span className="review-badge review-badge-probable">75–89 Probable</span>
            <span className="review-badge review-badge-manual">55–74 Manual review</span>
          </div>
        </section>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {!loading && items.length === 0 && (
          <div className="review-empty card">
            <h3>Queue is clear</h3>
            <p>No pending entity matches require manual review (score 55+).</p>
          </div>
        )}

        {!loading &&
          items.map((item) => (
            <article key={item.id} className="review-item card">
              <div className="review-item-header">
                <div>
                  <span className="review-score-label">Match score</span>
                  <strong className="review-score">{item.match_score}</strong>
                </div>
                <span className={categoryBadgeClass(item.category)}>
                  {item.category_label}
                </span>
              </div>

              <p className="review-reason">
                <strong>Match reason:</strong> {item.match_reason || '—'}
              </p>

              <div className="review-persons-grid">
                <PersonCard person={item.person_a} label="Person A" />
                <PersonCard person={item.person_b} label="Person B" />
              </div>

              <div className="review-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={actingId === item.id}
                  onClick={() => handleAction('approve', item.id)}
                >
                  {actingId === item.id ? 'Processing…' : 'Approve match'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={actingId === item.id}
                  onClick={() => handleAction('reject', item.id)}
                >
                  Reject match
                </button>
                <button
                  type="button"
                  className="btn btn-secondary review-merge-btn"
                  disabled={actingId === item.id}
                  onClick={() => handleAction('merge', item.id)}
                >
                  Merge profiles
                </button>
              </div>
            </article>
          ))}

        {!loading && total > 0 && (
          <p className="review-queue-count">{total} item(s) in queue</p>
        )}
      </div>
    </Layout>
  );
}
