import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import SensitiveAccessBadge from '../components/SensitiveAccessBadge';
import Spinner from '../components/Spinner';
import { fetchIntelligenceSearch } from '../services/intelligenceSearchService';
import { formatError } from '../utils/formatError';
import '../styles/intelligenceSearch.css';

const FIELD_LABELS = {
  full_name: 'Name',
  mobile: 'Mobile',
  district: 'District',
  village: 'Village',
  father_name: 'Father name',
  consumer_id: 'LPG / Consumer no',
  connection_no: 'Connection no',
  aadhaar: 'Aadhaar ref',
  customer_id: 'Customer ID',
  exact_match: 'Exact match',
  bank_ref: 'Bank ref',
  lpg_consumer_no: 'LPG consumer no',
};

const SUGGEST_DEBOUNCE_MS = 280;

function relevanceBadgeClass(score) {
  const value = Number(score) || 0;
  if (value >= 85) return 'intel-relevance-badge intel-relevance-high';
  if (value >= 65) return 'intel-relevance-badge intel-relevance-medium';
  return 'intel-relevance-badge intel-relevance-low';
}

function formatRelevance(score) {
  const value = Number(score);
  if (Number.isNaN(value)) return '—';
  return `${value.toFixed(0)}%`;
}

function formatMatchFieldLabel(field) {
  if (!field) return 'Field';
  return FIELD_LABELS[field] || field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function matchBadgeClass(badge) {
  return badge === 'EXACT MATCH'
    ? 'intel-match-badge intel-match-exact'
    : 'intel-match-badge intel-match-fuzzy';
}

function openProfile(navigate, row) {
  const citizenId = row.citizen_id || (row.match_type === 'citizen' ? row.id : null);
  const stagingId = row.staging_id;
  if (citizenId) {
    const qs = stagingId ? `?staging_id=${stagingId}` : '';
    navigate(`/person-profile/${citizenId}${qs}`, {
      state: stagingId ? { focusStagingId: String(stagingId) } : undefined,
    });
    return;
  }
  if (stagingId) {
    navigate(`/intelligence-search`, {
      state: { message: 'This upload record is not linked to a citizen profile yet.' },
    });
  }
}

function HighlightedValue({ text, spans = [] }) {
  if (!text) return '—';
  if (!spans?.length) return text;

  const parts = [];
  let cursor = 0;
  const sorted = [...spans].sort((a, b) => a[0] - b[0]);

  sorted.forEach(([start, end], idx) => {
    const s = Math.max(0, start);
    const e = Math.min(text.length, end);
    if (s > cursor) {
      parts.push(<span key={`t-${idx}-pre`}>{text.slice(cursor, s)}</span>);
    }
    if (e > s) {
      parts.push(
        <mark key={`m-${idx}`}>{text.slice(s, e)}</mark>,
      );
      cursor = e;
    }
  });

  if (cursor < text.length) {
    parts.push(<span key="tail">{text.slice(cursor)}</span>);
  }

  return <>{parts.length ? parts : text}</>;
}

function renderFieldValue(row, field, masked) {
  const highlight = row.highlights?.[field];
  const raw = row[field] ?? highlight?.text ?? '';
  const className = masked && field === 'mobile' ? 'sensitive-field-masked' : '';
  if (highlight?.spans?.length && !masked) {
    return <HighlightedValue text={highlight.text || raw} spans={highlight.spans} />;
  }
  return <span className={className}>{raw || '—'}</span>;
}

export default function IntelligenceSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [stagingResults, setStagingResults] = useState([]);
  const [ambiguousGroups, setAmbiguousGroups] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [total, setTotal] = useState(0);
  const [searchedQuery, setSearchedQuery] = useState('');
  const [accessFlags, setAccessFlags] = useState({});
  const [loading, setLoading] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef(null);
  const inputRef = useRef(null);

  const runSearch = useCallback(async (searchText, { forSuggestions = false } = {}) => {
    const q = (searchText || '').trim();
    if (!q) {
      setResults([]);
      setStagingResults([]);
      setAmbiguousGroups([]);
      setSuggestions([]);
      setTotal(0);
      setSearchedQuery('');
      return;
    }

    if (forSuggestions) {
      setSuggestLoading(true);
    } else {
      setLoading(true);
      setError('');
    }

    try {
      const data = await fetchIntelligenceSearch(q, {
        limit: forSuggestions ? 8 : 25,
      });
      if (forSuggestions) {
        setSuggestions(data.suggestions || []);
      } else {
        setResults(data.results || []);
        setStagingResults([]);
        setAmbiguousGroups(data.ambiguous_groups || []);
        setSuggestions(data.suggestions || []);
        setTotal(data.total ?? (data.results || []).length);
        setSearchedQuery(data.query || q);
        setAccessFlags({
          can_view_sensitive_fields: data.can_view_sensitive_fields,
          sensitive_fields_masked: data.sensitive_fields_masked,
        });
        setShowSuggestions(false);
      }
    } catch (err) {
      if (!forSuggestions) {
        setError(formatError(err, 'Intelligence search failed'));
        setResults([]);
        setStagingResults([]);
        setAmbiguousGroups([]);
        setTotal(0);
      }
    } finally {
      if (forSuggestions) setSuggestLoading(false);
      else setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const q = query.trim();
    if (q.length < 2) {
      setSuggestions([]);
      setSuggestLoading(false);
      return undefined;
    }

    debounceRef.current = setTimeout(() => {
      if (showSuggestions) {
        runSearch(q, { forSuggestions: true });
      }
    }, SUGGEST_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, showSuggestions, runSearch]);

  const handleSubmit = (e) => {
    e.preventDefault();
    runSearch(query);
  };

  const applySuggestion = (value) => {
    setQuery(value);
    setShowSuggestions(false);
    runSearch(value);
  };

  const hasSearched = Boolean(searchedQuery);
  const noResults =
    hasSearched &&
    !loading &&
    results.length === 0 &&
    stagingResults.length === 0 &&
    ambiguousGroups.length === 0 &&
    !error;

  const renderResultCard = (row, keyPrefix = 'r') => (
    <article key={`${keyPrefix}-${row.staging_id || row.id || row.citizen_id}`} className="intel-result-card">
      <header className="intel-result-header">
        <h4 className="intel-result-name">{renderFieldValue(row, 'full_name')}</h4>
        <div className="intel-result-badges">
          <span className={matchBadgeClass(row.match_badge)}>
            {row.match_badge || (row.match_priority <= 2 ? 'EXACT MATCH' : 'FUZZY MATCH')}
          </span>
          <span className={relevanceBadgeClass(row.relevance_score)}>
            {formatRelevance(row.relevance_score)}
          </span>
        </div>
      </header>

      {row.match_field && row.match_value && (
        <p className="intel-exact-hit">
          Matched on <strong>{row.match_field_label || formatMatchFieldLabel(row.match_field)}</strong>
          : {row.match_value}
        </p>
      )}

      {(row.source_label || row.match_type === 'staging' || row.match_type === 'duckdb') && (
        <p className="intel-staging-note">
          Source: {row.source_label || `${row.department_name || 'Upload'} · ${row.source_name || 'Record'}`}
          {row.upload_batch_id ? ` · Batch #${row.upload_batch_id}` : ''}
        </p>
      )}

      <div className="intel-matched-tags" aria-label="Matched fields">
        {(row.matched_fields || []).map((field) => (
          <span key={field} className="intel-field-tag">
            {FIELD_LABELS[field] || field}
          </span>
        ))}
      </div>

      <div className="intel-result-fields">
        {['mobile', 'district', 'village', 'father_name'].map((field) => {
          const show = row[field] || row.matched_fields?.includes(field);
          if (!show) return null;
          return (
            <div key={field} className="intel-field-row">
              <span className="intel-field-label">{FIELD_LABELS[field]}:</span>
              <span className="intel-field-value">
                {renderFieldValue(row, field, accessFlags.sensitive_fields_masked)}
              </span>
            </div>
          );
        })}
        {row.source_id && row.match_field !== 'consumer_id' && (
          <div className="intel-field-row">
            <span className="intel-field-label">Identifier:</span>
            <span className="intel-field-value">{row.source_id}</span>
          </div>
        )}
      </div>

      <div className="intel-result-actions">
        {row.citizen_id || row.staging_id ? (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => openProfile(navigate, row)}
          >
            View 360 profile
          </button>
        ) : (
          <span className="intel-unlinked-label">Upload record — link via manual review</span>
        )}
      </div>
    </article>
  );

  return (
    <Layout>
      <div className="intel-search-page">
        <section className="intel-search-intro card">
          <h2>Advanced intelligence search</h2>
          <p>
            Search across citizen registry, upload staging, and source identifiers (LPG consumer
            no, Aadhaar ref, mobile, and all uploaded fields). Fuzzy name matching with duplicate-name
            disambiguation.
          </p>
        </section>

        <section className="intel-search-bar-card card">
          <form className="intel-search-form" onSubmit={handleSubmit}>
            <div className="intel-search-input-wrap">
              <input
                ref={inputRef}
                type="search"
                className="intel-search-input"
                placeholder="Search intelligence records…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => {
                  setTimeout(() => setShowSuggestions(false), 180);
                }}
                aria-label="Global intelligence search"
                autoComplete="off"
              />
              {showSuggestions && suggestions.length > 0 && (
                <ul className="intel-suggestions" role="listbox">
                  {suggestions.map((item) => (
                    <li key={item}>
                      <button
                        type="button"
                        className="intel-suggestion-item"
                        role="option"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => applySuggestion(item)}
                      >
                        {item}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <button
              type="submit"
              className="btn btn-primary intel-search-btn"
              disabled={loading || !query.trim()}
            >
              {loading ? 'Searching…' : 'Search'}
            </button>
          </form>

          <p className="intel-search-hints">
            <strong>Tip:</strong> Try partial names, districts with spelling variants, or last digits of a mobile number.
            Citizen Records keeps its own filter-based search unchanged.
          </p>

          {(loading || suggestLoading) && (
            <div className="intel-processing-row" role="status">
              <Spinner />
              <span>{loading ? 'Ranking matches…' : 'Loading suggestions…'}</span>
            </div>
          )}

          {error && (
            <div className="alert alert-error" role="alert">
              {error}
            </div>
          )}
        </section>

        {ambiguousGroups.length > 0 && (
          <section className="intel-ambiguous-section card">
            <h3>Multiple matching profiles found</h3>
            <p className="intel-results-meta">
              Same name matched different people. Select the correct profile — records are not merged
              automatically.
            </p>
            {ambiguousGroups.map((group) => (
              <div key={group.normalized_name} className="intel-ambiguous-group">
                <h4>{group.display_name || group.normalized_name}</h4>
                <div className="intel-results-grid">
                  {(group.candidates || []).map((candidate) =>
                    renderResultCard(
                      {
                        ...candidate,
                        id: candidate.citizen_id,
                        matched_fields: candidate.matched_fields || ['full_name'],
                      },
                      `amb-${group.normalized_name}`
                    )
                  )}
                </div>
              </div>
            ))}
          </section>
        )}

        {(results.length > 0 || stagingResults.length > 0) && (
          <section className="intel-results-section card">
            <div className="intel-results-title-row">
              <h3>Ranked results</h3>
              <SensitiveAccessBadge {...accessFlags} />
            </div>
            <p className="intel-results-meta">
              Showing {(results.length || 0) + (stagingResults.length || 0)} of {total} match
              {total === 1 ? '' : 'es'} for &ldquo;{searchedQuery}&rdquo;
              {searchedQuery && /^[a-zA-Z]*\d/i.test(searchedQuery) ? ' · exact identifiers ranked first' : ''}
            </p>
            <div className="intel-results-grid">
              {results.map((row) => renderResultCard(row))}
              {stagingResults.map((row) => renderResultCard(row, 's'))}
            </div>
          </section>
        )}

        {noResults && (
          <section className="intel-empty-card card" aria-live="polite">
            <h3>No matching intelligence records</h3>
            <p>
              No ranked results for &ldquo;{searchedQuery}&rdquo;. Try a shorter query, check spelling variants,
              or search by district or mobile instead.
            </p>
            <p className="intel-empty-examples">
              Examples: Chndu · Vizg · 98XXXX · Rampur
            </p>
          </section>
        )}

        {!hasSearched && !loading && (
          <section className="intel-empty-card card">
            <h3>Start a fuzzy search</h3>
            <p>
              Enter a name, location, or mobile number above. Results are ranked by relevance with matched fields highlighted.
            </p>
            <p className="intel-empty-examples">
              Examples: Chndu → Chandu · Vizg → Visakhapatnam
            </p>
          </section>
        )}
      </div>
    </Layout>
  );
}
