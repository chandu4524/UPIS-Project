import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import Spinner from '../components/Spinner';
import {
  SUGGESTED_PROMPTS,
  sendAssistantQuery,
} from '../services/assistantService';
import { formatError } from '../utils/formatError';
import '../styles/aiAssistant.css';

const STORAGE_KEY = 'gpip_assistant_history';

function normalizeMessage(msg) {
  if (!msg || typeof msg !== 'object') return null;
  const text = msg.content ?? msg.answer ?? '';
  const role = msg.role === 'user' ? 'user' : 'assistant';
  return {
    ...msg,
    id: msg.id || `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    role,
    content: typeof text === 'string' ? text : String(text ?? ''),
    answer: typeof text === 'string' ? text : String(text ?? ''),
    suggested_actions: Array.isArray(msg.suggested_actions) ? msg.suggested_actions : [],
    related_links: Array.isArray(msg.related_links) ? msg.related_links : [],
    createdAt: msg.createdAt || new Date().toISOString(),
  };
}

function loadHistory() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeMessage).filter(Boolean);
  } catch {
    return [];
  }
}

function saveHistory(messages) {
  try {
    const normalized = messages.map(normalizeMessage).filter(Boolean);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(normalized.slice(-40)));
  } catch {
    /* ignore quota */
  }
}

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function getMessageText(msg) {
  const raw = msg?.content ?? msg?.answer ?? '';
  return typeof raw === 'string' ? raw : String(raw ?? '');
}

function renderAnswerText(text) {
  const value = (text || '').trim();
  if (!value) return null;

  const parts = value.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`b-${i}`}>{part.slice(2, -2)}</strong>;
    }
    return part ? <span key={`t-${i}`}>{part}</span> : null;
  });
}

function ActionLinks({ actions = [], links = [], navigate }) {
  const safeActions = actions.filter((item) => item && item.label && item.path);
  const safeLinks = links.filter((item) => item && item.label && item.path);

  if (!safeActions.length && !safeLinks.length) return null;

  return (
    <div className="ai-response-card">
      {safeActions.length > 0 && (
        <>
          <h5>Suggested actions</h5>
          <ul className="ai-action-list">
            {safeActions.map((item) => (
              <li key={`${item.label}-${item.path}`}>
                <button
                  type="button"
                  className="ai-action-btn"
                  onClick={() => navigate(item.path)}
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {safeLinks.length > 0 && (
        <>
          <h5 style={{ marginTop: safeActions.length ? '0.75rem' : 0 }}>Related links</h5>
          <ul className="ai-action-list">
            {safeLinks.map((item) => (
              <li key={`${item.label}-${item.path}`}>
                <Link to={item.path} className="ai-action-btn gold">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default function AIAssistant() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState(() => loadHistory());
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);
  const inFlightRef = useRef(false);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!loading) {
      saveHistory(messages);
    }
  }, [messages, loading]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const appendAssistantMessage = useCallback((payload) => {
    const answerText = (payload.answer || '').trim() || 'No response available.';
    const assistantMsg = normalizeMessage({
      id: `a-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      role: 'assistant',
      content: answerText,
      answer: answerText,
      suggested_actions: payload.suggested_actions || [],
      related_links: payload.related_links || [],
      intent: payload.intent,
      createdAt: new Date().toISOString(),
    });

    setMessages((prev) => {
      const list = Array.isArray(prev) ? prev : [];
      return [...list, assistantMsg];
    });
  }, []);

  const submitQuery = useCallback(async (text) => {
    const q = (text || '').trim();
    if (!q || inFlightRef.current) return;

    const reqId = ++requestIdRef.current;
    inFlightRef.current = true;
    setError('');
    setLoading(true);

    const userMsg = normalizeMessage({
      id: `u-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      role: 'user',
      content: q,
      createdAt: new Date().toISOString(),
    });

    setMessages((prev) => {
      const list = Array.isArray(prev) ? prev : [];
      return [...list, userMsg];
    });
    setInput('');

    try {
      const payload = await sendAssistantQuery(q);
      if (reqId !== requestIdRef.current) return;
      appendAssistantMessage(payload);
    } catch (err) {
      if (reqId === requestIdRef.current) {
        setError(formatError(err, 'Assistant request failed'));
      }
    } finally {
      if (reqId === requestIdRef.current) {
        inFlightRef.current = false;
        setLoading(false);
      }
    }
  }, [appendAssistantMessage]);

  const handleSubmit = (e) => {
    e.preventDefault();
    submitQuery(input);
  };

  const handlePromptClick = (prompt) => {
    submitQuery(prompt);
  };

  const clearHistory = () => {
    requestIdRef.current += 1;
    inFlightRef.current = false;
    setLoading(false);
    setMessages([]);
    sessionStorage.removeItem(STORAGE_KEY);
  };

  const hasMessages = messages.length > 0;

  return (
    <Layout>
      <div className="ai-assistant-page">
        <section className="ai-assistant-intro card">
          <h2>AI Intelligence Assistant</h2>
          <p>
            Ask questions about districts, citizens, OCR, audits, and manual review — powered by live GPIP data.
          </p>
        </section>

        <section className="ai-chat-card card" aria-label="Assistant conversation">
          <div className="ai-chat-messages">
            {!hasMessages && !loading && (
              <div className="ai-empty-state">
                <div className="ai-empty-icon" aria-hidden="true">
                  ◆
                </div>
                <h3>How can I help?</h3>
                <p>
                  Ask a question or pick a suggested prompt. Conversation history is kept for this session.
                </p>
                <div className="ai-prompt-chips">
                  {SUGGESTED_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="ai-prompt-chip"
                      onClick={() => handlePromptClick(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => {
              const text = getMessageText(msg);
              const isAssistant = msg.role === 'assistant';
              const rendered = isAssistant ? renderAnswerText(text) : text;

              return (
                <div
                  key={msg.id}
                  className={`ai-message ai-message-${msg.role}`}
                >
                  <div className="ai-message-bubble">
                    {rendered || (isAssistant ? 'No response available.' : text)}
                  </div>
                  {isAssistant && (
                    <ActionLinks
                      actions={msg.suggested_actions}
                      links={msg.related_links}
                      navigate={navigate}
                    />
                  )}
                  <span className="ai-message-meta">{formatTime(msg.createdAt)}</span>
                </div>
              );
            })}

            {loading && (
              <div className="ai-loading-row" role="status">
                <Spinner inline />
                <span>Analyzing intelligence data…</span>
              </div>
            )}

            {error && (
              <div className="alert alert-error" role="alert">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {hasMessages && (
            <div className="ai-prompt-chips" style={{ padding: '0 1.25rem 0.75rem' }}>
              {SUGGESTED_PROMPTS.slice(0, 4).map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="ai-prompt-chip"
                  onClick={() => handlePromptClick(prompt)}
                  disabled={loading}
                >
                  {prompt}
                </button>
              ))}
              <button
                type="button"
                className="ai-prompt-chip"
                onClick={clearHistory}
                disabled={loading}
                style={{ background: '#fff', borderColor: 'var(--gov-border)' }}
              >
                Clear history
              </button>
            </div>
          )}

          <form className="ai-chat-composer" onSubmit={handleSubmit}>
            <textarea
              className="ai-chat-input"
              rows={1}
              placeholder="Ask the intelligence assistant…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              disabled={loading}
              aria-label="Officer query"
            />
            <button
              type="submit"
              className="btn btn-primary ai-send-btn"
              disabled={loading || !input.trim()}
            >
              {loading ? 'Sending…' : 'Send'}
            </button>
          </form>
        </section>
      </div>
    </Layout>
  );
}
