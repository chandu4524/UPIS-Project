/**
 * Frontend RBAC — mirrors backend permission keys.
 */

export const ROLES = {
  admin: 'Admin',
  state_officer: 'State Officer',
  district_officer: 'District Officer',
  police_officer: 'Police Officer',
  welfare_officer: 'Welfare Officer',
  auditor: 'Auditor',
};

const PERM = {
  DASHBOARD: 'dashboard:read',
  ANALYTICS: 'dashboard:analytics',
  UPLOAD_WRITE: 'upload:write',
  UPLOAD_READ: 'upload:read',
  TEMPLATE: 'template:write',
  CITIZENS: 'citizens:read',
  SEARCH: 'search:read',
  REVIEW: 'review:write',
  OCR: 'ocr:write',
  AUDIT: 'audit:read',
  REPORTS: 'reports:read',
  ASSISTANT: 'assistant:use',
  VIEW_SENSITIVE: 'view:sensitive_fields',
  USERS_ADMIN: 'users:admin',
};

export const PERM_VIEW_SENSITIVE_FIELDS = PERM.VIEW_SENSITIVE;

const ROLE_PERMISSIONS = {
  admin: [...Object.values(PERM)],
  state_officer: [
    PERM.DASHBOARD,
    PERM.ANALYTICS,
    PERM.UPLOAD_WRITE,
    PERM.UPLOAD_READ,
    PERM.TEMPLATE,
    PERM.CITIZENS,
    PERM.SEARCH,
    PERM.REVIEW,
    PERM.OCR,
    PERM.AUDIT,
    PERM.REPORTS,
    PERM.ASSISTANT,
    PERM.VIEW_SENSITIVE,
  ],
  district_officer: [
    PERM.DASHBOARD,
    PERM.ANALYTICS,
    PERM.UPLOAD_WRITE,
    PERM.UPLOAD_READ,
    PERM.TEMPLATE,
    PERM.CITIZENS,
    PERM.SEARCH,
    PERM.REVIEW,
    PERM.ASSISTANT,
  ],
  police_officer: [
    PERM.DASHBOARD,
    PERM.CITIZENS,
    PERM.SEARCH,
    PERM.ASSISTANT,
    PERM.VIEW_SENSITIVE,
  ],
  welfare_officer: [
    PERM.DASHBOARD,
    PERM.UPLOAD_WRITE,
    PERM.UPLOAD_READ,
    PERM.TEMPLATE,
    PERM.CITIZENS,
    PERM.SEARCH,
    PERM.REVIEW,
    PERM.ASSISTANT,
  ],
  auditor: [
    PERM.DASHBOARD,
    PERM.ANALYTICS,
    PERM.AUDIT,
    PERM.REPORTS,
    PERM.CITIZENS,
  ],
};

const ROLE_ALIASES = {
  admin: 'admin',
  administrator: 'admin',
  'state officer': 'state_officer',
  state_officer: 'state_officer',
  'district officer': 'district_officer',
  district_officer: 'district_officer',
  'police officer': 'police_officer',
  police_officer: 'police_officer',
  'welfare officer': 'welfare_officer',
  welfare_officer: 'welfare_officer',
  auditor: 'auditor',
  officer: 'admin',
};

export function normalizeRole(raw) {
  if (!raw) return 'district_officer';
  const key = String(raw).trim().toLowerCase().replace(/-/g, '_');
  if (ROLE_PERMISSIONS[key]) return key;
  return ROLE_ALIASES[key] || ROLE_ALIASES[String(raw).trim().toLowerCase()] || 'district_officer';
}

export function getRoleLabel(role) {
  const key = normalizeRole(role);
  return ROLES[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function hasPermission(role, permission) {
  const key = normalizeRole(role);
  if (key === 'admin') return true;
  const perms = ROLE_PERMISSIONS[key] || [];
  return perms.includes(permission);
}

export const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: '▣', permission: PERM.DASHBOARD },
  { to: '/upload', label: 'File Upload', icon: '↑', permission: PERM.UPLOAD_WRITE },
  { to: '/ocr-processing', label: 'OCR Processing', icon: '◎', permission: PERM.OCR },
  { to: '/template-mapping', label: 'Template Mapping', icon: '⇄', permission: PERM.TEMPLATE },
  { to: '/upload-history', label: 'Upload History', icon: '◷', permission: PERM.UPLOAD_READ },
  { to: '/citizens', label: 'Citizen Records', icon: '☰', permission: PERM.CITIZENS },
  { to: '/intelligence-search', label: 'Intelligence Search', icon: '⌕', permission: PERM.SEARCH },
  { to: '/ai-assistant', label: 'AI Assistant', icon: '◈', permission: PERM.ASSISTANT },
  { to: '/manual-review', label: 'Manual Review Queue', icon: '⚖', permission: PERM.REVIEW },
  { to: '/audit-logs', label: 'Audit Logs', icon: '⊞', permission: PERM.AUDIT },
  { to: '/reports', label: 'Reports', icon: '📊', permission: PERM.REPORTS },
  { to: '/admin-users', label: 'Admin Users', icon: '👤', permission: PERM.USERS_ADMIN },
];

const ROUTE_PERMISSIONS = [
  { pattern: /^\/dashboard$/, permission: PERM.DASHBOARD },
  { pattern: /^\/upload$/, permission: PERM.UPLOAD_WRITE },
  { pattern: /^\/upload-history$/, permission: PERM.UPLOAD_READ },
  { pattern: /^\/template-mapping$/, permission: PERM.TEMPLATE },
  { pattern: /^\/ocr-processing$/, permission: PERM.OCR },
  { pattern: /^\/citizens$/, permission: PERM.CITIZENS },
  { pattern: /^\/intelligence-search$/, permission: PERM.SEARCH },
  { pattern: /^\/ai-assistant$/, permission: PERM.ASSISTANT },
  { pattern: /^\/manual-review$/, permission: PERM.REVIEW },
  { pattern: /^\/audit-logs$/, permission: PERM.AUDIT },
  { pattern: /^\/reports/, permission: PERM.REPORTS },
  { pattern: /^\/admin-users$/, permission: PERM.USERS_ADMIN },
  { pattern: /^\/person-profile\//, permission: PERM.CITIZENS },
  { pattern: /^\/relationships\//, permission: PERM.CITIZENS },
];

export function getNavItemsForRole(role) {
  return NAV_ITEMS.filter((item) => hasPermission(role, item.permission));
}

export function getDefaultRouteForRole(role) {
  const items = getNavItemsForRole(role);
  return items[0]?.to || '/dashboard';
}

export function canAccessRoute(role, pathname) {
  const key = normalizeRole(role);
  if (key === 'admin') return true;
  const rule = ROUTE_PERMISSIONS.find((r) => r.pattern.test(pathname));
  if (!rule) return true;
  return hasPermission(role, rule.permission);
}
