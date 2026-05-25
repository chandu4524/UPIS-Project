import { canViewSensitiveFields } from '../utils/sensitiveFields';
import '../styles/sensitiveAccess.css';

/**
 * Shows whether sensitive PII is masked or shown in full.
 * Prefer API flags when provided; falls back to local RBAC.
 */
export default function SensitiveAccessBadge({
  canViewSensitiveFields: canViewProp,
  sensitiveFieldsMasked: maskedProp,
  className = '',
}) {
  const canView = canViewProp ?? canViewSensitiveFields();
  const masked = maskedProp ?? !canView;

  const label = masked ? 'Masked' : 'Full Access';
  const variant = masked ? 'masked' : 'full';

  return (
    <span
      className={`sensitive-access-badge sensitive-access-${variant} ${className}`.trim()}
      title={
        masked
          ? 'Mobile and ID fields are masked for your role'
          : 'You can view unmasked sensitive fields'
      }
    >
      {label}
    </span>
  );
}
