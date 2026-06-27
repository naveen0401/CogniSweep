"""Static platform constants and startup-tunable limits for CogniSweep."""
from __future__ import annotations

from app_runtime_config import runtime_env


DEFAULT_PUBLIC_LANDING_URL = "https://www.cognisweep.com/solutions/software-localization-tool"
PUBLIC_LANDING_ROUTE = "solutions/software-localization-tool"
PUBLIC_LANDING_PATH = f"/{PUBLIC_LANDING_ROUTE}"
PUBLIC_LANDING_CANONICAL_URL = (
    runtime_env("ERRORSWEEP_PUBLIC_LANDING_URL", DEFAULT_PUBLIC_LANDING_URL).strip().rstrip("/")
    or DEFAULT_PUBLIC_LANDING_URL
)

# Persistent browser sessions should survive reloads and browser restarts until
# the user explicitly clicks Logout. Browser cookies still need a finite
# Max-Age, so use a long renewal window while the signed token itself has no
# expiry check.
SESSION_PERSISTENCE_SECONDS = int(runtime_env("ERRORSWEEP_SESSION_PERSISTENCE_SECONDS", str(60 * 60 * 24 * 365 * 10)))
SESSION_TTL_SECONDS = SESSION_PERSISTENCE_SECONDS
DEFAULT_SESSION_SECRET = "errorsweep-dev-session-secret-change-me"
SESSION_HISTORY_LIMIT = 500
RULE_ZIP_MAX_FILES = int(runtime_env("ERRORSWEEP_RULE_ZIP_MAX_FILES", "250"))
RULE_ZIP_MAX_BYTES = int(runtime_env("ERRORSWEEP_RULE_ZIP_MAX_BYTES", str(25 * 1024 * 1024)))
RULE_ZIP_MAX_EXPANDED_BYTES = int(runtime_env("ERRORSWEEP_RULE_ZIP_MAX_EXPANDED_BYTES", str(RULE_ZIP_MAX_BYTES * 4)))
RULE_ZIP_MEMBER_MAX_BYTES = int(runtime_env("ERRORSWEEP_RULE_ZIP_MEMBER_MAX_BYTES", str(5 * 1024 * 1024)))
OFFICE_ZIP_MAX_FILES = int(runtime_env("ERRORSWEEP_OFFICE_ZIP_MAX_FILES", "1500"))
OFFICE_ZIP_MAX_EXPANDED_BYTES = int(runtime_env("ERRORSWEEP_OFFICE_ZIP_MAX_EXPANDED_BYTES", str(120 * 1024 * 1024)))
OFFICE_XML_MEMBER_MAX_BYTES = int(runtime_env("ERRORSWEEP_OFFICE_XML_MEMBER_MAX_BYTES", str(20 * 1024 * 1024)))
MEDIA_PREVIEW_TTL_SECONDS = int(runtime_env("ERRORSWEEP_MEDIA_PREVIEW_TTL_SECONDS", str(60 * 60 * 24 * 2)))
MEDIA_URL_MAX_BYTES = int(runtime_env("ERRORSWEEP_MEDIA_URL_MAX_BYTES", str(200 * 1024 * 1024)))
RETENTION_POLICY_DEFAULTS = {
    "expired_auth_token_grace_days": 0,
    "expired_file_manifest_grace_days": 7,
    "sent_notification_days": 180,
    "completed_task_days": 90,
    "closed_privacy_request_days": 730,
    "closed_support_ticket_days": 730,
    "local_media_preview_hours": max(1, MEDIA_PREVIEW_TTL_SECONDS // 3600),
}
LEGAL_VERSION_DEFAULTS = {
    "terms_version": "2026-05-29",
    "privacy_version": "2026-05-29",
    "nda_version": "2026-05-29",
    "cookie_version": "2026-05-29",
    "dpa_version": "2026-05-29",
}
ABUSE_PROTECTION_DEFAULTS = {
    "window_minutes": 15,
    "owner_login_attempts": 5,
    "workspace_login_attempts": 8,
    "demo_access_attempts": 12,
    "signup_attempts": 5,
    "password_reset_attempts": 5,
    "checkout_intent_attempts": 5,
    "support_ticket_attempts": 8,
    "privacy_request_attempts": 8,
}
ABUSE_ACTION_META = {
    "owner_login": ("Owner login", "owner_login_attempts"),
    "workspace_login": ("Workspace login", "workspace_login_attempts"),
    "demo_access": ("Demo access", "demo_access_attempts"),
    "signup": ("Public signup", "signup_attempts"),
    "password_reset": ("Password reset", "password_reset_attempts"),
    "checkout_intent": ("Checkout intent", "checkout_intent_attempts"),
    "support_ticket": ("Support ticket", "support_ticket_attempts"),
    "privacy_request": ("Privacy request", "privacy_request_attempts"),
}
SUBPROCESSOR_APPROVAL_STATUSES = ["Needs review", "Approved", "Blocked", "Customer controlled"]
SUBPROCESSOR_DPA_STATUSES = ["Needs DPA", "DPA approved", "Not applicable", "Customer controlled"]
SUBPROCESSOR_NOTICE_STATUSES = ["Needs customer notice", "Covered in policy", "Customer-specific approval", "Not applicable"]
SUBPROCESSOR_DEFAULT_REGISTER = {
    "supabase_persistence": {
        "approval_status": "Needs review",
        "dpa_status": "Needs DPA",
        "customer_notice": "Covered in policy",
        "notes": "",
    },
    "object_storage": {
        "approval_status": "Needs review",
        "dpa_status": "Needs DPA",
        "customer_notice": "Covered in policy",
        "notes": "",
    },
    "async_worker": {
        "approval_status": "Needs review",
        "dpa_status": "Needs DPA",
        "customer_notice": "Covered in policy",
        "notes": "",
    },
    "transactional_email": {
        "approval_status": "Needs review",
        "dpa_status": "Needs DPA",
        "customer_notice": "Covered in policy",
        "notes": "",
    },
    "billing_gateway": {
        "approval_status": "Needs review",
        "dpa_status": "Needs DPA",
        "customer_notice": "Covered in policy",
        "notes": "",
    },
    "byo_ai": {
        "approval_status": "Customer controlled",
        "dpa_status": "Customer controlled",
        "customer_notice": "Customer-specific approval",
        "notes": "Customer-provided API keys and base URLs are controlled by the customer/workspace.",
    },
    "languagetool": {
        "approval_status": "Needs review",
        "dpa_status": "Needs DPA",
        "customer_notice": "Customer-specific approval",
        "notes": "Public LanguageTool routing should remain disabled unless approved by customer policy.",
    },
}
SSO_PROVIDER_OPTIONS = ["Microsoft Entra ID", "Okta", "Google Workspace", "Custom OIDC", "SAML 2.0"]
SSO_PROTOCOL_OPTIONS = ["OIDC", "SAML"]
SSO_STATUS_OPTIONS = ["Draft", "Metadata review", "Enabled", "Disabled"]
SESSION_COLLECTION_LIMITS = {
    "ai_usage_events": 500,
    "audit_logs": 500,
    "jobs": 500,
    "owner_recent_editor_jobs": 100,
    "payments": 500,
    "invoices": 500,
    "projects": 500,
    "files": 1000,
    "translation_memory": 5000,
    "tm": 5000,
    "glossary": 5000,
    "dnt": 5000,
    "rule_instructions": 1000,
    "users": 1000,
    "workspaces": 1000,
    "notifications": 1000,
    "task_queue": 1000,
    "subscriptions": 500,
    "checkout_sessions": 500,
    "billing_events": 500,
    "auth_tokens": 500,
    "platform_settings": 100,
    "privacy_requests": 500,
    "support_tickets": 1000,
    "status_incidents": 500,
    "consent_records": 1000,
    "integration_connections": 500,
    "resource_bindings": 1000,
    "resource_lookup_cache": 1000,
    "integration_audit": 1000,
}
SAAS_CACHE_TTL_SECONDS = int(runtime_env("ERRORSWEEP_SAAS_CACHE_TTL_SECONDS", "15"))
SAAS_CACHE_GENERATION_KEY = "_saas_read_cache_generation"
SAAS_CACHEABLE_COLLECTIONS = {
    "workspaces",
    "projects",
    "jobs",
    "payments",
    "invoices",
    "audit_logs",
    "notifications",
    "files",
    "subscriptions",
    "checkout_sessions",
    "billing_events",
    "platform_settings",
    "privacy_requests",
    "support_tickets",
    "status_incidents",
    "consent_records",
    "integration_connections",
    "resource_bindings",
    "translation_memory",
    "integration_audit",
}
SESSION_COOKIE_NAME = "errorsweep_session"
SESSION_STORAGE_KEY = "errorsweep_session"
SESSION_COOKIE_CONTROLLER_KEY = "errorsweep_browser_cookies"
SESSION_HANDOFF_QUERY_PARAM = "es_session"
EDITOR_LAUNCH_QUERY_PARAM = "es_launch"
EDITOR_LAUNCH_TTL_SECONDS = int(runtime_env("ERRORSWEEP_EDITOR_LAUNCH_TTL_SECONDS", str(60 * 30)))
EDITOR_AUTH_FAILED_QUERY_PARAM = "es_editor_auth_failed"
EDITOR_SUBMITTED_QUERY_PARAM = "es_editor_submitted"
EDITOR_SUBMITTED_TYPE_QUERY_PARAM = "es_editor_submitted_type"
AUTH_CHECK_QUERY_PARAM = "es_auth_checked"
AUTH_STATE_UNKNOWN = "unknown"
AUTH_STATE_AUTHENTICATED = "authenticated"
AUTH_STATE_UNAUTHENTICATED = "unauthenticated"
ROUTE_STORAGE_KEY = "errorsweep_route"
LOGOUT_BROADCAST_KEY = "errorsweep_logout_broadcast"
LOGIN_BROADCAST_KEY = "errorsweep_login_broadcast"
LOGOUT_DONE_QUERY_PARAM = "es_signed_out"
LOGOUT_BROWSER_CLEANUP_KEY = "_logout_browser_cleanup_pending"
LOGOUT_SKIP_RESTORE_KEY = "_logout_skip_restore_once"
BROWSER_TIMEZONE_QUERY_PARAM = "es_tz"
BROWSER_TIMEZONE_STORAGE_KEY = "cognisweep_browser_timezone"
ROUTE_STORAGE_PARAM_KEYS = ("es_page", "es_editor", "job_id", "review_id")
ROUTE_RESTORE_BLOCKING_QUERY_KEYS = (
    *ROUTE_STORAGE_PARAM_KEYS,
    "route",
    "public",
    "return_to",
    EDITOR_LAUNCH_QUERY_PARAM,
    EDITOR_AUTH_FAILED_QUERY_PARAM,
    EDITOR_SUBMITTED_QUERY_PARAM,
)
SESSION_TOKEN_USER_FIELDS = ("email", "role", "account_type", "workspace", "plan", "status", "email_verified", "timezone")
SESSION_STARTED_AT_MS_FIELD = "session_started_at_ms"
SESSION_LOGOUT_REGISTRY_LIMIT = 2000
SESSION_COOKIE_MAX_BYTES = 3800
LANGUAGE_CATALOG = [
    "English",
    "French",
    "Spanish",
    "German",
    "Italian",
    "Portuguese",
    "Hindi",
    "Bengali",
    "Tamil",
    "Telugu",
    "Kannada",
    "Malayalam",
    "Marathi",
    "Gujarati",
    "Punjabi",
    "Urdu",
    "Arabic",
    "Persian",
    "Hebrew",
    "Russian",
    "Ukrainian",
    "Polish",
    "Turkish",
    "Greek",
    "Dutch",
    "Norwegian",
    "Swedish",
    "Danish",
    "Finnish",
    "Afrikaans",
    "Swahili",
    "Hausa",
    "Sinhala",
    "Zulu",
    "Amharic",
    "Yoruba",
    "Chinese",
    "Japanese",
    "Korean",
    "Thai",
    "Indonesian",
    "Malay",
    "Tagalog",
    "Burmese",
    "Khmer",
    "Lao",
    "Mongolian",
    "Vietnamese",
]
TALENT_PROFILE_TYPES = [
    "Freelancer",
    "Professional",
    "Agency",
    "Company employee",
    "Client / Hiring manager",
]
TALENT_PRIMARY_ROLES = [
    "Translator",
    "Reviewer",
    "LQA Specialist",
    "Subtitler",
    "Transcriptionist",
    "Project Manager",
    "Localization Engineer",
    "Client / Hiring Manager",
    "Other",
]
TALENT_SERVICES = [
    "Translation",
    "Editing",
    "Proofreading",
    "LQA",
    "Terminology",
    "Subtitling",
    "Transcription",
    "MTPE",
    "Project Management",
    "Localization Engineering",
]
TALENT_DOMAINS = [
    "Software / UI",
    "Marketing",
    "Legal",
    "Medical",
    "Finance",
    "Gaming",
    "E-learning",
    "Media / Entertainment",
    "Technical",
    "General Business",
]
TALENT_AVAILABILITY = ["Available now", "Available this week", "Part-time", "Booked", "Not currently available"]
TALENT_WORK_PREFERENCES = ["Remote", "Hybrid", "On-site", "Contract", "Full-time", "Part-time"]
UI_LANGUAGE_OPTIONS = [
    ("EN", "English"),
    ("HI", "Hindi"),
    ("TE", "Telugu"),
    ("TA", "Tamil"),
    ("KN", "Kannada"),
    ("ML", "Malayalam"),
    ("FR", "French"),
    ("ES", "Spanish"),
    ("DE", "German"),
    ("JA", "Japanese"),
]
