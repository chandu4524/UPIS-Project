"""Role-based access control for GPIP."""

from typing import Dict, FrozenSet, Optional, Set

# Canonical role keys
ROLE_ADMIN = "admin"
ROLE_STATE_OFFICER = "state_officer"
ROLE_DISTRICT_OFFICER = "district_officer"
ROLE_POLICE_OFFICER = "police_officer"
ROLE_WELFARE_OFFICER = "welfare_officer"
ROLE_AUDITOR = "auditor"

ROLE_LABELS: Dict[str, str] = {
    ROLE_ADMIN: "Admin",
    ROLE_STATE_OFFICER: "State Officer",
    ROLE_DISTRICT_OFFICER: "District Officer",
    ROLE_POLICE_OFFICER: "Police Officer",
    ROLE_WELFARE_OFFICER: "Welfare Officer",
    ROLE_AUDITOR: "Auditor",
}

ALL_ROLES = frozenset(ROLE_LABELS.keys())

# Permissions
PERM_DASHBOARD_READ = "dashboard:read"
PERM_DASHBOARD_ANALYTICS = "dashboard:analytics"
PERM_UPLOAD_WRITE = "upload:write"
PERM_UPLOAD_READ = "upload:read"
PERM_TEMPLATE_WRITE = "template:write"
PERM_CITIZENS_READ = "citizens:read"
PERM_SEARCH_READ = "search:read"
PERM_REVIEW_WRITE = "review:write"
PERM_OCR_WRITE = "ocr:write"
PERM_AUDIT_READ = "audit:read"
PERM_REPORTS_READ = "reports:read"
PERM_ASSISTANT_USE = "assistant:use"
PERM_USERS_ADMIN = "users:admin"
PERM_VIEW_SENSITIVE_FIELDS = "view:sensitive_fields"

_ROLE_ALIASES = {
    "admin": ROLE_ADMIN,
    "administrator": ROLE_ADMIN,
    "state officer": ROLE_STATE_OFFICER,
    "state_officer": ROLE_STATE_OFFICER,
    "stateofficer": ROLE_STATE_OFFICER,
    "district officer": ROLE_DISTRICT_OFFICER,
    "district_officer": ROLE_DISTRICT_OFFICER,
    "districtofficer": ROLE_DISTRICT_OFFICER,
    "police officer": ROLE_POLICE_OFFICER,
    "police_officer": ROLE_POLICE_OFFICER,
    "policeofficer": ROLE_POLICE_OFFICER,
    "welfare officer": ROLE_WELFARE_OFFICER,
    "welfare_officer": ROLE_WELFARE_OFFICER,
    "welfareofficer": ROLE_WELFARE_OFFICER,
    "auditor": ROLE_AUDITOR,
    # Legacy default login role
    "officer": ROLE_ADMIN,
}

_STATE_PERMS: Set[str] = {
    PERM_DASHBOARD_READ,
    PERM_DASHBOARD_ANALYTICS,
    PERM_UPLOAD_WRITE,
    PERM_UPLOAD_READ,
    PERM_TEMPLATE_WRITE,
    PERM_CITIZENS_READ,
    PERM_SEARCH_READ,
    PERM_REVIEW_WRITE,
    PERM_OCR_WRITE,
    PERM_AUDIT_READ,
    PERM_REPORTS_READ,
    PERM_ASSISTANT_USE,
    PERM_VIEW_SENSITIVE_FIELDS,
}

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    ROLE_ADMIN: frozenset(
        {
            PERM_DASHBOARD_READ,
            PERM_DASHBOARD_ANALYTICS,
            PERM_UPLOAD_WRITE,
            PERM_UPLOAD_READ,
            PERM_TEMPLATE_WRITE,
            PERM_CITIZENS_READ,
            PERM_SEARCH_READ,
            PERM_REVIEW_WRITE,
            PERM_OCR_WRITE,
            PERM_AUDIT_READ,
            PERM_REPORTS_READ,
            PERM_ASSISTANT_USE,
            PERM_USERS_ADMIN,
            PERM_VIEW_SENSITIVE_FIELDS,
        }
    ),
    ROLE_STATE_OFFICER: frozenset(_STATE_PERMS | {PERM_VIEW_SENSITIVE_FIELDS}),
    ROLE_DISTRICT_OFFICER: frozenset(
        {
            PERM_DASHBOARD_READ,
            PERM_DASHBOARD_ANALYTICS,
            PERM_UPLOAD_WRITE,
            PERM_UPLOAD_READ,
            PERM_TEMPLATE_WRITE,
            PERM_CITIZENS_READ,
            PERM_SEARCH_READ,
            PERM_REVIEW_WRITE,
            PERM_ASSISTANT_USE,
        }
    ),
    ROLE_POLICE_OFFICER: frozenset(
        {
            PERM_DASHBOARD_READ,
            PERM_CITIZENS_READ,
            PERM_SEARCH_READ,
            PERM_ASSISTANT_USE,
            PERM_VIEW_SENSITIVE_FIELDS,
        }
    ),
    ROLE_WELFARE_OFFICER: frozenset(
        {
            PERM_DASHBOARD_READ,
            PERM_UPLOAD_WRITE,
            PERM_UPLOAD_READ,
            PERM_TEMPLATE_WRITE,
            PERM_CITIZENS_READ,
            PERM_SEARCH_READ,
            PERM_REVIEW_WRITE,
            PERM_ASSISTANT_USE,
        }
    ),
    ROLE_AUDITOR: frozenset(
        {
            PERM_DASHBOARD_READ,
            PERM_DASHBOARD_ANALYTICS,
            PERM_AUDIT_READ,
            PERM_REPORTS_READ,
            PERM_CITIZENS_READ,
        }
    ),
}


def normalize_role(raw: Optional[str]) -> str:
    if not raw:
        return ROLE_DISTRICT_OFFICER
    key = str(raw).strip().lower().replace("-", "_")
    if key in ALL_ROLES:
        return key
    return _ROLE_ALIASES.get(key, _ROLE_ALIASES.get(str(raw).strip().lower(), ROLE_DISTRICT_OFFICER))


def role_label(role: str) -> str:
    return ROLE_LABELS.get(normalize_role(role), str(role).replace("_", " ").title())


def has_permission(role: str, permission: str) -> bool:
    canonical = normalize_role(role)
    if canonical == ROLE_ADMIN:
        return True
    perms = ROLE_PERMISSIONS.get(canonical, frozenset())
    return permission in perms


def has_any_permission(role: str, permissions: Set[str]) -> bool:
    return any(has_permission(role, p) for p in permissions)
