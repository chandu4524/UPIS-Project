import { hasPermission, PERM_VIEW_SENSITIVE_FIELDS } from '../config/rbac';
import { getStoredRole } from '../services/authService';

export { PERM_VIEW_SENSITIVE_FIELDS };

export function canViewSensitiveFields(role) {
  return hasPermission(role ?? getStoredRole(), PERM_VIEW_SENSITIVE_FIELDS);
}

export function isSensitiveFieldMasked(apiFlags) {
  if (apiFlags?.sensitive_fields_masked != null) {
    return Boolean(apiFlags.sensitive_fields_masked);
  }
  if (apiFlags?.can_view_sensitive_fields != null) {
    return !apiFlags.can_view_sensitive_fields;
  }
  return !canViewSensitiveFields();
}

export function accessFlagsFromResponse(data) {
  return {
    can_view_sensitive_fields: data?.can_view_sensitive_fields,
    sensitive_fields_masked: data?.sensitive_fields_masked,
  };
}
