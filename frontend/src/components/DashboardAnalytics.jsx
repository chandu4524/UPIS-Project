import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import '../styles/dashboardAnalytics.css';

const CHART_COLORS = ['#0b2545', '#134074', '#c9a227', '#1e5a8a', '#8a6d1f', '#2d6a4f'];

function formatShortDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function formatActionTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function DashboardAnalytics({ analytics, loading, error }) {
  if (loading) {
    return (
      <section className="dash-analytics card" aria-busy="true" aria-label="Intelligence analytics">
        <header className="dash-analytics-header">
          <h3>Intelligence analytics</h3>
          <p className="dash-analytics-subtitle">Loading charts…</p>
        </header>
        <div className="dash-analytics-skeleton">
          <div className="dash-skeleton-chart" />
          <div className="dash-skeleton-chart" />
          <div className="dash-skeleton-chart wide" />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="dash-analytics card" aria-label="Intelligence analytics">
        <header className="dash-analytics-header">
          <h3>Intelligence analytics</h3>
        </header>
        <div className="alert alert-error" role="alert">
          <p>{error}</p>
          <p className="dash-analytics-retry-hint">
            Charts are optional — dashboard stats above remain available.
          </p>
        </div>
      </section>
    );
  }

  if (!analytics) return null;

  const district = analytics.district || {};
  const uploads = analytics.uploads || {};
  const entity = analytics.entity_resolution || {};
  const ocr = analytics.ocr || {};
  const audit = analytics.audit || {};

  const districtData = district.top_districts || [];
  const uploadTrend = uploads.over_time || [];
  const matchStats = [
    { name: 'Confirmed', value: entity.confirmed_matches ?? 0, key: 'confirmed' },
    { name: 'Probable', value: entity.probable_matches ?? 0, key: 'probable' },
    { name: 'Manual review', value: entity.manual_review_count ?? 0, key: 'manual' },
  ];

  return (
    <section className="dash-analytics" aria-label="Intelligence analytics">
      <header className="dash-analytics-header card">
        <div>
          <h3>Intelligence analytics</h3>
          <p className="dash-analytics-subtitle">
            District distribution, upload trends, entity resolution, OCR, and officer activity
          </p>
        </div>
      </header>

      <div className="dash-analytics-grid">
        <article className="dash-chart-card card">
          <h4>District distribution</h4>
          <p className="dash-chart-meta">
            {district.total_citizens ?? 0} citizens · top {districtData.length} districts
          </p>
          {districtData.length > 0 ? (
            <div className="dash-chart-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={districtData} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d7dee8" />
                  <XAxis
                    dataKey="district"
                    tick={{ fontSize: 11, fill: '#6b7280' }}
                    angle={-28}
                    textAnchor="end"
                    height={56}
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      border: '1px solid #d7dee8',
                      borderRadius: 8,
                      fontSize: 13,
                    }}
                  />
                  <Bar dataKey="count" name="Citizens" radius={[4, 4, 0, 0]}>
                    {districtData.map((entry, index) => (
                      <Cell key={entry.district} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="dash-chart-empty">No district data available yet.</p>
          )}
        </article>

        <article className="dash-chart-card card">
          <h4>Upload trend</h4>
          <p className="dash-chart-meta">
            {uploads.total_uploads ?? 0} files · {uploads.total_imported_rows ?? 0} imported rows
          </p>
          {uploadTrend.length > 0 ? (
            <div className="dash-chart-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={uploadTrend} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d7dee8" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatShortDate}
                    tick={{ fontSize: 11, fill: '#6b7280' }}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} allowDecimals={false} />
                  <Tooltip
                    labelFormatter={formatShortDate}
                    contentStyle={{
                      border: '1px solid #d7dee8',
                      borderRadius: 8,
                      fontSize: 13,
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="uploads"
                    name="Uploads"
                    stroke="#0b2545"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="imported_rows"
                    name="Imported rows"
                    stroke="#c9a227"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="dash-chart-empty">No upload history to chart yet.</p>
          )}
        </article>

        <article className="dash-chart-card card">
          <h4>Entity resolution</h4>
          <p className="dash-chart-meta">
            {entity.total_reviews ?? 0} total review pairs
            {entity.pending_manual_review > 0 && (
              <> · {entity.pending_manual_review} pending manual</>
            )}
          </p>
          <div className="dash-chart-wrap dash-match-chart">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={matchStats} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#d7dee8" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#6b7280' }} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                />
                <Tooltip
                  contentStyle={{
                    border: '1px solid #d7dee8',
                    borderRadius: 8,
                    fontSize: 13,
                  }}
                />
                <Bar dataKey="value" name="Count" radius={[0, 4, 4, 0]}>
                  {matchStats.map((entry, index) => (
                    <Cell key={entry.key} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="dash-chart-card card dash-ocr-card">
          <h4>OCR summary</h4>
          <div className="dash-ocr-stats">
            <div className="dash-ocr-stat">
              <span className="dash-ocr-label">Processed documents</span>
              <strong className="dash-ocr-value">{ocr.processed_documents ?? 0}</strong>
            </div>
            <div className="dash-ocr-stat accent-gold">
              <span className="dash-ocr-label">Avg confidence</span>
              <strong className="dash-ocr-value">
                {(ocr.avg_confidence_score ?? 0).toFixed(1)}%
              </strong>
            </div>
          </div>
          {(ocr.processed_documents ?? 0) > 0 && (
            <div className="dash-chart-wrap dash-ocr-pie">
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie
                    data={[
                      { name: 'Confidence', value: ocr.avg_confidence_score || 0 },
                      { name: 'Remainder', value: Math.max(0, 100 - (ocr.avg_confidence_score || 0)) },
                    ]}
                    dataKey="value"
                    cx="50%"
                    cy="50%"
                    innerRadius={42}
                    outerRadius={62}
                    startAngle={90}
                    endAngle={-270}
                  >
                    <Cell fill="#c9a227" />
                    <Cell fill="#e8eef4" />
                  </Pie>
                  <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
          {(ocr.processed_documents ?? 0) === 0 && (
            <p className="dash-chart-empty">No OCR documents processed yet.</p>
          )}
        </article>

        <article className="dash-chart-card card dash-audit-card wide">
          <h4>Officer activity</h4>
          <p className="dash-chart-meta">
            {audit.officer_activity_count ?? 0} officers · {audit.total_actions ?? 0} total actions
          </p>
          <div className="dash-audit-layout">
            {(audit.officer_activity || []).length > 0 ? (
              <div className="dash-chart-wrap dash-officer-chart">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={audit.officer_activity} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d7dee8" />
                    <XAxis
                      dataKey="username"
                      tick={{ fontSize: 11, fill: '#6b7280' }}
                    />
                    <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        border: '1px solid #d7dee8',
                        borderRadius: 8,
                        fontSize: 13,
                      }}
                    />
                    <Bar dataKey="action_count" name="Actions" fill="#134074" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="dash-chart-empty">No audit activity recorded yet.</p>
            )}

            <div className="dash-recent-actions">
              <h5>Recent actions</h5>
              {(audit.recent_actions || []).length > 0 ? (
                <ul className="dash-action-list">
                  {audit.recent_actions.map((action) => (
                    <li key={action.id}>
                      <span className="dash-action-type">{action.action_type}</span>
                      <span className="dash-action-user">{action.username}</span>
                      <time className="dash-action-time" dateTime={action.created_at}>
                        {formatActionTime(action.created_at)}
                      </time>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="dash-chart-empty">No recent actions.</p>
              )}
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}
