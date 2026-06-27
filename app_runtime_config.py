"""Runtime configuration helpers and deployment constants for CogniSweep.

Keep this module free of Streamlit imports so app startup can read basic
configuration without pulling UI/runtime state into tests or deploy checks.
"""
from __future__ import annotations

import os


def cognisweep_env_alias(name: str) -> str:
    if name.startswith("ERRORSWEEP_"):
        return f"COGNISWEEP_{name[len('ERRORSWEEP_'):]}"
    return ""


def runtime_env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value not in (None, ""):
        return str(value)
    alias = cognisweep_env_alias(name)
    if alias:
        value = os.environ.get(alias)
        if value not in (None, ""):
            return str(value)
    return default


APP_VERSION = "v46 Security + QA Workflow Hardening"
DEPLOY_BUILD_ID = "auth-handoff-v15-server-logout-watchdog-2026-06-23"
DEPLOY_EXPECTED_BRANCH = runtime_env("ERRORSWEEP_EXPECTED_BRANCH", "main").strip() or "main"
DEPLOY_EXPECTED_FEATURES = (
    "separate_global_and_editor_shells",
    "editor_css_scoped_to_editor_shell",
    "direct_selected_page_navigation",
    "stable_html_app_topbar",
    "parent_runtime_no_reload_navigation",
    "secondary_internal_links_no_reload",
    "same_session_public_auth_routes",
    "full_width_global_app_shell",
    "pre_render_login_submit_callback",
    "server_side_editor_launch_token",
    "direct_file_url_media_source",
    "browser_timezone_local_time_display",
    "server_side_logout_revocation",
    "stable_cross_tab_login_logout_markers",
)
DEFAULT_MODEL = "gpt-4o-mini"

