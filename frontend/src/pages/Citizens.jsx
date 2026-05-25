import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import PageError from '../components/PageError';
import SensitiveAccessBadge from '../components/SensitiveAccessBadge';
import Pagination from '../components/Pagination';
import SortableTh from '../components/SortableTh';
import Spinner from '../components/Spinner';
import { fetchCitizens } from '../services/citizenService';
import { subscribeCitizenRefresh } from '../utils/appRefresh';
import { formatError } from '../utils/formatError';
import '../styles/citizens.css';

const PAGE_SIZE = 10;

const EMPTY_FILTERS = { name: '', mobile: '', district: '', village: '' };

function hasActiveFilters(filters) {
  return Object.values(filters).some((v) => String(v || '').trim());
}

export default function Citizens() {
  const navigate = useNavigate();
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(EMPTY_FILTERS);
  const [sortBy, setSortBy] = useState('full_name');
  const [sortOrder, setSortOrder] = useState('asc');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);
  const [accessFlags, setAccessFlags] = useState({});

  const loadCitizens = useCallback(async ({
    searchFilters = appliedFilters,
    pageNum = 1,
    sortField = sortBy,
    sortDir = sortOrder,
  } = {}) => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchCitizens({
        name: searchFilters.name,
        mobile: searchFilters.mobile,
        district: searchFilters.district,
        village: searchFilters.village,
        page: pageNum,
        pageSize: PAGE_SIZE,
        sortBy: sortField,
        sortOrder: sortDir,
      });
      setRecords(data.items || []);
      setAccessFlags({
        can_view_sensitive_fields: data.can_view_sensitive_fields,
        sensitive_fields_masked: data.sensitive_fields_masked,
      });
      setTotal(data.total ?? 0);
      setTotalPages(data.total_pages ?? 0);
      setPage(data.page ?? pageNum);
      setSortBy(sortField);
      setSortOrder(sortDir);
      setAppliedFilters(searchFilters);
    } catch (err) {
      setError(formatError(err, 'Failed to load citizen records'));
      setRecords([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
      setInitialLoad(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadCitizens({ pageNum: 1 });
  }, [loadCitizens]);

  useEffect(() => {
    return subscribeCitizenRefresh(() => loadCitizens({ pageNum: 1 }));
  }, [loadCitizens]);

  const handleFilterChange = (field, value) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleSearch = (e) => {
    if (e) e.preventDefault();
    setAppliedFilters(filters);
    setPage(1);
    loadCitizens({ searchFilters: filters, pageNum: 1 });
  };

  const handleResetFilters = () => {
    setFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
    loadCitizens({ searchFilters: EMPTY_FILTERS, pageNum: 1 });
  };

  const handleSort = (field) => {
    const nextOrder =
      sortBy === field && sortOrder === 'asc' ? 'desc' : 'asc';
    loadCitizens({ sortField: field, sortDir: nextOrder, pageNum: 1 });
  };

  const handlePageChange = (nextPage) => {
    loadCitizens({ pageNum: nextPage });
  };

  const showEmpty = !loading && !error && records.length === 0;
  const showTable = !loading && !error && records.length > 0;
  const searching = loading && !initialLoad;

  const openProfile = (citizenId) => {
    navigate(`/person-profile/${citizenId}`);
  };

  const handleRowKeyDown = (e, citizenId) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openProfile(citizenId);
    }
  };

  return (
    <Layout>
      {loading && initialLoad && <Loader label="Loading intelligence search..." />}

      <div className="citizens-page">
        <section className="intelligence-intro card">
          <h2>Intelligence search</h2>
          <p>
            Query citizen records by identity, contact, and location attributes. Results
            update from the secure GPIP registry.
          </p>
        </section>

        <div className="search-card card">
          <div className="search-card-header">
            <h3>Search filters</h3>
            {hasActiveFilters(appliedFilters) && (
              <span className="filters-active-badge">Filters applied</span>
            )}
          </div>
          <form className="search-form" onSubmit={handleSearch}>
            <label>
              Full name
              <input
                type="text"
                placeholder="e.g. Chandu Reddy"
                value={filters.name}
                onChange={(e) => handleFilterChange('name', e.target.value)}
                disabled={loading}
              />
            </label>
            <label>
              Mobile number
              <input
                type="text"
                placeholder="e.g. 9876543210"
                value={filters.mobile}
                onChange={(e) => handleFilterChange('mobile', e.target.value)}
                disabled={loading}
              />
            </label>
            <label>
              District
              <input
                type="text"
                placeholder="e.g. Visakhapatnam"
                value={filters.district}
                onChange={(e) => handleFilterChange('district', e.target.value)}
                disabled={loading}
              />
            </label>
            <label>
              Village
              <input
                type="text"
                placeholder="e.g. Pedagadi"
                value={filters.village}
                onChange={(e) => handleFilterChange('village', e.target.value)}
                disabled={loading}
              />
            </label>
            <div className="search-actions">
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {searching ? (
                  <Spinner label="Searching..." inline />
                ) : (
                  'Search'
                )}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleResetFilters}
                disabled={loading}
              >
                Reset filters
              </button>
            </div>
          </form>
        </div>

        {error && (
          <PageError
            message={error}
            onRetry={() => loadCitizens({ pageNum: page })}
            retryLabel="Reload records"
          />
        )}

        <div className={`table-card card ${searching ? 'table-card-loading' : ''}`}>
          <div className="table-header">
            <h2>Search results</h2>
            <div className="table-header-meta">
              <SensitiveAccessBadge {...accessFlags} />
              {searching && (
                <span className="search-status" role="status">
                  <Spinner label="Fetching results..." inline />
                </span>
              )}
              <span className="record-count">
                {total} intelligence record{total === 1 ? '' : 's'} found
              </span>
            </div>
          </div>

          {showEmpty && (
            <div className="empty-state">
              <div className="empty-state-icon" aria-hidden="true">
                🔍
              </div>
              <h3>No matching intelligence records found</h3>
              <p>
                {hasActiveFilters(appliedFilters)
                  ? 'Adjust your search filters or reset to view all registered citizens.'
                  : 'No citizens are registered yet. Upload a CSV from the File Upload page.'}
              </p>
            </div>
          )}

          {showTable && (
            <>
              <div className="table-wrap">
                <table className="citizen-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <SortableTh
                        label="Full name"
                        field="full_name"
                        sortBy={sortBy}
                        sortOrder={sortOrder}
                        onSort={handleSort}
                      />
                      <SortableTh
                        label="Mobile"
                        field="mobile"
                        sortBy={sortBy}
                        sortOrder={sortOrder}
                        onSort={handleSort}
                      />
                      <SortableTh
                        label="District"
                        field="district"
                        sortBy={sortBy}
                        sortOrder={sortOrder}
                        onSort={handleSort}
                      />
                      <th>Village</th>
                      <th>DOB</th>
                      <th>Profile</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((row) => (
                      <tr
                        key={row.id}
                        className="citizen-row-clickable"
                        onClick={() => openProfile(row.id)}
                        onKeyDown={(e) => handleRowKeyDown(e, row.id)}
                        tabIndex={0}
                        role="link"
                        aria-label={`View profile for ${row.full_name || 'citizen'}`}
                      >
                        <td>{row.id}</td>
                        <td>{row.full_name}</td>
                        <td
                          className={
                            accessFlags.sensitive_fields_masked ? 'sensitive-field-masked' : ''
                          }
                        >
                          {row.mobile}
                        </td>
                        <td>{row.district}</td>
                        <td>{row.village}</td>
                        <td>{row.dob}</td>
                        <td
                          className="citizen-actions-cell"
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            className="btn btn-secondary btn-view-profile"
                            onClick={() => openProfile(row.id)}
                          >
                            View Profile
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                totalPages={totalPages}
                total={total}
                onPageChange={handlePageChange}
                disabled={loading}
              />
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
