import { useCallback, useEffect, useState } from 'react';
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
import Layout from '../components/Layout';
import { fetchAnalyticsDashboard } from '../services/analyticsService';
import { formatError } from '../utils/formatError';
import '../styles/analyticsDashboard.css';

const CHART_COLORS = ['#0b2545', '#134074', '#c9a227', '#1e5a8a', '#8a6d1f', '#2d6a4f', '#9b2226'];

const EMPTY_WIDGET_ERRORS = {
  summary: null,
  sources: null,
  validation: null,
  trends: null,
};

function formatNumber(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return '0';
  return n.toLocaleString();
}

function formatShortDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function KpiCard({ label, value, accent = '' }) {
  return (
    <article className={`analytics-kpi-card ${accent}`}>
      <span className="analytics-kpi-label">{label}</span>
      <strong className="analytics-kpi-value">{value}</strong>
    </article>
  );
}

function WidgetError({ message }) {
  if (!message) return null;
  return (
    <div className="analytics-widget-error" role="alert">
      <p>{message}</p>
    </div>
  );
}

function EmptyChart({ message }) {
  return (
    <div className="analytics-empty" role="status">
      <span className="analytics-empty-icon" aria-hidden="true">
        📊
      </span>
      <p>{message}</p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="analytics-loading-block" aria-busy="true" aria-label="Loading analytics dashboard">
      <p className="analytics-loading-label">Loading dashboard…</p>
      <div className="analytics-skeleton-grid">
        {Array.from({ length: 6 }).map((_, idx) => (
          <div key={idx} className="analytics-skeleton-card" />
        ))}
      </div>
      <div className="analytics-charts-grid">
        <div className="analytics-skeleton-chart" />
        <div className="analytics-skeleton-chart" />
        <div className="analytics-skeleton-chart wide" />
      </div>
    </div>
  );
}

export default function AnalyticsDashboard() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [sources, setSources] = useState([]);
  const [validation, setValidation] = useState([]);
  const [trends, setTrends] = useState([]);
  const [widgetErrors, setWidgetErrors] = useState(EMPTY_WIDGET_ERRORS);
  const [loadError, setLoadError] = useState('');

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setLoadError('');

    try {
      const data = await fetchAnalyticsDashboard();

      setSummary(data.summary ?? null);
      setSources(Array.isArray(data.sources) ? data.sources : []);
      setValidation(Array.isArray(data.validation) ? data.validation : []);
      setTrends(Array.isArray(data.trends) ? data.trends : []);
      setWidgetErrors(data.errors ?? EMPTY_WIDGET_ERRORS);

      const allFailed =
        !data.summary &&
        (!data.sources || data.sources.length === 0) &&
        (!data.validation || data.validation.length === 0) &&
        (!data.trends || data.trends.length === 0) &&
        Object.values(data.errors ?? {}).every(Boolean);

      if (allFailed) {
        setLoadError('Unable to load analytics data. Please try again.');
      }
    } catch (err) {
      console.warn('[Analytics] dashboard load failed', err);
      setLoadError(formatError(err, 'Failed to load analytics dashboard'));
      setSummary(null);
      setSources([]);
      setValidation([]);
      setTrends([]);
      setWidgetErrors(EMPTY_WIDGET_ERRORS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const validationList = Array.isArray(validation) ? validation : [];
  const sourcesList = Array.isArray(sources) ? sources : [];
  const trendsList = Array.isArray(trends) ? trends : [];

  const hasData = Boolean(
    summary?.total_uploads ||
      summary?.total_records ||
      sourcesList.length > 0 ||
      validationList.length > 0 ||
      trendsList.length > 0
  );

  const validationTotal = validationList.reduce(
    (sum, item) => sum + Number(item?.count || 0),
    0
  );

  const showContent = !loading;

  return (
    <Layout>
      <div className="page-content analytics-dashboard">
        <header className="analytics-dashboard-header">
          <div>
            <h2>Upload analytics overview</h2>
            <p>DuckDB-powered metrics from uploaded files and validation results.</p>
          </div>
          <button type="button" className="btn btn-secondary" onClick={loadDashboard} disabled={loading}>
            Refresh
          </button>
        </header>

        {loading && <LoadingSkeleton />}

        {showContent && loadError && !summary && (
          <div className="alert alert-error" role="alert">
            <p>{loadError}</p>
            <button type="button" className="btn btn-secondary" onClick={loadDashboard} style={{ marginTop: 12 }}>
              Retry
            </button>
          </div>
        )}

        {showContent && (
          <>
            <section className="analytics-kpi-grid" aria-label="Key performance indicators">
              {widgetErrors.summary ? (
                <div className="analytics-kpi-card analytics-kpi-error-span">
                  <WidgetError message={`Summary: ${widgetErrors.summary}`} />
                </div>
              ) : (
                <>
                  <KpiCard label="Total Uploads" value={formatNumber(summary?.total_uploads)} />
                  <KpiCard label="Total Records" value={formatNumber(summary?.total_records)} />
                  <KpiCard label="Valid Records" value={formatNumber(summary?.valid_records)} accent="accent-success" />
                  <KpiCard label="Invalid Records" value={formatNumber(summary?.invalid_records)} accent="accent-danger" />
                  <KpiCard label="Duplicate Records" value={formatNumber(summary?.duplicate_records)} />
                  <KpiCard
                    label="Success Rate"
                    value={`${formatNumber(summary?.success_rate ?? 0)}%`}
                    accent="accent-gold"
                  />
                </>
              )}
            </section>

            {!hasData && !widgetErrors.summary ? (
              <div className="analytics-table-card">
                <EmptyChart message="No upload analytics yet. Upload files to populate the dashboard." />
              </div>
            ) : (
              <>
                <section className="analytics-charts-grid" aria-label="Analytics charts">
                  <article className="analytics-chart-card">
                    <h3>Source distribution</h3>
                    <p className="analytics-chart-subtitle">Records grouped by data source</p>
                    <WidgetError message={widgetErrors.sources} />
                    {!widgetErrors.sources && sourcesList.length === 0 ? (
                      <EmptyChart message="No source distribution data available." />
                    ) : !widgetErrors.sources ? (
                      <div className="analytics-chart-body">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={sourcesList} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,37,69,0.08)" />
                            <XAxis
                              dataKey="source"
                              tick={{ fontSize: 12 }}
                              interval={0}
                              angle={-20}
                              textAnchor="end"
                              height={60}
                            />
                            <YAxis tick={{ fontSize: 12 }} />
                            <Tooltip formatter={(value) => formatNumber(value)} />
                            <Legend />
                            <Bar dataKey="records" name="Records" fill="#134074" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : null}
                  </article>

                  <article className="analytics-chart-card">
                    <h3>Validation distribution</h3>
                    <p className="analytics-chart-subtitle">Valid, invalid, and duplicate record counts</p>
                    <WidgetError message={widgetErrors.validation} />
                    {!widgetErrors.validation && validationTotal === 0 ? (
                      <EmptyChart message="Validation metrics will appear after new uploads." />
                    ) : !widgetErrors.validation ? (
                      <div className="analytics-chart-body">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={validationList}
                              dataKey="count"
                              nameKey="label"
                              cx="50%"
                              cy="50%"
                              outerRadius={95}
                              label={({ label, percent }) =>
                                `${label}: ${(percent * 100).toFixed(0)}%`
                              }
                            >
                              {validationList.map((entry, idx) => (
                                <Cell key={entry.label} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip formatter={(value) => formatNumber(value)} />
                            <Legend />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    ) : null}
                  </article>

                  <article className="analytics-chart-card wide">
                    <h3>Upload trends</h3>
                    <p className="analytics-chart-subtitle">Upload activity over time</p>
                    <WidgetError message={widgetErrors.trends} />
                    {!widgetErrors.trends && trendsList.length === 0 ? (
                      <EmptyChart message="No upload trend data available." />
                    ) : !widgetErrors.trends ? (
                      <div className="analytics-chart-body tall">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={trendsList} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,37,69,0.08)" />
                            <XAxis dataKey="date" tickFormatter={formatShortDate} tick={{ fontSize: 12 }} />
                            <YAxis tick={{ fontSize: 12 }} />
                            <Tooltip
                              labelFormatter={formatShortDate}
                              formatter={(value) => formatNumber(value)}
                            />
                            <Legend />
                            <Line
                              type="monotone"
                              dataKey="uploads"
                              name="Uploads"
                              stroke="#0b2545"
                              strokeWidth={2.5}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />
                            <Line
                              type="monotone"
                              dataKey="records"
                              name="Records"
                              stroke="#c9a227"
                              strokeWidth={2.5}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    ) : null}
                  </article>
                </section>

                <section className="analytics-table-card" aria-label="Source-wise summary">
                  <h3>Source-wise summary</h3>
                  <WidgetError message={widgetErrors.sources} />
                  {!widgetErrors.sources && sourcesList.length === 0 ? (
                    <EmptyChart message="No source summary available." />
                  ) : !widgetErrors.sources ? (
                    <div className="analytics-table-wrap">
                      <table className="analytics-table">
                        <thead>
                          <tr>
                            <th>Source</th>
                            <th>Files</th>
                            <th>Records</th>
                            <th>Errors</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sourcesList.map((row) => (
                            <tr key={row.source}>
                              <td>{row.source}</td>
                              <td>{formatNumber(row.files)}</td>
                              <td>{formatNumber(row.records)}</td>
                              <td>{formatNumber(row.errors)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </section>
              </>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
