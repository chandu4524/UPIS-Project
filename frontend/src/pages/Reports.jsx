import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import {
  REPORT_ICONS,
  exportReportExcel,
  exportReportPdf,
  fetchReports,
} from '../services/reportsService';
import { formatError } from '../utils/formatError';
import '../styles/reports.css';

export default function Reports() {
  const navigate = useNavigate();
  const [reportCards, setReportCards] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchReports();
      setReportCards(data.reports || []);
    } catch (err) {
      setError(formatError(err, 'Failed to load reports'));
      setReportCards([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleViewReport = (reportKey) => {
    navigate(`/reports/preview/${reportKey}`);
  };

  const handleExport = async (format, reportKey) => {
    setExporting(`${format}-${reportKey}`);
    setError('');
    try {
      if (format === 'pdf') {
        await exportReportPdf(reportKey);
      } else {
        await exportReportExcel(reportKey);
      }
    } catch (err) {
      setError(formatError(err, `Failed to export ${format.toUpperCase()}`));
    } finally {
      setExporting(null);
    }
  };

  return (
    <Layout>
      {loading && <Loader label="Loading reports..." />}

      <div className="reports-page">
        <section className="reports-intro card">
          <h2>Reports &amp; export</h2>
          <p>
            Generate intelligence summaries from citizens, uploads, audit activity, and
            district statistics. Preview on screen or download as PDF or Excel.
          </p>
        </section>

        {error && <div className="alert alert-error">{error}</div>}

        {!loading && (
          <div className="reports-grid">
            {reportCards.map((report) => {
              const key = report.id;
              const busyPdf = exporting === `pdf-${key}`;
              const busyExcel = exporting === `excel-${key}`;
              return (
                <article key={key} className="report-card card">
                  <div className="report-card-icon" aria-hidden="true">
                    {REPORT_ICONS[key] || '📊'}
                  </div>
                  <h3>{report.name}</h3>
                  <p>{report.description}</p>
                  <span className="report-record-badge">
                    {report.record_count ?? 0} record(s)
                  </span>
                  <div className="report-card-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => handleViewReport(key)}
                    >
                      View report
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleExport('pdf', key)}
                      disabled={!!exporting}
                    >
                      {busyPdf ? 'Exporting…' : 'Export PDF'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleExport('excel', key)}
                      disabled={!!exporting}
                    >
                      {busyExcel ? 'Exporting…' : 'Export Excel'}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
}
