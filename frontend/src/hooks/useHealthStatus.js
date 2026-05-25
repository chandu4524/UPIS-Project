import { useEffect, useState } from 'react';
import {
  HEALTH_STATUS_LABELS,
  subscribeHealthPolling,
} from '../services/healthService';

/**
 * Non-blocking health polling for navbar / dashboard badges.
 */
export default function useHealthStatus(pollMs = 60000) {
  const [status, setStatus] = useState('checking');
  const [detail, setDetail] = useState('');
  const [payload, setPayload] = useState(null);

  useEffect(() => {
    return subscribeHealthPolling(({ status: badge, payload: data, error }) => {
      setStatus(badge);
      setPayload(data);
      if (error) {
        setDetail('Backend unreachable');
        return;
      }
      if (data) {
        const db = data.database_status || 'unknown';
        const env = data.environment || '';
        const ocr = data.ocr_ready === false ? ' · OCR limited' : '';
        setDetail(`DB: ${db}${env ? ` · ${env}` : ''}${ocr}`);
      } else {
        setDetail('');
      }
    }, pollMs);
  }, [pollMs]);

  return {
    status,
    detail,
    payload,
    label: HEALTH_STATUS_LABELS[status] || HEALTH_STATUS_LABELS.checking,
  };
}
