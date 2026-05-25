import { useCallback, useEffect, useState } from 'react';
import { subscribeNotify } from '../utils/notify';
import '../styles/toast.css';

export default function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    return subscribeNotify((toast) => {
      setToasts((prev) => [...prev.slice(-4), toast]);
      const ms = toast.durationMs ?? 5000;
      setTimeout(() => dismiss(toast.id), ms);
    });
  }, [dismiss]);

  return (
    <>
      {children}
      <div className="toast-stack" aria-live="polite" aria-relevant="additions">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.type || 'error'}`}
            role="status"
          >
            <span className="toast-message">{toast.message}</span>
            <button
              type="button"
              className="toast-dismiss"
              aria-label="Dismiss"
              onClick={() => dismiss(toast.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
