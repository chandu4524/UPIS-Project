import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import {
  REPORT_ICONS,
  fetchReportData,
  isValidReportType,
} from '../services/reportsService';
import { formatError } from '../utils/formatError';
import '../styles/reportPreview.css';

export default function ReportPreview() {
  const { type } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const loadReport = useCallback(async () => {
    if (!isValidReportType(type)) {
      setError('Invalid report type');
      setReport(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await fetchReportData(type);
      setReport(data);
    } catch (err) {
      setError(formatError(err, 'Failed to load report preview'));
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [type]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const headers = report?.headers || [];
  const rows = report?.rows || [];
  const recordCount = report?.total ?? rows.length;
  const reportKey = report?.report_key || type;

  return (
    <Layout>
      {loading && <Loader label="Loading report preview..." />}

      <div className="report-preview-page">
        <nav className="report-preview-breadcrumb" aria-label="Breadcrumb">
          <Link to="/reports">← Back to reports</Link>
        </nav>

        {error && (
          <div className="alert alert-error">
            {error}
            <button
              type="button"
              className="btn btn-secondary report-preview-back-btn"
              onClick={() => navigate('/reports')}
            >
              Back to reports
            </button>
          </div>
        )}

        {!loading && !error && report && (
          <>
            <header className="report-preview-header-card card">
              <div className="report-preview-header-main">
                <span className="report-preview-icon" aria-hidden="true">
                  {REPORT_ICONS[reportKey] || '📊'}
                </span>
                <div>
                  <span className="report-preview-eyebrow">GPIP report preview</span>
                  <h1>{report.title || 'Report'}</h1>
                  {report.summary && <p className="report-preview-summary">{report.summary}</p>}
                </div>
              </div>
              <span className="report-preview-count-badge">
                {recordCount} record(s)
              </span>
            </header>

            <section className="report-preview-table-card card" aria-label="Report data table">
              <div className="report-preview-table-header">
                <h2>Data preview</h2>
                <span className="report-preview-showing">
                  Showing {rows.length} row(s) in preview
                </span>
              </div>
              <div className="report-preview-table-wrap">
                <table className="report-preview-table">
                  <thead>
                    <tr>
                      {headers.map((header) => (
                        <th key={header}>{String(header).replace(/_/g, ' ')}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.length > 0 ? (
                      rows.map((row, rowIdx) => (
                        <tr key={rowIdx}>
                          {row.map((cell, cellIdx) => (
                            <td key={`${rowIdx}-${cellIdx}`}>
                              {cell === null || cell === undefined || cell === ''
                                ? '—'
                                : String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={Math.max(headers.length, 1)}>No data rows</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </Layout>
  );
}
