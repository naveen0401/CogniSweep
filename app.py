
import base64
import csv
import hashlib
import hmac
import io
import json
import math
import os
import re
import difflib
import time
import zipfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from openai import OpenAI

try:
    from managed_ai_router import ai_json_items, select_ai_route
except Exception:
    ai_json_items = None
    select_ai_route = None

# ErrorSweep v30 backend-only translation router:
# Phase 1 current default = Azure Translator
# Phase 2 future switch = NLLB self-hosted when NLLB_MODE=True
try:
    from translator_router import translate_batch as builtin_translate_batch, current_builtin_engine_label
except Exception:
    builtin_translate_batch = None
    current_builtin_engine_label = None

# Speech-to-text helper for subtitle/transcription editor.
# v32 policy: auto transcription only uses the user's own API key; no-key users get blank manual rows.
try:
    from speech_transcription import transcribe_media_to_rows, speech_engine_label
except Exception:
    transcribe_media_to_rows = None
    speech_engine_label = None



from openpyxl import load_workbook, Workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from docx import Document

# External editor job storage for v41.
# Stores Pro translated rows so a separate browser tab can open the CAT editor by job_id.
try:
    from editor_job_store import save_editor_job, load_editor_job, update_editor_job
except Exception:
    save_editor_job = None
    load_editor_job = None
    update_editor_job = None


# v42 production persistence. Supabase is used when configured; local JSON fallback keeps the MVP working.
try:
    from production_persistence import (
        save_persistent_editor_job,
        load_persistent_editor_job,
        update_persistent_editor_job,
        log_persistent_usage_event,
        fetch_persistent_usage_events,
        fetch_persistent_editor_jobs,
        persistence_health,
    )
except Exception:
    save_persistent_editor_job = None
    load_persistent_editor_job = None
    update_persistent_editor_job = None
    log_persistent_usage_event = None
    fetch_persistent_usage_events = None
    fetch_persistent_editor_jobs = None
    persistence_health = None



# ==========================================================
# ErrorSweep Platform v42
# Production persistence + usage tracking + external CAT editor launcher
# Phase 1: Azure Translator | Phase 2: NLLB self-hosted
# Editor jobs and usage persist to Supabase when configured, with local JSON fallback
# ==========================================================

APP_VERSION = "v43 Owner Console Job Details"
DEFAULT_MODEL = "gpt-4o-mini"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7

st.set_page_config(
    page_title="ErrorSweep",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==========================================================
# Visual system
# ==========================================================

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Space+Mono:wght@400;700&display=swap');

:root {
  --es-bg: #070914;
  --es-panel: rgba(18, 21, 38, .86);
  --es-card: rgba(18, 21, 38, .78);
  --es-border: rgba(84, 105, 180, .35);
  --es-border-soft: rgba(84, 105, 180, .20);
  --es-text: #f7fbff;
  --es-muted: #a8b0d6;
  --es-green: #00d985;
  --es-cyan: #34bdf6;
  --es-purple: #8b5cf6;
  --es-red: #ff4b33;
  --es-amber: #f59e0b;
}

html, body, [class*="css"] {
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp {
  background:
    radial-gradient(circle at 8% 12%, rgba(0, 217, 133, .18), transparent 26%),
    radial-gradient(circle at 88% 8%, rgba(52, 189, 246, .12), transparent 28%),
    radial-gradient(circle at 55% 96%, rgba(139, 92, 246, .10), transparent 34%),
    linear-gradient(180deg, #070914 0%, #060711 100%);
  color: var(--es-text);
}

#MainMenu, footer, header,
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stDeployButton"], .stAppDeployButton {
  visibility: hidden !important;
  display: none !important;
}

.block-container {
  padding-top: 1.3rem !important;
  max-width: 1600px !important;
}

.es-shell {
  min-height: calc(100vh - 80px);
}

.es-rail {
  background: rgba(13, 16, 31, .88);
  border: 1px solid var(--es-border-soft);
  border-radius: 24px;
  padding: 16px 14px;
  position: sticky;
  top: 18px;
  box-shadow: 0 30px 80px rgba(0,0,0,.22);
}

.es-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 900;
  font-size: 22px;
  margin-bottom: 8px;
  letter-spacing: -0.02em;
}

.es-logo-badge {
  width: 36px;
  height: 36px;
  border-radius: 13px;
  display: grid;
  place-items: center;
  background:
    linear-gradient(135deg, rgba(0,217,133,.98), rgba(52,189,246,.92));
  color: #05131c;
  font-weight: 950;
  font-size: 14px;
  letter-spacing: -.08em;
  position: relative;
  box-shadow: 0 10px 30px rgba(52, 189, 246, .22);
}

.es-small {
  color: var(--es-muted);
  font-size: 12px;
  line-height: 1.4;
}

.es-nav-label {
  font-family: "Space Mono", monospace;
  font-size: 10px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: #8ea1dc;
  margin: 18px 0 8px;
}

.es-hero {
  background:
    linear-gradient(135deg, rgba(0, 217, 133, .16), rgba(52, 189, 246, .08) 45%, rgba(139, 92, 246, .22)),
    rgba(17, 20, 38, .88);
  border: 1px solid rgba(52, 189, 246, .26);
  border-radius: 28px;
  padding: 34px 34px;
  margin-bottom: 20px;
  box-shadow: 0 30px 90px rgba(0,0,0,.30);
}

.es-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid rgba(0,217,133,.28);
  background: rgba(0,217,133,.10);
  color: #33f2aa;
  font-family: "Space Mono", monospace;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.es-title {
  font-size: clamp(32px, 4vw, 56px);
  line-height: 1.02;
  font-weight: 900;
  letter-spacing: -.04em;
  margin: 16px 0 10px;
  color: #f8fbff;
}

.es-title span {
  background: linear-gradient(90deg, #dfffee, #7dd3fc, #c4b5fd);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.es-subtitle {
  color: #c2c9e9;
  font-size: 16px;
  max-width: 980px;
}

.es-card {
  background: var(--es-card);
  border: 1px solid var(--es-border-soft);
  border-radius: 20px;
  padding: 20px;
  box-shadow: 0 18px 54px rgba(0,0,0,.18);
}

.es-card h3, .es-card h4 {
  margin-top: 0;
}

.es-grid-4 {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 16px 0 22px;
}

.es-grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 16px 0 22px;
}

.es-metric-label {
  font-family: "Space Mono", monospace;
  color: #9aa7da;
  font-size: 11px;
  letter-spacing: .10em;
  text-transform: uppercase;
}

.es-metric-value {
  font-size: 30px;
  font-weight: 900;
  color: #fff;
  margin: 7px 0 4px;
}

.es-chip {
  display:inline-block;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid rgba(52,189,246,.22);
  background: rgba(52,189,246,.08);
  color: #bfeaff;
  font-size: 12px;
  font-weight: 700;
}

.es-chip.green {
  border-color: rgba(0,217,133,.24);
  background: rgba(0,217,133,.10);
  color: #77ffc9;
}

.es-chip.amber {
  border-color: rgba(245,158,11,.30);
  background: rgba(245,158,11,.12);
  color: #ffd18a;
}

.es-chip.red {
  border-color: rgba(255,75,51,.30);
  background: rgba(255,75,51,.12);
  color: #ffb0a5;
}

.es-row-card {
  border: 1px solid var(--es-border-soft);
  border-radius: 16px;
  padding: 12px;
  background: rgba(255,255,255,.03);
  margin: 8px 0;
}

.es-timeline {
  position: relative;
  height: 68px;
  border: 1px solid rgba(84,105,180,.28);
  border-radius: 18px;
  background: linear-gradient(90deg, rgba(0,217,133,.08), rgba(52,189,246,.06), rgba(139,92,246,.08));
  overflow: hidden;
  margin-top: 12px;
}

.es-timebar {
  position: absolute;
  top: 18px;
  height: 26px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--es-green), var(--es-cyan));
  border: 1px solid rgba(255,255,255,.22);
  box-shadow: 0 12px 24px rgba(0,217,133,.16);
}

.es-timebar.current {
  background: linear-gradient(90deg, #f59e0b, #ff4b33);
}

.stButton > button, .stDownloadButton > button {
  width: 100%;
  border-radius: 14px !important;
  border: 1px solid rgba(0,217,133,.24) !important;
  background: linear-gradient(90deg, #00bf75, #2094f3) !important;
  color: white !important;
  font-weight: 800 !important;
  box-shadow: 0 12px 30px rgba(0,0,0,.18);
}

.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 18px 38px rgba(52,189,246,.24);
}


.es-nav-link {
  display: block;
  text-decoration: none !important;
  text-align: center;
  color: #dce8ff !important;
  border: 1px solid rgba(84,105,180,.26);
  background: rgba(18,21,38,.74);
  border-radius: 14px;
  padding: 0.72rem 0.85rem;
  margin: 0.45rem 0;
  font-weight: 800;
  box-shadow: 0 8px 22px rgba(0,0,0,.14);
}
.es-nav-link:hover {
  background: rgba(52,189,246,.15);
  border-color: rgba(52,189,246,.45);
  color: #ffffff !important;
}
.es-nav-link.active {
  background: linear-gradient(90deg, #00bf75, #2094f3);
  color: #ffffff !important;
  border-color: rgba(0,217,133,.45);
  box-shadow: 0 14px 30px rgba(32,148,243,.22);
}
.es-video-compact-note {
  color: #a8b0d6;
  font-size: 12px;
  margin: 6px 0 14px;
}
[data-testid="stVideo"] video {
  max-height: 220px !important;
  object-fit: contain !important;
  background: #000 !important;
  border-radius: 16px !important;
}
[data-testid="stVideo"] {
  max-width: 520px !important;
  margin-left: auto !important;
  margin-right: auto !important;
}

textarea, input, select {
  border-radius: 12px !important;
}

[data-testid="stFileUploader"] {
  background: rgba(18,21,38,.72);
  border: 1px solid rgba(84,105,180,.24);
  border-radius: 18px;
  padding: 10px 14px;
}

[data-testid="stExpander"] {
  background: rgba(18,21,38,.70) !important;
  border: 1px solid rgba(84,105,180,.24) !important;
  border-radius: 18px !important;
}

@media (max-width: 1100px) {
  .es-grid-4, .es-grid-3 { grid-template-columns: 1fr; }
}
</style>
""",
    unsafe_allow_html=True,
)


# ==========================================================
# Session and config helpers
# ==========================================================

def secret(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass
    return default


def session_secret() -> str:
    return secret("ERRORSWEEP_SESSION_SECRET", "errorsweep-dev-session-secret-change-me")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def sign_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = b64url(raw)
    sig = hmac.new(session_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_payload(token: str) -> Optional[Dict[str, Any]]:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(session_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        data = json.loads(b64url_decode(body))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


def query_get(name: str) -> str:
    try:
        val = st.query_params.get(name, "")
        if isinstance(val, list):
            return val[0] if val else ""
        return val or ""
    except Exception:
        return ""


def query_set(name: str, value: str) -> None:
    try:
        st.query_params[name] = value
    except Exception:
        pass


def query_clear(name: str) -> None:
    try:
        if name in st.query_params:
            del st.query_params[name]
    except Exception:
        pass


def login_user(email: str, role: str, account_type: str, workspace: str = "Demo Workspace") -> None:
    user = {
        "email": email,
        "role": role,
        "account_type": account_type,
        "workspace": workspace,
        "login_at": datetime.now(timezone.utc).isoformat(),
    }
    st.session_state["user"] = user
    payload = {**user, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    query_set("es_session", sign_payload(payload))


def restore_session_from_query() -> None:
    if st.session_state.get("user"):
        return
    token = query_get("es_session")
    if not token:
        return
    data = verify_payload(token)
    if data:
        st.session_state["user"] = {
            "email": data.get("email", ""),
            "role": data.get("role", "User"),
            "account_type": data.get("account_type", "user"),
            "workspace": data.get("workspace", "Demo Workspace"),
            "login_at": data.get("login_at", ""),
        }


def logout() -> None:
    st.session_state.pop("user", None)
    query_clear("es_session")
    st.rerun()


restore_session_from_query()


# ==========================================================
# Data initialization
# ==========================================================

def init_state() -> None:
    defaults = {
        "page": "Dashboard",
        "projects": [],
        "jobs": [],
        "tm": [],
        "glossary": [
            {"source": "Docflow", "target": "Docflow", "notes": "Product name / DNT"},
            {"source": "FitJourney", "target": "FitJourney", "notes": "Product name / DNT"},
        ],
        "dnt": ["Docflow", "FitJourney", "{{email}}", "{{password}}", "{{user_name}}"],
        "review_segments": [],
        "subtitle_segments": [],
        "payments": [
            {"date": "2026-05-01", "workspace": "Demo Workspace", "user": "demo@errorsweep.local", "plan": "Trial", "amount": 0, "currency": "USD", "status": "Demo"}
        ],
        "workspaces": [
            {"workspace": "Demo Workspace", "owner": "demo@errorsweep.local", "plan": "Trial", "status": "Active", "users": 3, "jobs": 0}
        ],
        "users": [
            {"email": "owner@errorsweep.local", "workspace": "Platform", "role": "Platform Owner", "plan": "Owner", "status": "Active"},
            {"email": "demo@errorsweep.local", "workspace": "Demo Workspace", "role": "Workspace Owner", "plan": "Trial", "status": "Active"},
            {"email": "reviewer@errorsweep.local", "workspace": "Demo Workspace", "role": "Reviewer", "plan": "Trial", "status": "Active"},
        ],
        "audit_logs": [],
        "ai_usage_events": [],
        "selected_review_index": 0,
        "selected_subtitle_index": 0,
        "subtitle_editor_active": False,
        "subtitle_workflow": "Transcription",
        "subtitle_video_bytes": None,
        "subtitle_video_name": "",
        "subtitle_video_type": "video/mp4",
        "show_timing_grid": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_state()


# ==========================================================
# Permissions and navigation
# ==========================================================

OWNER_PAGES = [
    "Owner Console",
    "Payments Received",
    "User Access Matrix",
    "All Workspaces",
    "Platform Settings",
    "Platform Audit Logs",
]

WORKSPACE_PAGES = [
    "Dashboard",
    "Projects",
    "Jobs",
    "ErrorSweep QA",
    "ErrorSweep Pro",
    "Subtitle / Transcription Editor",
    "Scorecards",
    "Memory & Rules",
    "Team & Roles",
    "Billing",
    "Account",
    "Admin",
]

# Hidden route pages. They are not shown as navigation buttons,
# but they let editors open as dedicated professional workspaces.
HIDDEN_EDITOR_PAGES = [
    "Human Review Workspace",
    "Subtitle Workspace",
    "Transcription Workspace",
]

ROLE_PAGE_ACCESS = {
    "Platform Owner": OWNER_PAGES + WORKSPACE_PAGES,
    "Workspace Owner": WORKSPACE_PAGES,
    "Workspace Admin": ["Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Subtitle / Transcription Editor", "Scorecards", "Memory & Rules", "Team & Roles", "Account", "Admin"],
    "Project Manager": ["Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Subtitle / Transcription Editor", "Scorecards", "Memory & Rules", "Account"],
    "Translator": ["Dashboard", "Jobs", "Subtitle / Transcription Editor", "Account"],
    "Reviewer": ["Dashboard", "Jobs", "ErrorSweep QA", "Subtitle / Transcription Editor", "Scorecards", "Memory & Rules", "Account"],
    "Client Viewer": ["Dashboard", "Jobs", "Account"],
    "Billing Admin": ["Dashboard", "Billing", "Account"],
    "User": ["Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Subtitle / Transcription Editor", "Scorecards", "Memory & Rules", "Account"],
}


def current_user() -> Optional[Dict[str, Any]]:
    return st.session_state.get("user")


def current_role() -> str:
    user = current_user() or {}
    return user.get("role", "User")


def allowed_pages() -> List[str]:
    pages = list(ROLE_PAGE_ACCESS.get(current_role(), ROLE_PAGE_ACCESS["User"]))
    # Add hidden editor pages without showing them in the left navigation.
    for page in HIDDEN_EDITOR_PAGES:
        if page not in pages:
            pages.append(page)
    return pages


def is_owner() -> bool:
    return current_role() == "Platform Owner"


def page_link(page: str) -> str:
    token = query_get("es_session")
    page_param = quote(page)
    if token:
        return f"?es_session={token}&es_page={page_param}"
    return f"?es_page={page_param}"


def open_page(page: str) -> None:
    """Open an internal ErrorSweep route as a dedicated page in the same session."""
    st.session_state.page = page
    query_set("es_page", page)
    if page == "Human Review Workspace":
        session_id = st.session_state.get("active_review_session_id")
        if session_id:
            query_set("review_id", str(session_id))
    st.rerun()


def nav_button(page: str, key_prefix: str = "nav") -> None:
    active = st.session_state.get("page") == page
    cls = "es-nav-link active" if active else "es-nav-link"
    st.markdown(
        f'<a class="{cls}" href="{page_link(page)}" target="_self">{escape(page)}</a>',
        unsafe_allow_html=True,
    )


def render_navigation() -> None:
    user = current_user() or {}
    pages = allowed_pages()

    st.markdown(
        f"""
        <div class="es-rail">
          <div class="es-logo"><span class="es-logo-badge">ES</span><span>ErrorSweep</span></div>
          <div class="es-small">{APP_VERSION}</div>
          <div class="es-small" style="margin-top:8px;">Signed in as<br><b>{escape(user.get("email",""))}</b></div>
          <div style="margin-top:10px;"><span class="es-chip green">{escape(current_role())}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="es-nav-label">Workspace</div>', unsafe_allow_html=True)
    for page in WORKSPACE_PAGES:
        if page in pages:
            nav_button(page)

    if is_owner():
        st.markdown('<div class="es-nav-label">Owner only</div>', unsafe_allow_html=True)
        for page in OWNER_PAGES:
            nav_button(page, key_prefix="owner_nav")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        logout()


# ==========================================================
# General helpers
# ==========================================================

def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def add_audit(action: str, details: str = "") -> None:
    st.session_state.audit_logs.insert(0, {
        "time": now_stamp(),
        "actor": (current_user() or {}).get("email", "unknown"),
        "action": action,
        "details": details,
    })


def hero(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <section class="es-hero">
          <div class="es-kicker">{escape(kicker)}</div>
          <div class="es-title">{title}</div>
          <div class="es-subtitle">{escape(subtitle)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def metrics(cards: List[Tuple[str, Any, str]]) -> None:
    """Render metric cards without raw HTML."""
    if not cards:
        return
    cols = st.columns(min(4, len(cards)))
    for idx, (label, value, note) in enumerate(cards):
        with cols[idx % len(cols)]:
            with st.container(border=True):
                st.caption(str(label).upper())
                st.markdown(f"### {escape(str(value))}")
                if note:
                    st.caption(str(note))


def safe_text(x: Any) -> str:
    if x is None:
        return ""
    return str(x).replace("\u00A0", " ").strip()


def split_text_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_timecode(value: str) -> float:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(value)
    except Exception:
        return 0.0


def format_time(seconds: float, comma: bool = True) -> str:
    seconds = max(float(seconds), 0.0)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if comma:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return f"{h:02d}:{m:02d}:{int(s):02d}.{int((s % 1) * 1000):03d}"


def parse_srt_or_vtt(text: str) -> List[Dict[str, Any]]:
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    rows = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        idx = 0
        if re.fullmatch(r"\d+", lines[0]):
            idx = 1
        if idx >= len(lines):
            continue
        if "-->" not in lines[idx]:
            # Maybe plain text block.
            content = " ".join(lines[idx:])
            if content:
                n = len(rows)
                rows.append({
                    "id": n + 1, "start": n * 4.0, "end": n * 4.0 + 3.0,
                    "source": content, "target": "", "status": "Untranslated", "match": ""
                })
            continue
        start_s, end_s = [x.strip().split(" ")[0] for x in lines[idx].split("-->", 1)]
        content = " ".join(lines[idx + 1:]).strip()
        n = len(rows)
        rows.append({
            "id": n + 1,
            "start": parse_timecode(start_s),
            "end": parse_timecode(end_s),
            "source": content,
            "target": "",
            "status": "Untranslated",
            "match": "",
        })
    return rows


def parse_uploaded_text(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def extract_rows_from_upload(uploaded_file, mode: str = "review") -> List[Dict[str, Any]]:
    if uploaded_file is None:
        return []
    name = uploaded_file.name.lower()
    rows: List[Dict[str, Any]] = []
    try:
        if name.endswith(".xlsx"):
            wb = load_workbook(io.BytesIO(uploaded_file.getvalue()), data_only=True)
            ws = wb.active
            data = list(ws.iter_rows(values_only=True))
            if not data:
                return []
            headers = [safe_text(x).lower() for x in data[0]]
            src_idx = 0
            tgt_idx = 1 if len(headers) > 1 else None
            for i, h in enumerate(headers):
                if "source" in h or "english" in h:
                    src_idx = i
                if "target" in h or "translation" in h:
                    tgt_idx = i
            for i, row in enumerate(data[1:], start=1):
                src = safe_text(row[src_idx] if src_idx < len(row) else "")
                tgt = safe_text(row[tgt_idx] if tgt_idx is not None and tgt_idx < len(row) else "")
                if src or tgt:
                    rows.append({"id": len(rows)+1, "source": src, "target": tgt, "status": "Existing" if tgt else "Untranslated", "match": ""})
        elif name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(uploaded_file.getvalue()))
            cols = [c.lower() for c in df.columns.astype(str)]
            src_col = df.columns[0]
            tgt_col = df.columns[1] if len(df.columns) > 1 else None
            for c in df.columns:
                cl = str(c).lower()
                if "source" in cl or "english" in cl:
                    src_col = c
                if "target" in cl or "translation" in cl:
                    tgt_col = c
            for _, row in df.iterrows():
                src = safe_text(row.get(src_col, ""))
                tgt = safe_text(row.get(tgt_col, "")) if tgt_col is not None else ""
                if src or tgt:
                    rows.append({"id": len(rows)+1, "source": src, "target": tgt, "status": "Existing" if tgt else "Untranslated", "match": ""})
        elif name.endswith(".docx"):
            doc = Document(io.BytesIO(uploaded_file.getvalue()))
            if doc.tables:
                table = doc.tables[0]
                for row in table.rows[1:] if len(table.rows) > 1 else table.rows:
                    cells = [safe_text(c.text) for c in row.cells]
                    if any(cells):
                        rows.append({"id": len(rows)+1, "source": cells[0] if cells else "", "target": cells[1] if len(cells)>1 else "", "status": "Existing" if len(cells)>1 and cells[1] else "Untranslated", "match": ""})
            for p in doc.paragraphs:
                txt = safe_text(p.text)
                if txt:
                    rows.append({"id": len(rows)+1, "source": txt, "target": "", "status": "Untranslated", "match": ""})
        else:
            text = parse_uploaded_text(uploaded_file)
            if name.endswith((".srt", ".vtt")):
                rows = parse_srt_or_vtt(text)
            else:
                lines = split_text_lines(text)
                for line in lines:
                    rows.append({"id": len(rows)+1, "source": line, "target": "", "status": "Untranslated", "match": ""})
    except Exception as exc:
        st.error(f"Could not parse uploaded file: {exc}")
    return rows


def rows_to_csv(rows: List[Dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def rows_to_srt(rows: List[Dict[str, Any]], use_target: bool = True) -> bytes:
    out = []
    for i, row in enumerate(rows, start=1):
        text = safe_text(row.get("target" if use_target else "source", ""))
        if not text:
            text = safe_text(row.get("source", ""))
        out.append(str(i))
        out.append(f"{format_time(row.get('start', (i-1)*4), comma=True)} --> {format_time(row.get('end', (i-1)*4+3), comma=True)}")
        out.append(text)
        out.append("")
    return "\n".join(out).encode("utf-8")


@st.cache_resource
def get_review_session_store() -> Dict[str, Dict[str, Any]]:
    """Small in-memory review-session store.

    Streamlit reruns can cause a button on the Pro page to re-render before the
    hidden editor page has read session_state. We store the Pro review rows under
    a stable session id and pass that id through the query string, so the editor
    can restore rows reliably instead of opening as a blank page.
    """
    return {}


def save_review_session_to_store(rows: List[Dict[str, Any]], title: str, target_language: str, file_name: str) -> str:
    """Save a Pro review job for separate-tab editor use.

    v42 release hardening:
    - session memory for current tab
    - local JSON fallback for development
    - Supabase persistence when SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are configured
    """
    session_id = uuid.uuid4().hex
    user = current_user() or {}
    metadata = {
        "title": title,
        "target_language": target_language,
        "file_name": file_name,
        "created": now_stamp() if "now_stamp" in globals() else "",
        "source": "ErrorSweep Pro",
        "workspace": user.get("workspace", "Demo Workspace"),
        "user_email": user.get("email", ""),
        "status": "draft",
    }
    payload = {
        "job_id": session_id,
        "rows": rows,
        "metadata": metadata,
        "title": title,
        "target_language": target_language,
        "file_name": file_name,
        "created": metadata["created"],
        "job_type": "cat",
    }
    get_review_session_store()[session_id] = payload

    # Existing v41 local job store fallback.
    if save_editor_job is not None:
        try:
            save_editor_job("cat", rows, metadata=metadata, job_id=session_id)
        except Exception:
            pass

    # v42 production persistence.
    if save_persistent_editor_job is not None:
        try:
            save_persistent_editor_job("cat", rows, metadata=metadata, job_id=session_id, user=user)
        except Exception:
            pass

    st.session_state["active_review_session_id"] = session_id

    # v43 owner-console handoff: keep visible current/recent job details even if
    # Supabase/local persistence is not immediately readable in this Streamlit run.
    owner_job_record = {
        "id": session_id,
        "job_type": "cat",
        "workspace": metadata.get("workspace", ""),
        "user_email": metadata.get("user_email", ""),
        "file_name": file_name,
        "target_language": target_language,
        "status": metadata.get("status", "draft"),
        "row_count": len(rows or []),
        "created": metadata.get("created", ""),
        "updated_at": metadata.get("created", ""),
        "source": metadata.get("source", "ErrorSweep Pro"),
    }
    st.session_state["last_pro_task_details"] = owner_job_record
    st.session_state.setdefault("owner_recent_editor_jobs", [])
    st.session_state["owner_recent_editor_jobs"] = [
        owner_job_record,
        *[j for j in st.session_state["owner_recent_editor_jobs"] if j.get("id") != session_id],
    ][:25]
    return session_id


def load_review_session_from_store(session_id: str) -> bool:
    """Load review rows from memory, Supabase persistence, or local fallback."""
    if not session_id:
        return False
    payload = get_review_session_store().get(session_id)

    if not payload and load_persistent_editor_job is not None:
        try:
            payload = load_persistent_editor_job(session_id)
        except Exception:
            payload = None

    if not payload and load_editor_job is not None:
        try:
            payload = load_editor_job(session_id)
        except Exception:
            payload = None

    if not payload:
        return False
    rows = payload.get("rows") or []
    if not rows:
        return False
    metadata = payload.get("metadata") or payload
    st.session_state.review_segments = rows
    st.session_state.last_pro_review_segments = rows
    st.session_state.latest_human_review_segments = rows
    st.session_state.pro_post_editing_ready = True
    st.session_state.selected_review_index = min(int(st.session_state.get("selected_review_index", 0) or 0), max(len(rows)-1, 0))
    st.session_state.review_workspace_title = metadata.get("title") or payload.get("title") or "ErrorSweep Pro"
    st.session_state.review_workspace_language = metadata.get("target_language") or payload.get("target_language") or ""
    st.session_state.review_workspace_file_name = metadata.get("file_name") or payload.get("file_name") or ""
    st.session_state.active_review_session_id = session_id
    return True


def prepare_human_review_session(rows: List[Dict[str, Any]], source: str = "ErrorSweep Pro", target_language: str = "", file_name: str = "") -> None:
    """Store rows in a durable Human Review session before opening the editor.

    This fixes the blank-page issue: the review workspace reads from
    st.session_state.review_segments, so Pro must always seed that state
    before routing to the dedicated Human Review Workspace page.
    """
    prepared = []
    for i, row in enumerate(rows, start=1):
        src = safe_text(row.get("source", ""))
        tgt = safe_text(row.get("target", row.get("translation", "")))
        status = safe_text(row.get("status", "MT" if tgt else "Needs Review"))
        match = safe_text(row.get("match", "MT" if tgt else "Untranslated"))
        prepared.append({
            "id": row.get("id", i),
            "location": row.get("location", f"Segment {i}"),
            "source": src,
            "target": tgt,
            "status": status,
            "match": match,
            "language": target_language,
            "file_name": file_name,
            "source_workflow": source,
            "notes": row.get("notes", ""),
            "start": row.get("start", ""),
            "end": row.get("end", ""),
        })
    # Store in more than one session key. Some Streamlit reruns can make a hidden
    # route render before the editor reads review_segments; these backup keys let
    # the workspace restore itself instead of opening as a blank page.
    st.session_state.review_segments = prepared
    st.session_state.last_pro_review_segments = prepared
    st.session_state.latest_human_review_segments = prepared
    st.session_state.pro_review_rows = prepared
    st.session_state.pro_post_edit_rows = prepared
    st.session_state.pro_post_edit_language = target_language
    st.session_state.pro_post_edit_file_name = file_name
    st.session_state.pro_post_editing_ready = True
    st.session_state.selected_review_index = 0
    st.session_state.review_workspace_title = source
    st.session_state.review_workspace_language = target_language
    st.session_state.review_workspace_file_name = file_name
    st.session_state.review_workspace_created = now_stamp() if "now_stamp" in globals() else ""
    session_id = save_review_session_to_store(prepared, source, target_language, file_name)
    query_set("review_id", session_id)


def restore_human_review_session_from_cache() -> bool:
    """Restore Pro review rows if the dedicated page is opened after a rerun.

    This avoids the confusing blank-page experience after clicking
    "Open Human Review workspace". The restore order is:
    1. current review_segments
    2. review_id query/session store
    3. backup session_state lists
    """
    if st.session_state.get("review_segments"):
        return True

    session_id = st.session_state.get("active_review_session_id") or query_get("review_id")
    if session_id and load_review_session_from_store(str(session_id)):
        return True

    for key in ("last_pro_review_segments", "latest_human_review_segments", "pro_review_rows", "pro_post_edit_rows"):
        cached = st.session_state.get(key)
        if isinstance(cached, list) and cached:
            st.session_state.review_segments = cached
            st.session_state.selected_review_index = 0
            st.session_state.pro_post_editing_ready = True
            return True
    return False


def go_to_human_review_workspace() -> None:
    """Route to the dedicated Pro post-editing workspace safely."""
    restore_human_review_session_from_cache()
    session_id = st.session_state.get("active_review_session_id")
    if session_id:
        query_set("review_id", str(session_id))
    open_page("Human Review Workspace")


def current_session_token_for_links() -> str:
    token = query_get("es_session")
    if token:
        return token
    user = current_user() or {}
    if not user:
        return ""
    payload = {**user, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    try:
        return sign_payload(payload)
    except Exception:
        return ""


def external_editor_url(editor_type: str, job_id: str) -> str:
    parts = []
    token = current_session_token_for_links()
    if token:
        parts.append(f"es_session={quote(token)}")
    parts.append(f"es_editor={quote(editor_type)}")
    parts.append(f"job_id={quote(str(job_id))}")
    return "?" + "&".join(parts)


def render_external_editor_link(label: str, editor_type: str, job_id: str) -> None:
    url = external_editor_url(editor_type, job_id)
    st.markdown(
        f"""
        <a href="{url}" target="_blank" style="
            display:flex; align-items:center; justify-content:center; width:100%;
            padding: 0.78rem 1rem; border-radius:14px; text-decoration:none;
            background: linear-gradient(90deg,#00d985,#34bdf6); color:#061018;
            font-weight:900; box-shadow:0 12px 30px rgba(52,189,246,.25);
        ">{escape(label)} ↗</a>
        """,
        unsafe_allow_html=True,
    )


def load_external_editor_payload(job_id: str) -> Optional[Dict[str, Any]]:
    if not job_id:
        return None

    # v42 production persistence first, so new browser tabs survive Streamlit restarts.
    if load_persistent_editor_job is not None:
        try:
            payload = load_persistent_editor_job(job_id)
            if payload:
                return payload
        except Exception:
            pass

    # v41 local JSON fallback.
    if load_editor_job is not None:
        try:
            payload = load_editor_job(job_id)
            if payload:
                return payload
        except Exception:
            pass
    return get_review_session_store().get(job_id)


def save_external_editor_payload(job_id: str, payload: Dict[str, Any]) -> None:
    if not job_id or not payload:
        return
    rows = payload.get("rows") or []
    metadata = payload.get("metadata") or {
        "title": payload.get("title", "ErrorSweep CAT"),
        "target_language": payload.get("target_language", ""),
        "file_name": payload.get("file_name", ""),
    }
    get_review_session_store()[job_id] = {
        "rows": rows,
        "metadata": metadata,
        "title": metadata.get("title", "ErrorSweep CAT"),
        "target_language": metadata.get("target_language", ""),
        "file_name": metadata.get("file_name", ""),
        "created": metadata.get("created", ""),
        "job_type": payload.get("job_type", "cat"),
    }

    if update_editor_job is not None:
        try:
            update_editor_job(job_id, rows=rows, metadata=metadata)
        except Exception:
            pass

    # v42 persistent save/update.
    if update_persistent_editor_job is not None:
        try:
            update_persistent_editor_job(job_id, rows=rows, metadata=metadata, status=metadata.get("status", "draft"))
        except Exception:
            pass


def render_external_cat_editor(job_id: str) -> None:
    payload = load_external_editor_payload(job_id)
    if not payload:
        st.error("Editor job not found or expired. Please go back to ErrorSweep Pro and open the editor again.")
        return
    rows = payload.get("rows") or []
    metadata = payload.get("metadata") or payload
    if not rows:
        st.error("This editor job has no rows. Please rerun Pro translation and open the editor again.")
        return

    st.markdown(
        """
        <style>
        .block-container { max-width: 100vw !important; padding: .15rem .25rem .25rem .25rem !important; }
        .es-editor-shell { border: 1px solid rgba(148,163,184,.25); background:#080a12; min-height: calc(100vh - 10px); overflow:hidden; }
        .es-editor-top { height: 50px; display:flex; align-items:center; justify-content:space-between; padding:0 14px; background:#242a2f; border-bottom:1px solid rgba(255,255,255,.08); }
        .es-editor-brand { display:flex; align-items:center; gap:10px; font-weight:900; color:#fff; }
        .es-editor-logo { width:32px; height:32px; border-radius:10px; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg,#00d985,#34bdf6,#8b5cf6); color:#061018; font-weight:1000; }
        .es-editor-pill { display:inline-flex; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:900; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); color:#e5edff; }
        .es-editor-pill.green { background:rgba(0,217,133,.14); border-color:rgba(0,217,133,.35); color:#63ffc4; }
        .es-editor-tabs { height:36px; display:flex; align-items:center; gap:0; background:#eef2f7; color:#0f172a; border-bottom:1px solid #cbd5e1; }
        .es-editor-tab { height:36px; padding:0 22px; display:flex; align-items:center; font-weight:800; font-size:13px; border-right:1px solid #cbd5e1; }
        .es-editor-tab.active { background:#fff; border-bottom:2px solid #00d985; }
        .es-context-preview { height:96px; background:#e9eef5; border-bottom:1px solid #cbd5e1; display:flex; justify-content:center; }
        .es-context-phone { width:430px; background:#1f2027; display:flex; align-items:center; justify-content:center; }
        .es-context-highlight { padding:8px 54px; border-radius:999px; background:#4b5563; color:#7dd3fc; border:2px dashed #7dd3fc; font-weight:800; }
        .es-formatbar { height:32px; display:flex; align-items:center; gap:12px; background:#313940; color:#fff; border-bottom:1px solid rgba(255,255,255,.10); padding:0 10px; font-size:13px; }
        .es-side-card { background:#f5f6f8; color:#1f2937; border-left:1px solid #cbd5e1; height: calc(100vh - 254px); overflow-y:auto; }
        .es-side-head { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-bottom:1px solid #cbd5e1; font-weight:900; }
        .es-side-section { padding:14px; border-bottom:1px solid #d8dee8; }
        .es-side-title { font-size:13px; font-weight:900; color:#4b5563; margin-bottom:8px; }
        .es-resource { display:grid; grid-template-columns:38px 1fr; border:1px solid #d1d5db; background:#fff; margin-bottom:8px; }
        .es-resource-code { background:#cbd5e1; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:12px; }
        .es-resource-body { padding:8px; font-size:13px; }
        .es-muted { color:#64748b; font-size:12px; }
        div[data-testid="stDataEditor"] { border-radius:0 !important; border:0 !important; }
        div[data-testid="stDataEditor"] textarea, div[data-testid="stDataEditor"] input { font-size:14px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    title = safe_text(metadata.get("title", "ErrorSweep CAT")) or "ErrorSweep CAT"
    file_name = safe_text(metadata.get("file_name", "translation_job")) or "translation_job"
    language = safe_text(metadata.get("target_language", "Target")) or "Target"
    completion = compute_review_completion(rows)

    st.markdown(
        f"""
        <div class="es-editor-shell">
          <div class="es-editor-top">
            <div class="es-editor-brand"><div class="es-editor-logo">ES</div><div><div>{escape(file_name)}</div><div class="es-muted">{escape(title)} · Target: {escape(language)} · Job: {escape(job_id[:10])}</div></div></div>
            <div style="display:flex; align-items:center; gap:8px;"><span class="es-editor-pill green">Accepted</span><span class="es-editor-pill">TM</span><span class="es-editor-pill">TB</span><span class="es-editor-pill">MT</span></div>
          </div>
          <div class="es-editor-tabs"><div class="es-editor-tab active">Context</div><div class="es-editor-tab">Quality Checks</div><div class="es-editor-tab">Search TM</div><div class="es-editor-tab">Glossary</div><div style="margin-left:auto; padding-right:14px; font-size:13px;">Mode: <b>Highlight strings</b></div></div>
          <div class="es-context-preview"><div class="es-context-phone"><div class="es-context-highlight">Open account settings</div></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    toolbar_cols = st.columns([0.45, 0.18, 0.13, 0.10, 0.14], gap="small")
    with toolbar_cols[0]:
        search = st.text_input("Search", placeholder="Search source and translations", label_visibility="collapsed", key=f"ext_cat_search_{job_id}")
    with toolbar_cols[1]:
        status_filter = st.selectbox("Status", ["All", "MT", "Needs Review", "Approved", "Untranslated", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Rejected", "Needs Rework"], label_visibility="collapsed", key=f"ext_cat_status_{job_id}")
    with toolbar_cols[2]:
        pending_only = st.checkbox("Pending", value=False, key=f"ext_cat_pending_{job_id}")
    with toolbar_cols[3]:
        st.metric("Rows", len(rows))
    with toolbar_cols[4]:
        st.metric("Approved", completion["approved"])

    st.markdown('<div class="es-formatbar"><b>B</b><i>I</i><u>U</u><span>↶</span><span>↷</span><span>BR</span><span>NBSP</span><span>✓</span></div>', unsafe_allow_html=True)

    filtered_indexes = []
    needle = safe_text(search).lower().strip()
    for i, r in enumerate(rows):
        src = safe_text(r.get("source", ""))
        tgt = safe_text(r.get("target", ""))
        status = safe_text(r.get("status", "Needs Review")) or "Needs Review"
        if needle and needle not in src.lower() and needle not in tgt.lower():
            continue
        if status_filter != "All" and status != status_filter:
            continue
        if pending_only and status in {"Approved", "100%", "101%"}:
            continue
        filtered_indexes.append(i)
    if not filtered_indexes:
        filtered_indexes = list(range(len(rows)))

    grid_rows = []
    for i in filtered_indexes:
        r = rows[i]
        status = safe_text(r.get("status", "Needs Review")) or "Needs Review"
        grid_rows.append({
            "No": i + 1,
            "Source (EN)": safe_text(r.get("source", "")),
            "Target": safe_text(r.get("target", "")),
            "Match": safe_text(r.get("match", "MT")) or "MT",
            "QA": "✓" if status in {"Approved", "100%", "101%"} else "⚠" if status in {"Needs Review", "Untranslated", "Needs Rework"} else "",
            "Status": status,
            "Notes": safe_text(r.get("notes", "")),
            "Location": safe_text(r.get("location", f"Segment {i+1}")),
        })

    grid_col, side_col = st.columns([0.81, 0.19], gap="small")
    with grid_col:
        edited_df = st.data_editor(
            pd.DataFrame(grid_rows),
            use_container_width=True,
            hide_index=True,
            height=620,
            num_rows="fixed",
            disabled=["No", "Source (EN)", "Match", "QA", "Location"],
            column_order=["No", "Source (EN)", "Target", "Match", "QA", "Status", "Notes", "Location"],
            column_config={
                "No": st.column_config.NumberColumn("#", width="small"),
                "Source (EN)": st.column_config.TextColumn("Source (EN)", width="large"),
                "Target": st.column_config.TextColumn("Target", width="large"),
                "Match": st.column_config.TextColumn("Match", width="small"),
                "QA": st.column_config.TextColumn("QA", width="small"),
                "Status": st.column_config.SelectboxColumn("Status", options=["MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"], width="medium"),
                "Notes": st.column_config.TextColumn("Notes", width="medium"),
                "Location": st.column_config.TextColumn("Location", width="medium"),
            },
            key=f"external_cat_grid_{job_id}",
        )

        action_cols = st.columns([1, 1, 1, 1, 1])
        if action_cols[0].button("Save Page", type="primary", use_container_width=True, key=f"ext_cat_save_{job_id}"):
            for _, erow in edited_df.iterrows():
                idx = int(erow["No"]) - 1
                if 0 <= idx < len(rows):
                    rows[idx]["target"] = safe_text(erow.get("Target", ""))
                    rows[idx]["status"] = safe_text(erow.get("Status", "")) or "Needs Review"
                    rows[idx]["notes"] = safe_text(erow.get("Notes", ""))
            payload["rows"] = rows
            save_external_editor_payload(job_id, payload)
            st.success("Saved editor changes.")
        if action_cols[1].button("Approve visible", use_container_width=True, key=f"ext_cat_approve_{job_id}"):
            for _, erow in edited_df.iterrows():
                idx = int(erow["No"]) - 1
                if 0 <= idx < len(rows):
                    rows[idx]["target"] = safe_text(erow.get("Target", ""))
                    rows[idx]["status"] = "Approved" if safe_text(erow.get("Target", "")).strip() else "Needs Review"
                    rows[idx]["notes"] = safe_text(erow.get("Notes", ""))
            payload["rows"] = rows
            save_external_editor_payload(job_id, payload)
            st.success("Visible rows approved.")
        if action_cols[2].button("Submit", use_container_width=True, key=f"ext_cat_submit_{job_id}"):
            for r in rows:
                if safe_text(r.get("target", "")).strip() and safe_text(r.get("status", "")) not in {"Rejected", "Needs Rework"}:
                    r["status"] = "Approved"
            payload["rows"] = rows
            payload.setdefault("metadata", metadata)["submitted_at"] = now_stamp()
            save_external_editor_payload(job_id, payload)
            st.success("Submitted reviewed job.")
        if action_cols[3].button("Refresh", use_container_width=True, key=f"ext_cat_refresh_{job_id}"):
            st.rerun()
        if action_cols[4].button("Back to Pro", use_container_width=True, key=f"ext_cat_back_{job_id}"):
            query_clear("es_editor")
            query_clear("job_id")
            open_page("ErrorSweep Pro")

        dl1, dl2, dl3 = st.columns(3)
        base = re.sub(r"\.[^.]+$", "", file_name) or "reviewed_translation"
        dl1.download_button("Download reviewed Excel", build_reviewed_translation_workbook(rows), file_name=f"{base}_reviewed.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        dl2.download_button("Download reviewed CSV", rows_to_csv(rows), file_name=f"{base}_reviewed.csv", mime="text/csv", use_container_width=True)
        dl3.download_button("Download target text", build_reviewed_plain_text(rows), file_name=f"{base}_target.txt", mime="text/plain", use_container_width=True)

    with side_col:
        st.markdown('<div class="es-side-card">', unsafe_allow_html=True)
        st.markdown('<div class="es-side-head"><span>Additional Details</span><span class="es-editor-pill" style="background:#f97316;color:white;">1</span></div>', unsafe_allow_html=True)
        selected_no = int(edited_df.iloc[0]["No"]) if not edited_df.empty else 1
        selected_idx = max(0, min(selected_no - 1, len(rows) - 1))
        selected = rows[selected_idx]
        matches = compute_matches(safe_text(selected.get("source", "")))
        st.markdown('<div class="es-side-section"><div class="es-side-title">Language Resources</div>', unsafe_allow_html=True)
        if matches["glossary"]:
            for g in matches["glossary"][:5]:
                st.markdown(f'<div class="es-resource"><div class="es-resource-code">GT</div><div class="es-resource-body"><b>{escape(g.get("target", ""))}</b><br><span class="es-muted">{escape(g.get("source", ""))}</span></div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="es-resource"><div class="es-resource-code">GT</div><div class="es-resource-body"><b>Glossary</b><br><span class="es-muted">No glossary hit.</span></div></div>', unsafe_allow_html=True)
        if matches["tm"]:
            for m in matches["tm"][:3]:
                st.markdown(f'<div class="es-resource"><div class="es-resource-code">TM</div><div class="es-resource-body"><b>{escape(m.get("type", "TM"))}</b><br><span class="es-muted">{escape(m.get("target", ""))}</span></div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="es-side-section"><div class="es-side-title">Quality Checks</div><div class="es-resource"><div class="es-resource-code">QA</div><div class="es-resource-body">Check placeholders, glossary, DNT, punctuation, and number consistency before submit.</div></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="es-side-section"><div class="es-side-title">Selected Row</div><div class="es-resource"><div class="es-resource-code">#</div><div class="es-resource-body"><b>{selected_idx+1}</b><br><span class="es-muted">{escape(safe_text(selected.get("location", "")))}</span></div></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="es-side-section"><div class="es-side-title">Issues</div><button style="width:100%;border:1px solid #94a3b8;background:white;padding:8px;font-weight:800;">Open New Issue</button><div class="es-muted" style="margin-top:8px;">View related source issues (0)</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="es-side-section"><div class="es-side-title">History</div><div class="es-muted">Saved changes are stored under this job_id.</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_external_media_editor(job_id: str) -> None:
    payload = load_external_editor_payload(job_id)
    if not payload:
        st.error("Media editor job not found or expired.")
        return
    rows = payload.get("rows") or []
    st.warning("Media external editor shell is ready. Full video persistence will be connected in a later backend step.")
    st.data_editor(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=650, key=f"external_media_grid_{job_id}")


def render_external_editor_router() -> bool:
    editor_type = query_get("es_editor")
    if not editor_type:
        return False
    job_id = query_get("job_id")
    if editor_type == "cat":
        render_external_cat_editor(job_id)
        return True
    if editor_type == "media":
        render_external_media_editor(job_id)
        return True
    st.error("Unknown editor route.")
    return True



def build_reviewed_translation_workbook(rows: List[Dict[str, Any]]) -> bytes:
    """Excel output from Human Review. Always safe and easy for clients to review."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reviewed Translation"
    headers = ["Segment ID", "Location", "Source Text", "Final Translation", "Status", "Match", "Language", "Notes"]
    ws.append(headers)
    for row in rows:
        ws.append([
            row.get("id", ""),
            row.get("location", ""),
            row.get("source", ""),
            row.get("target", ""),
            row.get("status", ""),
            row.get("match", ""),
            row.get("language", ""),
            row.get("notes", ""),
        ])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    widths = {"A": 12, "B": 22, "C": 55, "D": 55, "E": 18, "F": 14, "G": 16, "H": 28}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


def build_reviewed_plain_text(rows: List[Dict[str, Any]]) -> bytes:
    return "\n".join(safe_text(r.get("target", "")) for r in rows).encode("utf-8-sig")


def compute_review_completion(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(rows)
    translated = sum(1 for r in rows if safe_text(r.get("target", "")).strip())
    approved = sum(1 for r in rows if safe_text(r.get("status", "")) == "Approved")
    needs_review = sum(1 for r in rows if "Review" in safe_text(r.get("status", "")) or not safe_text(r.get("target", "")).strip())
    return {"total": total, "translated": translated, "approved": approved, "needs_review": needs_review}


def compute_matches(source: str) -> Dict[str, List[Dict[str, str]]]:
    source_l = source.lower()
    tm_hits = []
    for item in st.session_state.tm:
        if item.get("source", "").lower() == source_l:
            tm_hits.append({"type": "TM 100%", "source": item.get("source",""), "target": item.get("target","")})
        elif source_l and item.get("source", "").lower() in source_l:
            tm_hits.append({"type": "TM fuzzy", "source": item.get("source",""), "target": item.get("target","")})

    gloss_hits = []
    for item in st.session_state.glossary:
        if item.get("source","").lower() in source_l:
            gloss_hits.append(item)

    dnt_hits = [{"term": term} for term in st.session_state.dnt if term.lower() in source_l]
    return {"tm": tm_hits[:5], "glossary": gloss_hits[:8], "dnt": dnt_hits[:8]}


def openai_client() -> Optional[OpenAI]:
    key = secret("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key)


def current_ai_route_label() -> str:
    """Small safe label for UI. Do not expose provider names, URLs, or tokens."""
    if st.session_state.get("byo_openai_api_key"):
        return "BYO key active"
    if current_builtin_engine_label is not None:
        try:
            return current_builtin_engine_label()
        except Exception:
            pass
    return "Translation engine not configured"


def log_ai_usage_event(usage: Dict[str, Any], purpose: str, segment_count: int = 0) -> None:
    """Log AI/translation usage in session and, when configured, Supabase.

    v42 persists Azure character usage and BYO/Managed AI events for owner reporting.
    """
    st.session_state.setdefault("ai_usage_events", [])
    record = {
        "time": now_stamp() if "now_stamp" in globals() else datetime.now().strftime("%Y-%m-%d %H:%M"),
        "purpose": purpose,
        "provider": usage.get("provider", usage.get("engine", "unknown")),
        "model": usage.get("model", usage.get("engine", "")),
        "managed": usage.get("managed", False),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "characters": usage.get("characters", 0),
        "requests": usage.get("requests", 0),
        "success": usage.get("success", False),
        "error": usage.get("error", ""),
        "segments": segment_count,
    }
    st.session_state.ai_usage_events.insert(0, record)

    if log_persistent_usage_event is not None:
        try:
            log_persistent_usage_event(record, purpose=purpose, segment_count=segment_count, user=current_user() or {}, metadata={"app_version": APP_VERSION})
        except Exception:
            pass


def call_main_api_translate(texts: List[str], target_language: str, domain: str) -> List[str]:
    """Translate through the v30 two-phase backend.

    User has BYO key:
        Keep the existing BYO OpenAI/vLLM-style prompt path unchanged.

    User has no key:
        Phase 2 if NLLB_MODE=True  -> self-hosted NLLB.
        Otherwise                  -> Phase 1 Azure Translator.
    """
    if not texts:
        return []

    user_key = str(st.session_state.get("byo_openai_api_key", "") or "").strip()

    # ----------------------------------------------------------
    # BYO KEY PATH — keep existing logic unchanged.
    # ----------------------------------------------------------
    if user_key:
        if ai_json_items is None or select_ai_route is None:
            st.error("BYO-key AI router file is missing. Add managed_ai_router.py beside app.py.")
            return ["" for _ in texts]

        try:
            route = select_ai_route(user_openai_key=user_key, purpose="translate")
        except Exception as exc:
            st.error(f"User AI route is not configured: {exc}")
            return ["" for _ in texts]

        system_prompt = f"""
You are ErrorSweep AI, a professional localization translator.
Return JSON only. Do not use markdown.

Task:
Translate source strings into {target_language} for a {domain} localization project.

Hard rules:
1. Preserve placeholders exactly: {{{{email}}}}, {{{{password}}}}, %s, %d, <tags>, URLs, emails.
2. Preserve numbers, units, emoji/icons, bullets, and product names.
3. Preserve DNT/client locked terms if they appear.
4. Square bracket UI labels may be localized inside brackets, but keep the bracket structure.
5. Do not leave translations blank.
6. Return a JSON object with key "items".

Output shape:
{{
  "items": [
    {{"index": 0, "translation": "translated text"}}
  ]
}}
"""
        payload = {
            "target_language": target_language,
            "domain": domain,
            "texts": [{"index": i, "source": text} for i, text in enumerate(texts)],
        }

        items, usage = ai_json_items(
            system_prompt=system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False),
            route=route,
            temperature=0.0,
            max_tokens=4500,
        )
        log_ai_usage_event(usage, "translate", len(texts))

        result = [""] * len(texts)
        for item in items:
            try:
                idx = int(item.get("index", 0))
            except Exception:
                continue
            if 0 <= idx < len(result):
                result[idx] = safe_text(item.get("translation", ""))

        if not any(result) and usage.get("error"):
            st.error(f"Translation service error: {usage.get('error')}")
        return result

    # ----------------------------------------------------------
    # NO USER KEY PATH — v30 built-in translation engine.
    # Phase 1 default: Azure Translator.
    # Phase 2 future: NLLB when NLLB_MODE=True.
    # ----------------------------------------------------------
    if builtin_translate_batch is None:
        st.error("Built-in translation router is missing. Add translator_router.py, azure_translator.py, and nllb_translator.py beside app.py.")
        return ["" for _ in texts]

    try:
        translations, usage = builtin_translate_batch(
            source_language="English",
            target_language=target_language,
            texts=texts,
            user_api_key="",
            protected_terms=[],
            metadata={"domain": domain},
        )
        # Store usage in the same owner-console log format.
        log_ai_usage_event({
            "provider": usage.get("provider", "built_in_translation"),
            "model": usage.get("engine", "built_in_translation"),
            "managed": True,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "success": usage.get("success", True),
            "error": usage.get("error", ""),
            "characters": usage.get("characters", 0),
            "requests": usage.get("requests", 0),
        }, "translate", len(texts))
        return [safe_text(t) for t in translations]
    except Exception as exc:
        st.error(f"Translation service error: {str(exc)}")
        return ["" for _ in texts]



def generate_transcription_rows_from_video(video_file, locale: str = "en-US", prompt: str = "") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Generate transcript rows from uploaded video/audio.

    v32 policy:
    - Auto transcription is available only when the user provides a BYO API key.
    - Azure Translator is text-only in ErrorSweep and is NOT used for transcription.
    - If no user API key is available, return blank starter rows for manual human editing.
    """
    if video_file is None:
        return default_subtitle_segments(10, transcription=True), {"success": False, "error": "No video uploaded."}

    user_key = str(st.session_state.get("byo_openai_api_key", "") or "").strip()
    if not user_key:
        return default_subtitle_segments(10, transcription=True), {
            "success": False,
            "provider": "manual_transcription",
            "engine": "manual_editor",
            "error": "No user API key available. Blank rows were created for manual transcription.",
        }

    if transcribe_media_to_rows is None:
        return default_subtitle_segments(10, transcription=True), {"success": False, "error": "speech_transcription.py is missing."}

    rows, usage = transcribe_media_to_rows(
        media_bytes=video_file.getvalue(),
        filename=getattr(video_file, "name", "video.mp4"),
        mime_type=getattr(video_file, "type", "video/mp4") or "video/mp4",
        user_openai_key=user_key,
        locale=locale,
        prompt=prompt,
    )
    st.session_state.setdefault("ai_usage_events", [])
    st.session_state.ai_usage_events.insert(0, {
        "time": now_stamp(),
        "purpose": "transcription",
        "provider": usage.get("provider", "user_speech"),
        "model": usage.get("engine", "speech"),
        "managed": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "success": usage.get("success", False),
        "error": usage.get("error", ""),
        "segments": len(rows),
    })
    return rows, usage


def translate_subtitle_sources(rows: List[Dict[str, Any]], target_language: str, domain: str = "Subtitling") -> Tuple[List[Dict[str, Any]], int]:
    """Translate source rows into target subtitle rows using BYO key or built-in Azure/NLLB."""
    source_texts = [safe_text(r.get("source", "")) for r in rows]
    translations = call_main_api_translate(source_texts, target_language, domain)
    missing = 0
    for row, trans in zip(rows, translations):
        row["target"] = safe_text(trans)
        if row["target"]:
            row["status"] = "MT"
            row["match"] = "MT"
        else:
            row["status"] = "Needs Review"
            row["match"] = "Untranslated"
            missing += 1
    return rows, missing

def call_main_api_qa(rows: List[Dict[str, Any]], domain: str, strictness: str = "Standard") -> List[Dict[str, Any]]:
    """Optional Managed AI QA route. Deterministic checks still run first elsewhere."""
    if not rows:
        return []
    if ai_json_items is None or select_ai_route is None:
        return []
    try:
        route = select_ai_route(
            user_openai_key=st.session_state.get("byo_openai_api_key", ""),
            purpose="qa",
        )
    except Exception:
        return []

    system_prompt = """
You are ErrorSweep AI, a conservative localization QA reviewer.
Return JSON only. Do not invent errors.
Flag only real issues supported by source/target evidence.
DNT/placeholder/number damage is severe. Empty target is Critical.

Output shape:
{"items":[{"id":1,"issue":"short issue","severity":"Minor|Major|Critical","suggestion":"fix","reason":"why"}]}
"""
    payload = {
        "domain": domain,
        "strictness": strictness,
        "segments": [
            {"id": r.get("id"), "source": r.get("source", ""), "target": r.get("target", "")}
            for r in rows[:80]
        ],
    }
    items, usage = ai_json_items(
        system_prompt=system_prompt,
        user_prompt=json.dumps(payload, ensure_ascii=False),
        route=route,
        temperature=0.0,
        max_tokens=3000,
    )
    log_ai_usage_event(usage, "qa", len(rows[:80]))
    return items

def auto_detect_domain(text_sample: str) -> str:
    t = text_sample.lower()
    if any(x in t for x in ["button", "dashboard", "settings", "login", "password", "screen", "menu", "tooltip"]):
        return "Software UI"
    if any(x in t for x in ["subtitle", "-->", "caption", "dialogue", "scene"]):
        return "Subtitling"
    if any(x in t for x in ["invoice", "payment", "bank", "account", "revenue"]):
        return "Finance"
    if any(x in t for x in ["agreement", "clause", "contract", "legal"]):
        return "Legal"
    if any(x in t for x in ["course", "lesson", "quiz", "module"]):
        return "E-learning"
    if any(x in t for x in ["campaign", "brand", "copy", "ad", "landing page"]):
        return "Marketing"
    return "General"


# ==========================================================
# Login
# ==========================================================

def render_login() -> None:
    hero("Account required", "ErrorSweep", "Secure localization QA, translation review, scorecards, subtitling, transcription, and memory workflows.")

    tabs = st.tabs(["Platform owner", "Workspace user", "Demo access"])

    with tabs[0]:
        st.markdown("### Platform Owner Login")
        owner_user = secret("ERRORSWEEP_OWNER_USERNAME", "owner@errorsweep.local")
        owner_pass = secret("ERRORSWEEP_OWNER_PASSWORD", "")
        with st.form("owner_login"):
            email = st.text_input("Owner email", value=owner_user if not owner_pass else "")
            password = st.text_input("Owner password", type="password")
            submitted = st.form_submit_button("Sign in as Platform Owner", use_container_width=True)
        if submitted:
            if owner_pass and hmac.compare_digest(email.strip(), owner_user.strip()) and hmac.compare_digest(password, owner_pass):
                login_user(email, "Platform Owner", "owner", "Platform")
                add_audit("Owner sign-in", email)
                st.rerun()
            elif not owner_pass:
                st.warning("Owner password is not configured. Use Demo access while building.")
            else:
                st.error("Invalid owner credentials.")

    with tabs[1]:
        st.markdown("### Workspace User Login")
        user_name = secret("ERRORSWEEP_USER_USERNAME", "user@errorsweep.local")
        user_pass = secret("ERRORSWEEP_USER_PASSWORD", "")
        default_role = secret("ERRORSWEEP_DEFAULT_USER_ROLE", "Workspace Owner")
        with st.form("user_login"):
            email = st.text_input("User email", value=user_name if not user_pass else "")
            password = st.text_input("User password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            if user_pass and hmac.compare_digest(email.strip(), user_name.strip()) and hmac.compare_digest(password, user_pass):
                login_user(email, default_role, "workspace", secret("ERRORSWEEP_ORG_NAME", "Demo Workspace"))
                add_audit("Workspace user sign-in", email)
                st.rerun()
            elif not user_pass:
                st.warning("Workspace password is not configured. Use Demo access while building.")
            else:
                st.error("Invalid workspace credentials.")

    with tabs[2]:
        st.markdown("### Demo Access")
        demo_role = st.selectbox(
            "Preview as",
            ["Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager", "Translator", "Reviewer", "Client Viewer", "Billing Admin", "User"],
        )
        if st.button("Enter demo workspace", use_container_width=True):
            account_type = "owner" if demo_role == "Platform Owner" else "workspace"
            login_user(f"{demo_role.lower().replace(' ', '_')}@errorsweep.local", demo_role, account_type, "Demo Workspace")
            add_audit("Demo login", demo_role)
            st.rerun()


# ==========================================================
# Pages
# ==========================================================

def page_dashboard() -> None:
    hero("Dashboard", "Localization operations hub", "Manage projects, jobs, review tasks, scorecards, and translation memory from one workspace.")
    metrics([
        ("Projects", len(st.session_state.projects), "client/product workspaces"),
        ("Jobs", len(st.session_state.jobs), "QA / Pro / Review"),
        ("TM Entries", len(st.session_state.tm), "approved translations"),
        ("Pending Review", sum(1 for r in st.session_state.review_segments if r.get("status") not in ("Approved", "Rejected")), "segments"),
    ])
    st.markdown("### Recommended next steps")
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.markdown("### 📁 Create a project")
        st.caption("Set source/target languages, domain, and reusable rules.")
    with c2.container(border=True):
        st.markdown("### 🚀 Run QA or Pro")
        st.caption("Upload bilingual files or source files and route outputs to review.")
    with c3.container(border=True):
        st.markdown("### 🎬 Subtitle / Transcription")
        st.caption("Create subtitles, transcripts, and timing rows in a focused editor.")

    st.markdown("### Recent jobs")
    if st.session_state.jobs:
        st.dataframe(pd.DataFrame(st.session_state.jobs), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet.")


def page_projects() -> None:
    hero("Projects", "Client and product workspaces", "Create language projects, attach rule packs, and keep memory scoped correctly.")
    with st.form("create_project"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Project name")
        client = c2.text_input("Client / workspace", value=(current_user() or {}).get("workspace", "Demo Workspace"))
        c3, c4 = st.columns(2)
        source_lang = c3.selectbox("Source language", ["English", "French", "Spanish", "German", "Hindi", "Telugu", "Tamil"])
        target_langs = c4.multiselect("Target languages", ["French", "Spanish", "German", "Italian", "Portuguese", "Telugu", "Hindi", "Tamil", "Malayalam"], default=["French"])
        domain = st.selectbox("Default domain", ["Auto-detect", "Software UI", "Marketing", "Legal", "Medical", "E-learning", "Subtitling", "Gaming", "Finance", "General"])
        submitted = st.form_submit_button("Create project", use_container_width=True)
    if submitted and name:
        st.session_state.projects.append({
            "created": now_stamp(),
            "project": name,
            "client": client,
            "source": source_lang,
            "targets": ", ".join(target_langs),
            "domain": domain,
            "status": "Active",
        })
        add_audit("Project created", name)
        st.success("Project created.")

    if st.session_state.projects:
        st.dataframe(pd.DataFrame(st.session_state.projects), use_container_width=True, hide_index=True)
    else:
        st.info("No projects yet.")


def page_jobs() -> None:
    hero("Jobs", "Workflow queue", "Track uploads, translation, QA, Pro post-editing, scorecards, and delivery status.")
    if st.session_state.jobs:
        st.dataframe(pd.DataFrame(st.session_state.jobs), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet.")
    st.markdown("### Create manual job")
    with st.form("manual_job"):
        c1, c2, c3 = st.columns(3)
        job_type = c1.selectbox("Job type", ["QA", "Pro Translation", "Post-editing Review", "Subtitle Review", "Transcription", "Scorecard"])
        language = c2.text_input("Target language", value="French")
        assignee = c3.text_input("Assignee", value="reviewer@errorsweep.local")
        note = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Create job", use_container_width=True)
    if submitted:
        st.session_state.jobs.insert(0, {
            "created": now_stamp(),
            "type": job_type,
            "language": language,
            "assignee": assignee,
            "status": "Draft",
            "note": note,
        })
        add_audit("Manual job created", job_type)
        st.success("Job created.")


def page_qa() -> None:
    hero("ErrorSweep QA", "Review existing translation", "Upload bilingual files, detect issues, and create review-ready findings.")
    file = st.file_uploader("Upload bilingual file", type=["xlsx", "csv", "docx", "txt", "srt", "vtt"], key="qa_file")
    rules = st.file_uploader("Upload rules ZIP (optional)", type=["zip"], key="qa_rules")
    c1, c2 = st.columns(2)
    strictness = c1.selectbox("Strictness", ["Lenient", "Standard", "Strict", "Very Strict"], index=2)
    domain = c2.selectbox("Domain", ["Auto-detect", "Software UI", "Marketing", "Legal", "Medical", "E-learning", "Subtitling", "General"])

    if st.button("Run QA", use_container_width=True, disabled=file is None):
        rows = extract_rows_from_upload(file)
        findings = []
        for r in rows:
            src = r.get("source", "")
            tgt = r.get("target", "")
            status = "Pass"
            issues = []
            if not tgt:
                issues.append("Blank target")
            for ph in re.findall(r"\{\{[^}]+\}\}", src):
                if ph not in tgt:
                    issues.append(f"Missing placeholder {ph}")
            if src and tgt and src == tgt:
                issues.append("Source copied")
            if issues:
                status = "Needs Review"
            findings.append({**r, "status": status, "issues": "; ".join(issues), "match": r.get("match") or ("MT" if tgt else "Untranslated")})

        st.session_state.jobs.insert(0, {"created": now_stamp(), "type": "QA", "language": "", "status": "Completed", "segments": len(findings)})
        add_audit("QA run", f"{len(findings)} segments")
        st.success("QA completed. Download the QA report below. Post-editing Human Review is available after Pro translation runs only.")
        st.dataframe(pd.DataFrame(findings), use_container_width=True, hide_index=True)
        st.download_button("Download QA CSV", rows_to_csv(findings), file_name="errorsweep_qa_findings.csv", mime="text/csv", use_container_width=True)


def page_pro() -> None:
    hero("ErrorSweep Pro", "Translate + QA + Human Review", "Translate first, then open a dedicated Human Review workspace for editing and approval.")
    st.caption(f"AI access: {current_ai_route_label()}")

    # If a Pro review session already exists, keep the action visible even after reruns.
    # This prevents the user from losing access to the post-editing workspace.
    if st.session_state.get("review_segments") or st.session_state.get("last_pro_review_segments"):
        restore_human_review_session_from_cache()
        st.success("A Pro Human Review session is ready.")
        if st.button("Open Human Review workspace", type="primary", use_container_width=True, key="open_existing_pro_review"):
            go_to_human_review_workspace()
    uploaded = st.file_uploader("Upload source or bilingual file", type=["xlsx", "csv", "docx", "txt", "srt", "vtt"], key="pro_file")
    rules_zip = st.file_uploader("Upload rules ZIP (optional)", type=["zip"], key="pro_rules")
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    target_language = c1.text_input("Target language", value="French")
    domain_choice = c2.selectbox("Domain", ["Auto-detect", "Software UI", "Marketing", "Legal", "Medical", "E-learning", "Subtitling", "Gaming", "Finance", "General"])
    threshold = c3.slider("Allow with review threshold", min_value=0, max_value=25, value=12, help="Incomplete rows below this percentage can be routed to Human Review.")

    if st.button("Run Translate + Review", use_container_width=True, disabled=uploaded is None):
        rows = extract_rows_from_upload(uploaded)
        if not rows:
            st.error("No segments found.")
            return
        sample = " ".join([r.get("source", "") for r in rows[:20]])
        domain = auto_detect_domain(sample) if domain_choice == "Auto-detect" else domain_choice
        st.info(f"Detected domain: {domain}")

        source_texts = [r.get("source", "") or r.get("target", "") for r in rows]
        with st.spinner("Translating with available AI route..."):
            translations = call_main_api_translate(source_texts, target_language, domain)

        review_rows = []
        missing = 0
        for r, trans in zip(rows, translations):
            r["target"] = trans
            r["status"] = "MT"
            r["match"] = "MT"
            if not trans or trans.strip() == r.get("source", "").strip():
                missing += 1
                r["status"] = "Needs Review"
                r["match"] = "Untranslated"
            review_rows.append(r)

        missing_rate = missing / max(len(review_rows), 1)
        # IMPORTANT: seed the dedicated Human Review workspace BEFORE any button click.
        # Without this, the Human Review page can open with no rows and look blank.
        prepare_human_review_session(
            review_rows,
            source="ErrorSweep Pro",
            target_language=target_language,
            file_name=getattr(uploaded, "name", "uploaded_file"),
        )
        status = "Completed" if missing == 0 else ("Needs Human Review" if missing_rate <= threshold / 100 else "Blocked")
        st.session_state.jobs.insert(0, {
            "created": now_stamp(),
            "type": "Pro Translation",
            "language": target_language,
            "status": status,
            "segments": len(review_rows),
            "missing": missing,
        })
        add_audit("Pro translation run", f"{target_language}: {status}")

        if status == "Blocked":
            st.error(f"Translation incomplete: {missing}/{len(review_rows)} rows need review. Output blocked, but segments are available in Human Review.")
        elif status == "Needs Human Review":
            st.warning(f"Translation mostly completed. {missing}/{len(review_rows)} rows need Human Review.")
        else:
            st.success("Translation completed. Review is ready for approval.")

        st.dataframe(pd.DataFrame(review_rows), use_container_width=True, hide_index=True)

        # v41: External editor launcher. The CAT editor opens in a new browser tab
        # by job_id, so it feels like a professional editor window instead of a
        # normal Streamlit dashboard page.
        st.markdown("### Next step")
        cta1, cta2 = st.columns([1, 1])
        with cta1:
            review_job_id = st.session_state.get("active_review_session_id") or query_get("review_id")
            if review_job_id:
                render_external_editor_link("Open Human Review Editor", "cat", str(review_job_id))
            else:
                st.error("Review job was not created. Please rerun Pro translation.")
        with cta2:
            st.download_button("Download draft CSV", rows_to_csv(review_rows), "errorsweep_pro_draft_review_rows.csv", "text/csv", use_container_width=True)
        st.info("Human Review now opens in a separate full-window CAT editor. Target editing happens directly in the main grid; the right panel is only for TM, glossary, DNT, QA, issues, and history.")


# Pro post-editing and Subtitle/Transcription editors
# ==========================================================

def render_assist_panel(source: str) -> None:
    matches = compute_matches(source)
    st.markdown("#### Assist panel")
    st.markdown("##### TM matches")
    if matches["tm"]:
        for m in matches["tm"]:
            st.markdown(f'<div class="es-row-card"><span class="es-chip green">{escape(m["type"])}</span><br><b>{escape(m["source"])}</b><br><span class="es-small">{escape(m["target"])}</span></div>', unsafe_allow_html=True)
    else:
        st.caption("No TM match.")

    st.markdown("##### Glossary")
    if matches["glossary"]:
        for g in matches["glossary"]:
            st.markdown(f'<div class="es-row-card"><b>{escape(g.get("source",""))}</b> → {escape(g.get("target",""))}<br><span class="es-small">{escape(g.get("notes",""))}</span></div>', unsafe_allow_html=True)
    else:
        st.caption("No glossary hits.")

    st.markdown("##### DNT")
    if matches["dnt"]:
        for d in matches["dnt"]:
            st.markdown(f'<span class="es-chip amber">{escape(d["term"])}</span> ', unsafe_allow_html=True)
    else:
        st.caption("No DNT hits.")


def render_text_review_editor() -> None:
    """Full-width CAT-style Pro post-editing workspace.

    This version is intentionally closer to CAT tools such as Phrase/Memsource:
    a compact job bar, filter row, spreadsheet-like source/target grid, match
    score/status columns, and a right CAT panel. It opens as a dedicated page
    without the normal platform navigation so the grid can use the full screen.
    """
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 100vw !important;
            padding: .45rem .75rem .65rem .75rem !important;
        }
        .es-cat-app-shell {
            min-height: calc(100vh - 16px);
            background: rgba(8, 10, 19, .98);
            border: 1px solid rgba(84,105,180,.20);
            border-radius: 16px;
            overflow: hidden;
        }
        .es-cat-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            padding: 10px 14px;
            background: #24252b;
            border-bottom: 1px solid rgba(255,255,255,.09);
        }
        .es-cat-brandline {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
            color: #fff;
            font-weight: 800;
            font-size: 15px;
        }
        .es-cat-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 900;
            border: 1px solid rgba(255,255,255,.15);
            background: rgba(255,255,255,.06);
            color: #eaf2ff;
            white-space: nowrap;
        }
        .es-cat-pill.green { background: rgba(0,217,133,.13); border-color: rgba(0,217,133,.32); color: #66ffc4; }
        .es-cat-pill.amber { background: rgba(245,158,11,.12); border-color: rgba(245,158,11,.35); color: #ffd38a; }
        .es-cat-toolbar2 {
            display: flex;
            gap: 10px;
            align-items: center;
            padding: 7px 14px;
            background: #1f2026;
            border-bottom: 1px solid rgba(255,255,255,.08);
            color: rgba(255,255,255,.72);
            font-size: 14px;
        }
        .es-cat-tool-icon {
            width: 28px; height: 28px; border-radius: 7px;
            display: inline-flex; align-items: center; justify-content: center;
            background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.06);
        }
        .es-cat-metrics {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            padding: 10px 14px 6px 14px;
            background: #0b0d17;
        }
        .es-cat-metric {
            background: rgba(18,21,38,.76);
            border: 1px solid rgba(84,105,180,.20);
            border-radius: 10px;
            padding: 8px 10px;
        }
        .es-cat-metric-label { font-family: Space Mono, monospace; color: #9aa7da; font-size: 10px; text-transform: uppercase; }
        .es-cat-metric-value { color:#fff; font-size:20px; font-weight:900; line-height: 1.1; }
        .es-cat-filterbar {
            display: grid;
            grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) 180px 120px;
            gap: 10px;
            padding: 8px 14px 10px 14px;
            background: #0b0d17;
            border-bottom: 1px solid rgba(255,255,255,.08);
        }
        .es-cat-grid-title {
            display: grid;
            grid-template-columns: 56px minmax(270px, 1fr) minmax(270px, 1fr) 74px 90px 90px;
            gap: 0;
            padding: 7px 12px;
            background: #161820;
            border: 1px solid rgba(255,255,255,.08);
            border-bottom: none;
            border-radius: 12px 12px 0 0;
            font-family: Space Mono, monospace;
            color: #aeb8dc;
            text-transform: uppercase;
            font-size: 10px;
            font-weight: 700;
        }
        .es-cat-grid-card {
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 0 0 12px 12px;
            overflow: hidden;
            background: #10121b;
        }
        .es-cat-side-card {
            border: 1px solid rgba(255,255,255,.10);
            background: #151721;
            border-radius: 12px;
            padding: 10px;
            height: 735px;
            overflow-y: auto;
        }
        .es-cat-seg-preview {
            background: #0e1018;
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .es-cat-assist-title {
            font-size: 13px;
            font-weight: 900;
            color: #fff;
            margin: 12px 0 5px 0;
        }
        .es-cat-assist-empty { color:#8d95bb; font-size:12px; }
        .es-cat-mini-row {
            border-bottom: 1px solid rgba(255,255,255,.06);
            padding: 7px 0;
            color: #dbe6ff;
            font-size: 12px;
        }
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border-radius: 0 !important;
            border: none !important;
        }
        div[data-testid="stDataEditor"] [role="grid"] {
            font-size: 13px !important;
        }
        div[data-testid="stDataEditor"] textarea,
        div[data-testid="stDataEditor"] input {
            font-size: 13px !important;
        }
        @media (max-width: 1100px) {
            .es-cat-filterbar { grid-template-columns: 1fr; }
            .es-cat-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    rows = st.session_state.get("review_segments", []) or []
    if not rows:
        st.info("No Pro translated rows are loaded. Run ErrorSweep Pro first, then click Open Human Review workspace.")
        return

    completion = compute_review_completion(rows)
    file_name = safe_text(st.session_state.get("review_workspace_file_name", "Current file")) or "Current file"
    language = safe_text(st.session_state.get("review_workspace_language", "Target")) or "Target"
    title = safe_text(st.session_state.get("review_workspace_title", "Pro Human Review")) or "Pro Human Review"

    # Top job bar like a CAT tool.
    st.markdown(
        f"""
        <div class="es-cat-app-shell">
          <div class="es-cat-topbar">
            <div class="es-cat-brandline">
              <span style="font-size:18px;">▣</span>
              <span>ErrorSweep CAT</span>
              <span style="color:#9aa0b9; font-weight:600;">/ {escape(title)} / {escape(file_name)} / {escape(language)}</span>
            </div>
            <div style="display:flex; gap:8px; align-items:center;">
              <span class="es-cat-pill green">Accepted</span>
              <span class="es-cat-pill">TM</span>
              <span class="es-cat-pill">TB</span>
              <span class="es-cat-pill amber">MT</span>
            </div>
          </div>
          <div class="es-cat-toolbar2">
            <span class="es-cat-tool-icon">B</span><span class="es-cat-tool-icon"><i>I</i></span><span class="es-cat-tool-icon">U</span>
            <span class="es-cat-tool-icon">⌘</span><span class="es-cat-tool-icon">✓</span><span class="es-cat-tool-icon">↶</span><span class="es-cat-tool-icon">↷</span>
            <span style="margin-left:auto; color:#8ea1dc; font-size:12px;">Post-editing workspace · source left · target right</span>
          </div>
          <div class="es-cat-metrics">
            <div class="es-cat-metric"><div class="es-cat-metric-label">Confirmed</div><div class="es-cat-metric-value">{completion['approved']}</div></div>
            <div class="es-cat-metric"><div class="es-cat-metric-label">Segments</div><div class="es-cat-metric-value">{completion['total']}</div></div>
            <div class="es-cat-metric"><div class="es-cat-metric-label">Translated</div><div class="es-cat-metric-value">{completion['translated']}</div></div>
            <div class="es-cat-metric"><div class="es-cat-metric-label">Needs Review</div><div class="es-cat-metric-value">{completion['needs_review']}</div></div>
          </div>
        """,
        unsafe_allow_html=True,
    )

    # Filter controls need Streamlit widgets, so they sit visually inside the shell.
    with st.container():
        f1, f2, f3, f4 = st.columns([1.25, 1.25, .7, .55])
        with f1:
            source_filter = st.text_input("Filter source", value="", placeholder="Filter source (en)", key="cat_v40_source_filter", label_visibility="collapsed")
        with f2:
            target_filter = st.text_input("Filter target", value="", placeholder="Filter target", key="cat_v40_target_filter", label_visibility="collapsed")
        with f3:
            status_options = ["All"] + sorted({safe_text(r.get("status", "Untranslated")) or "Untranslated" for r in rows})
            status_filter = st.selectbox("Status", status_options, key="cat_v40_status_filter", label_visibility="collapsed")
        with f4:
            pending_only = st.checkbox("Pending", value=False, key="cat_v40_pending_only")

    filtered_indexes: List[int] = []
    for i, r in enumerate(rows):
        src = safe_text(r.get("source", ""))
        tgt = safe_text(r.get("target", ""))
        status = safe_text(r.get("status", "Untranslated")) or "Untranslated"
        if source_filter and source_filter.lower() not in src.lower():
            continue
        if target_filter and target_filter.lower() not in tgt.lower():
            continue
        if status_filter != "All" and status != status_filter:
            continue
        if pending_only and status in {"Approved", "101%", "100%"}:
            continue
        filtered_indexes.append(i)

    if not filtered_indexes:
        st.warning("No segments match the current filters.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    current_idx = int(st.session_state.get("selected_review_index", filtered_indexes[0]) or filtered_indexes[0])
    if current_idx not in filtered_indexes:
        current_idx = filtered_indexes[0]
        st.session_state.selected_review_index = current_idx

    # Build the editable grid. Source and target appear side-by-side like Excel/CAT.
    grid_rows = []
    for i in filtered_indexes:
        r = rows[i]
        status = safe_text(r.get("status", "MT" if safe_text(r.get("target", "")) else "Needs Review"))
        match = safe_text(r.get("match", "MT" if safe_text(r.get("target", "")) else "Untranslated"))
        # Score column emulates Phrase/Memsource match percentage badges.
        if match in {"100%", "101%"}:
            score = match
        elif "Fuzzy" in match:
            score = match.replace("Fuzzy", "").strip() or "85%"
        elif status in {"Approved", "100%", "101%"}:
            score = "100"
        elif match == "MT":
            score = "MT"
        elif match == "Untranslated":
            score = "-"
        else:
            score = match or "MT"
        grid_rows.append({
            "No": i + 1,
            "Source": safe_text(r.get("source", "")),
            "Target": safe_text(r.get("target", "")),
            "Score": score,
            "Status": status,
            "QA": "✓" if status in {"Approved", "100%", "101%"} else "◯",
            "Notes": safe_text(r.get("notes", "")),
            "Location": safe_text(r.get("location", f"Segment {i+1}")),
        })

    main_col, side_col = st.columns([4.25, 1.15], gap="small")
    with main_col:
        st.markdown(
            '<div class="es-cat-grid-title"><div>No</div><div>Source</div><div>Target</div><div>Score</div><div>Status</div><div>QA</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="es-cat-grid-card">', unsafe_allow_html=True)
        edited_df = st.data_editor(
            pd.DataFrame(grid_rows),
            use_container_width=True,
            hide_index=True,
            height=700,
            num_rows="fixed",
            column_order=["No", "Source", "Target", "Score", "Status", "QA", "Notes", "Location"],
            disabled=["No", "Source", "Score", "QA", "Location"],
            column_config={
                "No": st.column_config.NumberColumn("", width="small"),
                "Source": st.column_config.TextColumn("Source", width="large", help="Read-only source segment"),
                "Target": st.column_config.TextColumn("Target", width="large", help="Editable reviewed translation"),
                "Score": st.column_config.TextColumn("", width="small"),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    width="medium",
                    options=["MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"],
                ),
                "QA": st.column_config.TextColumn("", width="small"),
                "Notes": st.column_config.TextColumn("Notes", width="medium"),
                "Location": st.column_config.TextColumn("Location", width="medium"),
            },
            key="cat_v40_excel_grid",
        )
        st.markdown('</div>', unsafe_allow_html=True)

        b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 1])
        if b1.button("Save edits", type="primary", use_container_width=True):
            for _, erow in edited_df.iterrows():
                idx = int(erow["No"]) - 1
                if 0 <= idx < len(rows):
                    rows[idx]["target"] = safe_text(erow.get("Target", ""))
                    rows[idx]["status"] = safe_text(erow.get("Status", "")) or "Needs Review"
                    rows[idx]["notes"] = safe_text(erow.get("Notes", ""))
            st.session_state.review_segments = rows
            st.session_state.last_pro_review_segments = rows
            st.session_state.latest_human_review_segments = rows
            st.toast("Saved grid edits.")
            st.rerun()

        if b2.button("Approve visible", use_container_width=True):
            for _, erow in edited_df.iterrows():
                idx = int(erow["No"]) - 1
                if 0 <= idx < len(rows) and safe_text(erow.get("Target", "")).strip():
                    rows[idx]["target"] = safe_text(erow.get("Target", ""))
                    rows[idx]["status"] = "Approved"
                    rows[idx]["notes"] = safe_text(erow.get("Notes", ""))
            st.session_state.review_segments = rows
            st.toast("Visible translated rows approved.")
            st.rerun()

        if b3.button("Next pending", use_container_width=True):
            next_idx = None
            for i, r in enumerate(rows):
                if safe_text(r.get("status", "")) not in {"Approved", "101%", "100%"} or not safe_text(r.get("target", "")).strip():
                    next_idx = i
                    break
            if next_idx is not None:
                st.session_state.selected_review_index = next_idx
                st.rerun()
            else:
                st.success("All rows look complete.")

        if b4.button("Save to TM", use_container_width=True):
            saved = 0
            for r in rows:
                src = safe_text(r.get("source", ""))
                tgt = safe_text(r.get("target", ""))
                if src and tgt and safe_text(r.get("status", "")) in {"Approved", "100%", "101%"}:
                    st.session_state.tm.append({
                        "source": src,
                        "target": tgt,
                        "language": safe_text(st.session_state.get("review_workspace_language", "")),
                        "created": now_stamp(),
                        "approved_by": (current_user() or {}).get("email", ""),
                    })
                    saved += 1
            st.success(f"Saved {saved} approved segment(s) to TM.")

        if b5.button("Back to Pro", use_container_width=True):
            open_page("ErrorSweep Pro")

        reviewed_base_name = safe_text(st.session_state.get("review_workspace_file_name", "human_review_output")) or "human_review_output"
        reviewed_base_name = re.sub(r"\.[^.]+$", "", reviewed_base_name)
        dl1, dl2, dl3 = st.columns(3)
        dl1.download_button(
            "Download reviewed Excel",
            build_reviewed_translation_workbook(rows),
            file_name=f"{reviewed_base_name}_reviewed_translation.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        dl2.download_button(
            "Download reviewed CSV",
            rows_to_csv(rows),
            file_name=f"{reviewed_base_name}_reviewed_translation.csv",
            mime="text/csv",
            use_container_width=True,
        )
        dl3.download_button(
            "Download target text",
            build_reviewed_plain_text(rows),
            file_name=f"{reviewed_base_name}_target_text.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with side_col:
        st.markdown('<div class="es-cat-side-card">', unsafe_allow_html=True)
        select_labels = [f"{i+1} · {safe_text(rows[i].get('source',''))[:42] or safe_text(rows[i].get('target',''))[:42]}" for i in filtered_indexes]
        selected_label = st.selectbox(
            "CAT",
            select_labels,
            index=filtered_indexes.index(current_idx) if current_idx in filtered_indexes else 0,
            key="cat_v40_focus_select",
            label_visibility="collapsed",
        )
        selected_idx = filtered_indexes[select_labels.index(selected_label)]
        st.session_state.selected_review_index = selected_idx
        focused = rows[selected_idx]
        status = safe_text(focused.get("status", "Needs Review"))
        match = safe_text(focused.get("match", "MT"))
        chip_class = "green" if status in {"Approved", "100%", "101%"} else "amber" if "Review" in status or status in {"MT", "Untranslated", "Needs Rework"} else "red"
        st.markdown(
            f"""
            <div class="es-cat-seg-preview">
              <div style="display:flex; justify-content:space-between; gap:8px; align-items:center;">
                <div class="es-small">Segment {selected_idx + 1} / {len(rows)}</div>
                <div><span class="es-cat-pill {chip_class}">{escape(status)}</span></div>
              </div>
              <div style="margin-top:8px;"><span class="es-cat-pill">{escape(match)}</span></div>
              <div class="es-small" style="margin-top:8px;">{escape(safe_text(focused.get('location','')))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="es-cat-assist-title">Source</div>', unsafe_allow_html=True)
        st.text_area("Source preview", value=safe_text(focused.get("source", "")), height=105, disabled=True, label_visibility="collapsed", key=f"v40_src_{selected_idx}")
        st.markdown('<div class="es-cat-assist-title">Target</div>', unsafe_allow_html=True)
        focused_target = st.text_area("Target preview", value=safe_text(focused.get("target", "")), height=135, label_visibility="collapsed", key=f"v40_tgt_{selected_idx}")
        focused_status = st.selectbox(
            "Status",
            ["MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"],
            index=["MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"].index(status) if status in ["MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"] else 5,
            key=f"v40_status_{selected_idx}",
        )
        c1, c2 = st.columns(2)
        if c1.button("Save", key=f"v40_save_{selected_idx}", use_container_width=True):
            rows[selected_idx]["target"] = focused_target
            rows[selected_idx]["status"] = focused_status
            st.session_state.review_segments = rows
            st.toast("Saved selected segment.")
            st.rerun()
        if c2.button("Approve", key=f"v40_approve_{selected_idx}", use_container_width=True):
            rows[selected_idx]["target"] = focused_target
            rows[selected_idx]["status"] = "Approved"
            st.session_state.review_segments = rows
            st.toast("Approved selected segment.")
            st.rerun()

        st.markdown('<div class="es-cat-assist-title">TM matches</div>', unsafe_allow_html=True)
        matches = compute_matches(safe_text(focused.get("source", "")))
        if matches["tm"]:
            for m in matches["tm"][:7]:
                st.markdown(f'<div class="es-cat-mini-row"><b>{escape(m.get("type","TM"))}</b> · {escape(m.get("source",""))}<br><span class="es-small">{escape(m.get("target",""))}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="es-cat-assist-empty">No TM match.</div>', unsafe_allow_html=True)

        st.markdown('<div class="es-cat-assist-title">Glossary</div>', unsafe_allow_html=True)
        if matches["glossary"]:
            for g in matches["glossary"][:8]:
                st.markdown(f'<div class="es-cat-mini-row"><b>{escape(g.get("source",""))}</b> → {escape(g.get("target",""))}<br><span class="es-small">{escape(g.get("notes",""))}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="es-cat-assist-empty">No glossary hits.</div>', unsafe_allow_html=True)

        st.markdown('<div class="es-cat-assist-title">DNT</div>', unsafe_allow_html=True)
        if matches["dnt"]:
            for d in matches["dnt"][:12]:
                st.markdown(f'<span class="es-cat-pill amber">{escape(d.get("term",""))}</span> ', unsafe_allow_html=True)
        else:
            st.markdown('<div class="es-cat-assist-empty">No DNT hits.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def default_subtitle_segments(count: int = 8, transcription: bool = False) -> List[Dict[str, Any]]:
    rows = []
    for i in range(count):
        rows.append({
            "id": i + 1,
            "start": round(i * 4.0, 3),
            "end": round(i * 4.0 + 3.5, 3),
            "source": "" if transcription else f"Source segment {i+1}",
            "target": "",
            "status": "Draft" if transcription else "Untranslated",
            "match": "",
        })
    return rows


def enter_subtitle_workspace(workflow: str, rows: List[Dict[str, Any]], video_file=None) -> None:
    """Open the dedicated subtitle/transcription workspace."""
    st.session_state.subtitle_workflow = workflow
    st.session_state.subtitle_segments = rows
    st.session_state.selected_subtitle_index = 0
    st.session_state.subtitle_editor_active = True
    if video_file is not None:
        st.session_state.subtitle_video_bytes = video_file.getvalue()
        st.session_state.subtitle_video_name = getattr(video_file, "name", "uploaded_video")
        st.session_state.subtitle_video_type = getattr(video_file, "type", "video/mp4") or "video/mp4"
    add_audit(f"{workflow} workspace opened", f"{len(rows)} rows")


def render_subtitle_transcription_setup() -> None:
    st.markdown("### Subtitle / Transcription Editor")
    st.caption("Create a dedicated editor workspace. Subtitling can use a source script. Transcription auto-generation is available only when the user provides an API key.")

    workflow = st.radio("Editor workflow", ["Subtitling", "Transcription"], horizontal=True, key="subtitle_workflow_picker")
    video = st.file_uploader("Upload video/audio", type=["mp4", "mov", "m4v", "webm", "mp3", "wav", "m4a"], key="subtitle_video_setup")
    user_key_available = bool(str(st.session_state.get("byo_openai_api_key", "") or "").strip())

    if video:
        preview_col, info_col = st.columns([0.45, 0.55], gap="large")
        with preview_col:
            st.video(video.getvalue())
        with info_col:
            st.success("Video/audio loaded.")
            st.caption("The editor will open as a dedicated workspace page, separate from this setup screen.")
            if user_key_available:
                st.caption("Transcription route: user API key available.")
            else:
                st.caption("Transcription route: manual editing. No API key is available for speech-to-text.")
    else:
        st.info("Upload a video/audio file to begin.")

    if workflow == "Subtitling":
        source_file = st.file_uploader(
            "Upload English source subtitle/script (optional for subtitling)",
            type=["srt", "vtt", "txt", "csv", "xlsx", "docx"],
            key="subtitle_source_setup",
        )
        target_file = st.file_uploader(
            "Upload existing target subtitle file (optional)",
            type=["srt", "vtt", "txt", "csv", "xlsx", "docx"],
            key="subtitle_target_setup",
        )
        c1, c2, c3 = st.columns([1, 1, 1])
        subtitle_target_language = c1.text_input("Target subtitle language", value=st.session_state.get("subtitle_target_language", "French"), key="subtitle_target_lang_setup")
        speech_locale = c2.text_input("Source speech locale", value="en-US", help="Used only if no source file is uploaded and a user API key is available for transcription.")
        starter_rows = c3.number_input("Starter rows", min_value=1, max_value=200, value=10, key="subtitle_starter_rows")
        auto_generate = st.checkbox(
            "Generate draft target subtitles",
            value=True,
            help="If source rows exist, target subtitles use BYO API key or built-in Azure/NLLB translation. If no source file is uploaded, speech-to-text requires a user API key; otherwise blank rows are created for manual editing.",
        )

        if st.button("Create subtitling workspace", use_container_width=True, disabled=video is None):
            st.session_state.subtitle_target_language = subtitle_target_language
            if source_file:
                rows = extract_rows_from_upload(source_file)
                for i, r in enumerate(rows):
                    r.setdefault("start", i * 4.0)
                    r.setdefault("end", i * 4.0 + 3.5)
                    r.setdefault("target", "")
                    r.setdefault("status", "Untranslated")
                    r.setdefault("match", "")
            else:
                if user_key_available:
                    with st.spinner("No source file uploaded. Transcribing source from video/audio using user API key..."):
                        transcript_rows, usage = generate_transcription_rows_from_video(video, locale=speech_locale)
                    rows = []
                    for i, tr in enumerate(transcript_rows):
                        rows.append({
                            "id": i + 1,
                            "start": tr.get("start", i * 3.5),
                            "end": tr.get("end", i * 3.5 + 3.0),
                            "source": tr.get("target", ""),
                            "target": "",
                            "status": "Transcribed Source" if tr.get("target") else "Untranslated",
                            "match": tr.get("match", "STT"),
                        })
                    if usage.get("error") and not usage.get("success"):
                        st.warning(f"Speech transcription was not available: {usage.get('error')}. Blank rows were created for manual subtitling.")
                else:
                    rows = default_subtitle_segments(int(starter_rows), transcription=False)
                    for r in rows:
                        r["source"] = ""
                        r["target"] = ""
                        r["status"] = "Draft"
                        r["match"] = "Manual"
                    st.info("No source file and no user API key were provided. Blank subtitle rows were created for manual source/target editing.")

            if target_file:
                target_rows = extract_rows_from_upload(target_file)
                for i, tr in enumerate(target_rows):
                    if i < len(rows):
                        rows[i]["target"] = tr.get("target") or tr.get("source") or ""
                        rows[i]["status"] = "Existing" if rows[i]["target"] else rows[i].get("status", "Untranslated")

            has_source_text = any(safe_text(r.get("source", "")) for r in rows)
            if auto_generate and rows and has_source_text:
                with st.spinner("Generating target subtitle draft..."):
                    rows, missing = translate_subtitle_sources(rows, subtitle_target_language, domain="Subtitling")
                if missing:
                    st.warning(f"Draft subtitles generated with {missing} untranslated row(s).")
                else:
                    st.success("Draft subtitles generated.")
            elif auto_generate and rows and not has_source_text:
                st.info("Draft target subtitles were skipped because there is no source text yet. Fill source rows manually, then translate/review later.")

            enter_subtitle_workspace("Subtitling", rows, video)
            open_page("Subtitle Workspace")
    else:
        st.caption("Transcription mode does not need a source file. Auto-transcription requires a user API key. Without a user key, blank transcript rows are created for human editing.")
        c1, c2 = st.columns([1, 1])
        speech_locale = c1.text_input("Speech locale", value="en-US", key="transcription_locale")
        starter_count = c2.number_input("Starter rows", min_value=1, max_value=200, value=10, key="transcription_starter_count")
        auto_transcribe = st.checkbox(
            "Auto-generate transcript using user API key",
            value=user_key_available,
            disabled=not user_key_available,
            help="Speech-to-text is available only when the user has added an API key in Account. Without a key, the editor opens with blank rows for manual transcription.",
        )
        if not user_key_available:
            st.info("No user API key found. The transcription workspace will open with blank rows for manual editing.")

        if st.button("Create transcription workspace", use_container_width=True, disabled=video is None):
            if auto_transcribe and user_key_available:
                with st.spinner("Creating transcript from video/audio using user API key..."):
                    rows, usage = generate_transcription_rows_from_video(video, locale=speech_locale)
                if usage.get("error") and not usage.get("success"):
                    st.warning(f"Auto-transcription was not available: {usage.get('error')}. Blank rows were created for manual transcription.")
                    rows = default_subtitle_segments(int(starter_count), transcription=True)
            else:
                rows = default_subtitle_segments(int(starter_count), transcription=True)
            if not rows:
                rows = default_subtitle_segments(int(starter_count), transcription=True)
            enter_subtitle_workspace("Transcription", rows, video)
            open_page("Transcription Workspace")

    if st.session_state.subtitle_segments:
        if st.button("Open existing subtitle/transcription workspace", use_container_width=True):
            st.session_state.subtitle_editor_active = True
            open_page("Subtitle Workspace" if st.session_state.get("subtitle_workflow") == "Subtitling" else "Transcription Workspace")


def render_focused_subtitle_workspace() -> None:
    workflow = st.session_state.get("subtitle_workflow", "Transcription")
    rows = st.session_state.subtitle_segments
    if not rows:
        st.session_state.subtitle_editor_active = False
        st.info("No editor rows available. Create a subtitle or transcription workspace first.")
        return

    top1, top2 = st.columns([0.78, 0.22])
    with top1:
        st.markdown(f"### {workflow} workspace")
        st.caption("Compact video on top, script writing in the middle, timing/text grid collapsed at the bottom.")
    with top2:
        if st.button("Back to setup", use_container_width=True):
            st.session_state.subtitle_editor_active = False
            open_page("Subtitle / Transcription Editor")

    video_bytes = st.session_state.get("subtitle_video_bytes")
    video_col, meta_col = st.columns([0.50, 0.50], gap="large")
    with video_col:
        if video_bytes:
            st.video(video_bytes)
        else:
            st.warning("Video is not available in this session. Go back and upload it again.")
    with meta_col:
        st.markdown("#### Job notes")
        st.caption("Use the selected segment below to write transcript/subtitle text. Use the collapsed grid for detailed timing edits.")
        st.metric("Rows", len(rows))
        st.metric("Approved", sum(1 for r in rows if r.get("status") == "Approved"))

    idx = min(st.session_state.selected_subtitle_index, len(rows) - 1)
    row = rows[idx]

    list_col, editor_col, assist_col = st.columns([1.25, 2.25, 1.15], gap="large")

    with list_col:
        st.markdown("#### Segments")
        for i, seg in enumerate(rows):
            time_label = f"{format_time(seg.get('start',0))} → {format_time(seg.get('end',0))}"
            preview = seg.get("source") if workflow == "Subtitling" else seg.get("target")
            if not preview:
                preview = "Empty transcript row" if workflow == "Transcription" else "Empty subtitle row"
            status = seg.get("status", "Draft")
            st.caption(f"{i+1}. {time_label} · {status}")
            if st.button(preview[:80], key=f"focused_pick_{i}", use_container_width=True):
                st.session_state.selected_subtitle_index = i
                st.rerun()

    with editor_col:
        st.markdown(f"#### {workflow} segment {idx+1} / {len(rows)}")
        time_a, time_b = st.columns(2)
        start_val = time_a.number_input("Start", min_value=0.0, value=float(row.get("start", 0.0)), step=0.1, key=f"focus_start_{idx}")
        end_val = time_b.number_input("End", min_value=0.0, value=float(row.get("end", max(start_val + 2.0, 2.0))), step=0.1, key=f"focus_end_{idx}")
        rows[idx]["start"] = float(start_val)
        rows[idx]["end"] = float(max(end_val, start_val + 0.1))

        if workflow == "Subtitling":
            source_text = st.text_area("English source", value=row.get("source", ""), height=90, key=f"focus_source_{idx}")
            rows[idx]["source"] = source_text
            target_label = "Target subtitle"
        else:
            target_label = "Transcript text"

        target_text = st.text_area(target_label, value=row.get("target", ""), height=170, key=f"focus_target_{idx}")
        status = st.selectbox(
            "Status",
            ["Draft", "MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"],
            index=["Draft", "MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"].index(row.get("status", "Draft")) if row.get("status", "Draft") in ["Draft", "MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"] else 0,
            key=f"focus_status_{idx}",
        )

        b1, b2, b3, b4 = st.columns(4)
        if b1.button("Save", key=f"focus_save_{idx}", use_container_width=True):
            rows[idx]["target"] = target_text
            rows[idx]["status"] = status
            st.success("Saved.")
        if b2.button("Approve", key=f"focus_approve_{idx}", use_container_width=True):
            rows[idx]["target"] = target_text
            rows[idx]["status"] = "Approved"
            st.success("Approved.")
        if b3.button("Split", key=f"focus_split_{idx}", use_container_width=True):
            start = float(rows[idx]["start"])
            end = float(rows[idx]["end"])
            mid = round((start + end) / 2, 3)
            rows[idx]["end"] = mid
            rows.insert(idx + 1, {**rows[idx], "id": len(rows) + 1, "start": mid, "end": end, "source": "", "target": "", "status": "Draft"})
            st.rerun()
        if b4.button("Next", key=f"focus_next_{idx}", use_container_width=True):
            rows[idx]["target"] = target_text
            rows[idx]["status"] = status
            st.session_state.selected_subtitle_index = min(idx + 1, len(rows) - 1)
            st.rerun()

    with assist_col:
        render_assist_panel(row.get("source", "") or row.get("target", ""))

    # No duration scale: compact timing/text grid only, hidden by default.
    with st.expander("Timing and text grid", expanded=bool(st.session_state.get("show_timing_grid", False))):
        grid_cols = ["id", "start", "end", "source", "target", "status", "match"] if workflow == "Subtitling" else ["id", "start", "end", "target", "status"]
        edited = st.data_editor(
            pd.DataFrame(rows)[grid_cols],
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            height=230,
            key="focused_subtitle_grid",
        )
        c1, c2, c3 = st.columns(3)
        if c1.button("Save grid", use_container_width=True):
            st.session_state.subtitle_segments = edited.to_dict("records")
            st.success("Grid saved.")
        c2.download_button("Download CSV", rows_to_csv(st.session_state.subtitle_segments), "subtitle_transcription_editor.csv", "text/csv", use_container_width=True)
        c3.download_button("Download SRT", rows_to_srt(st.session_state.subtitle_segments, use_target=True), "subtitle_transcription_output.srt", "text/plain", use_container_width=True)


def render_subtitle_transcription_editor() -> None:
    if st.session_state.get("subtitle_editor_active"):
        render_focused_subtitle_workspace()
    else:
        render_subtitle_transcription_setup()


def page_subtitle_transcription_editor() -> None:
    # Public/manual editor page. This page is only for subtitle and transcription work.
    # Pro post-editing Human Review is opened only from ErrorSweep Pro via the hidden
    # Human Review Workspace route.
    if st.session_state.get("subtitle_editor_active"):
        render_focused_subtitle_workspace()
        return
    hero("Subtitle / Transcription Editor", "Dedicated media localization workspace", "Create subtitles or transcripts. Pro post-editing opens separately only after a Pro translation run.")
    render_subtitle_transcription_editor()

# Backward-compatible alias for old references.
def page_human_review() -> None:
    page_subtitle_transcription_editor()


def page_human_review_workspace() -> None:
    """Dedicated CAT-style post-editing route opened from ErrorSweep Pro outputs only."""
    restore_human_review_session_from_cache()
    # Recovery guard: if Streamlit opened this hidden route after a rerun, restore
    # the Pro rows from the persistent Pro result cache. This prevents blank pages.
    if not st.session_state.get("review_segments") and st.session_state.get("pro_post_edit_rows"):
        prepare_human_review_session(
            st.session_state.get("pro_post_edit_rows", []),
            source="ErrorSweep Pro",
            target_language=st.session_state.get("pro_post_edit_language", ""),
            file_name=st.session_state.get("pro_post_edit_file_name", ""),
        )

    if not st.session_state.get("review_segments"):
        st.markdown(
            """
            <style>.block-container{max-width:100vw!important;padding:1rem!important;}</style>
            """,
            unsafe_allow_html=True,
        )
        st.warning("No Pro post-editing rows are loaded yet. Run ErrorSweep Pro first, then click Open Human Review workspace.")
        if st.button("Go to ErrorSweep Pro", type="primary", use_container_width=True):
            open_page("ErrorSweep Pro")
        return

    render_text_review_editor()



def page_subtitle_workspace() -> None:
    st.session_state.subtitle_editor_active = True
    st.session_state.subtitle_workflow = "Subtitling"
    render_focused_subtitle_workspace()


def page_transcription_workspace() -> None:
    st.session_state.subtitle_editor_active = True
    st.session_state.subtitle_workflow = "Transcription"
    render_focused_subtitle_workspace()



# ==========================================================
# SCORECARD EXCEL OUTPUT
# ==========================================================

ERROR_CATEGORIES = ["Accuracy", "Readability", "Style and Tone", "Grammar", "Country Standards"]
ERROR_SEVERITIES = ["Minor", "Major", "Critical"]
SEVERITY_POINTS = {"Minor": 1, "Major": 5, "Critical": 10}

CATEGORY_DESCRIPTIONS = {
    "Accuracy": "Translation does not accurately reflect the source meaning; omission, addition, mistranslation, wrong sense, or placeholder-critical meaning issue.",
    "Readability": "The natural flow of the sentence is compromised; structure is awkward, hard to understand, over-literal, or poorly segmented.",
    "Style and Tone": "The tone, register, or product style is not preserved; wording does not match the client style guide or expected UI tone.",
    "Grammar": "Grammar, spelling, punctuation, capitalization, spacing, or syntax issue in the target language.",
    "Country Standards": "Locale/country standard issue such as date/time/number format, unit, untranslated UI term, address/currency convention, or inappropriate locale adaptation.",
}

SEVERITY_DESCRIPTIONS = {
    "Minor": "Minor impact on meaning/readability. Overall meaning is accurate and understandable. Examples: typo, punctuation, minor grammar/style issue.",
    "Major": "Major impact on meaning/readability. Translation may be confusing, misleading, incomplete, or noticeably wrong.",
    "Critical": "Critical issue that can cause serious misunderstanding, offensive output, legal/compliance risk, or unusable delivery.",
}


def count_words(text: str) -> int:
    return len(re.findall(r"[\w\u0900-\u097F\u0C00-\u0C7F\u0B80-\u0BFF\u0600-\u06FF]+", safe_text(text)))


def extract_scorecard_placeholders(text: str) -> List[str]:
    return re.findall(r"\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|<[^>]+>", safe_text(text))


def extract_scorecard_numbers(text: str) -> List[str]:
    return re.findall(r"\d+(?:[.,:]\d+)*", safe_text(text))


def normalized_compare_text(text: str) -> str:
    text = safe_text(text).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def scorecard_category_and_severity(source: str, translator: str, reviewer: str) -> Tuple[str, str, int, str]:
    """Heuristic categorization for translator-vs-reviewer scorecards.

    The user can edit the generated categories/severities inside the Excel output.
    This provides a practical first pass from reviewer changes.
    """
    src = safe_text(source)
    tr = safe_text(translator)
    rv = safe_text(reviewer)

    if normalized_compare_text(tr) == normalized_compare_text(rv):
        return "", "", 0, "No reviewer change."

    if not tr and rv:
        return "Accuracy", "Critical", SEVERITY_POINTS["Critical"], "Translator target is blank while reviewer/final contains translation."
    if tr and not rv:
        return "Accuracy", "Major", SEVERITY_POINTS["Major"], "Reviewer/final target is blank or removed compared with translator output."

    tr_ph = extract_scorecard_placeholders(tr)
    rv_ph = extract_scorecard_placeholders(rv)
    if sorted(tr_ph) != sorted(rv_ph):
        return "Accuracy", "Major", SEVERITY_POINTS["Major"], "Placeholder/tag mismatch between translator and reviewer/final output."

    tr_nums = extract_scorecard_numbers(tr)
    rv_nums = extract_scorecard_numbers(rv)
    if sorted(tr_nums) != sorted(rv_nums):
        return "Country Standards", "Major", SEVERITY_POINTS["Major"], "Number, unit, or locale-sensitive value changed between translator and reviewer/final output."

    if src and normalized_compare_text(tr) == normalized_compare_text(src) and normalized_compare_text(rv) != normalized_compare_text(src):
        return "Accuracy", "Critical", SEVERITY_POINTS["Critical"], "Translator appears to have left source text untranslated."

    ratio = difflib.SequenceMatcher(None, normalized_compare_text(tr), normalized_compare_text(rv)).ratio()
    tr_compact = re.sub(r"[\s\W_]+", "", normalized_compare_text(tr))
    rv_compact = re.sub(r"[\s\W_]+", "", normalized_compare_text(rv))

    if tr_compact == rv_compact:
        return "Grammar", "Minor", SEVERITY_POINTS["Minor"], "Reviewer changed punctuation, spacing, casing, or minor formatting only."
    if ratio >= 0.92:
        return "Grammar", "Minor", SEVERITY_POINTS["Minor"], "Reviewer made a small language/formatting correction."
    if ratio >= 0.78:
        return "Style and Tone", "Minor", SEVERITY_POINTS["Minor"], "Reviewer made a style/tone or wording refinement."
    if ratio >= 0.55:
        return "Readability", "Major", SEVERITY_POINTS["Major"], "Reviewer substantially rewrote the segment for readability or clarity."

    return "Accuracy", "Major", SEVERITY_POINTS["Major"], "Reviewer/final translation differs substantially from translator output."


def build_scorecard_records(trans_rows: List[Dict[str, Any]], rev_rows: List[Dict[str, Any]], src_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    max_len = max(len(trans_rows), len(rev_rows), len(src_rows))
    records: List[Dict[str, Any]] = []
    category_counts = {cat: {sev: 0 for sev in ERROR_SEVERITIES} for cat in ERROR_CATEGORIES}
    severity_counts = {sev: 0 for sev in ERROR_SEVERITIES}
    total_penalty = 0
    changed_count = 0
    checked_words = 0

    for i in range(max_len):
        t = trans_rows[i] if i < len(trans_rows) else {}
        r = rev_rows[i] if i < len(rev_rows) else {}
        s = src_rows[i] if i < len(src_rows) else {}

        source = s.get("source") or t.get("source") or r.get("source") or ""
        translator = t.get("target") or t.get("translation") or t.get("source", "")
        reviewer = r.get("target") or r.get("translation") or r.get("source", "")
        source = safe_text(source)
        translator = safe_text(translator)
        reviewer = safe_text(reviewer)
        checked_words += count_words(source or translator or reviewer)

        changed_here = normalized_compare_text(translator) != normalized_compare_text(reviewer)
        category, severity, penalty, comment = scorecard_category_and_severity(source, translator, reviewer)
        if changed_here:
            changed_count += 1
            total_penalty += penalty
            if category in category_counts and severity in category_counts[category]:
                category_counts[category][severity] += 1
            if severity in severity_counts:
                severity_counts[severity] += 1

        records.append({
            "Item No.": i + 1,
            "Source Text": source,
            "Original Translation": translator,
            "Suggested Translation": reviewer if changed_here else "",
            "Repeated Error": "",
            "Error Category": category,
            "Error Severity": severity,
            "Reviewer's Comment": comment if changed_here else "",
            "Agree? (Yes/No)": "",
            "Comment": "",
            "Reviewer's Response": "",
            "Final Error Category": "",
            "Final Error Severity": "",
            "Changed": "Yes" if changed_here else "No",
            "Penalty": penalty,
        })

    score = max(0, 100 - total_penalty)
    result = "PASS" if score >= 90 else "REVIEW" if score >= 75 else "FAIL"
    summary = {
        "segments": max_len,
        "checked_words": checked_words,
        "changed_count": changed_count,
        "total_penalty": total_penalty,
        "score": score,
        "result": result,
        "category_counts": category_counts,
        "severity_counts": severity_counts,
    }
    return records, summary


def style_sheet_base(ws) -> None:
    ws.sheet_view.showGridLines = False
    thin = Side(style="thin", color="D7DEE8")
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)


def apply_widths(ws, widths: Dict[str, float]) -> None:
    for col, width in widths.items():
        ws.column_dimensions[col].width = width


def create_scorecard_excel(records: List[Dict[str, Any]], summary: Dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "QA Eval Sheet"
    score_ws = wb.create_sheet("Quality Evaluation")
    instr_ws = wb.create_sheet("LQA Instructions")

    dark = "1F2937"
    blue = "D9EAF7"
    green = "D9EAD3"
    yellow = "FFF2CC"
    red = "F4CCCC"
    border = Side(style="thin", color="A6A6A6")

    # Sheet 1: QA Eval Sheet
    ws.merge_cells("B1:M1")
    ws["B1"] = "ErrorSweep Linguistic Review Form"
    ws["B1"].font = Font(bold=True, size=14, color="FFFFFF")
    ws["B1"].alignment = Alignment(horizontal="center")
    ws["B1"].fill = PatternFill("solid", fgColor=dark)

    meta_rows = [
        ("B2", "Client", "C2", "", "D2", "Project ID", "E2", ""),
        ("B3", "Source language*", "C3", "", "D3", "Target language*", "E3", ""),
        ("B4", "Translator", "C4", "", "D4", "Reviewer", "E4", ""),
        ("B5", "Date (mm/dd/yyyy)*", "C5", "", "D5", "Number of checked words*", "E5", summary.get("checked_words", 0)),
    ]
    for row in meta_rows:
        for label_cell, label, value_cell, value in [(row[0], row[1], row[2], row[3]), (row[4], row[5], row[6], row[7])]:
            ws[label_cell] = label
            ws[value_cell] = value
            ws[label_cell].font = Font(bold=True)
            ws[label_cell].fill = PatternFill("solid", fgColor=blue)

    headers = [
        "Item No.", "Source Text", "Original Translation", "Suggested Translation", "Repeated Error",
        "Error Category", "Error Severity", "Reviewer's Comment", "Agree? (Yes/No)", "Comment",
        "Reviewer's Response", "Error Category", "Error Severity"
    ]
    header_row = 7
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.font = Font(bold=True, color="000000")
        cell.fill = PatternFill("solid", fgColor=blue)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_idx, rec in enumerate(records, start=header_row + 1):
        values = [
            rec.get("Item No."), rec.get("Source Text"), rec.get("Original Translation"), rec.get("Suggested Translation"),
            rec.get("Repeated Error"), rec.get("Error Category"), rec.get("Error Severity"), rec.get("Reviewer's Comment"),
            rec.get("Agree? (Yes/No)"), rec.get("Comment"), rec.get("Reviewer's Response"),
            rec.get("Final Error Category"), rec.get("Final Error Severity"),
        ]
        for col_idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if col_idx in (6, 12) and value:
                cell.fill = PatternFill("solid", fgColor=yellow)
            if col_idx in (7, 13) and value:
                if value == "Critical":
                    cell.fill = PatternFill("solid", fgColor=red)
                elif value == "Major":
                    cell.fill = PatternFill("solid", fgColor="FCE4D6")
                elif value == "Minor":
                    cell.fill = PatternFill("solid", fgColor=yellow)

    apply_widths(ws, {
        "A": 10, "B": 42, "C": 42, "D": 42, "E": 14, "F": 18, "G": 16, "H": 36,
        "I": 15, "J": 26, "K": 30, "L": 18, "M": 16,
    })
    ws.freeze_panes = "A8"

    # Sheet 2: Quality Evaluation
    score_ws.merge_cells("A1:D1")
    score_ws["A1"] = "Quality Evaluation Score Card"
    score_ws["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    score_ws["A1"].alignment = Alignment(horizontal="center")
    score_ws["A1"].fill = PatternFill("solid", fgColor=dark)

    score_ws["A3"] = "Number of checked words"
    score_ws["B3"] = summary.get("checked_words", 0)
    score_ws["A5"] = "Client"
    score_ws["B5"] = ""
    score_ws["A6"] = "Project ID"
    score_ws["B6"] = ""
    score_ws["A7"] = "Review date"
    score_ws["B7"] = ""
    score_ws["A8"] = "Source language"
    score_ws["B8"] = ""
    score_ws["A9"] = "Target language"
    score_ws["B9"] = ""

    score_ws["A12"] = "Error category"
    score_ws["B11"] = "Error severity"
    score_ws["B12"] = "Minor"
    score_ws["C12"] = "Major"
    score_ws["D12"] = "Critical"
    for cell in score_ws["A12:D12"][0]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=blue)

    for idx, cat in enumerate(ERROR_CATEGORIES, start=13):
        score_ws.cell(row=idx, column=1, value=cat)
        for col_idx, sev in enumerate(ERROR_SEVERITIES, start=2):
            score_ws.cell(row=idx, column=col_idx, value=summary["category_counts"].get(cat, {}).get(sev, 0))

    total_row = 13 + len(ERROR_CATEGORIES) + 1
    score_ws.cell(total_row, 1, "Total errors")
    score_ws.cell(total_row, 2, summary["severity_counts"].get("Minor", 0))
    score_ws.cell(total_row, 3, summary["severity_counts"].get("Major", 0))
    score_ws.cell(total_row, 4, summary["severity_counts"].get("Critical", 0))
    for cell in score_ws[total_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=green)

    score_ws["A22"] = "Penalty points"
    score_ws["B22"] = summary.get("total_penalty", 0)
    score_ws["A23"] = "LQA score"
    score_ws["B23"] = summary.get("score", 0)
    score_ws["A24"] = "Pass/Fail result"
    score_ws["B24"] = summary.get("result", "")
    score_ws["A25"] = "Changed segments"
    score_ws["B25"] = summary.get("changed_count", 0)
    score_ws["A26"] = "Compared segments"
    score_ws["B26"] = summary.get("segments", 0)
    for cell in ["A22", "A23", "A24", "A25", "A26"]:
        score_ws[cell].font = Font(bold=True)
        score_ws[cell].fill = PatternFill("solid", fgColor=blue)

    apply_widths(score_ws, {"A": 24, "B": 16, "C": 16, "D": 16})

    # Sheet 3: LQA Instructions
    instr_ws["A1"] = "Error categories"
    instr_ws["A1"].font = Font(bold=True, size=13)
    instr_ws["A2"] = "Category"
    instr_ws["B2"] = "Description"
    instr_ws["A2"].font = Font(bold=True)
    instr_ws["B2"].font = Font(bold=True)
    instr_ws["A2"].fill = PatternFill("solid", fgColor=blue)
    instr_ws["B2"].fill = PatternFill("solid", fgColor=blue)
    for idx, cat in enumerate(ERROR_CATEGORIES, start=3):
        instr_ws.cell(row=idx, column=1, value=cat)
        instr_ws.cell(row=idx, column=2, value=CATEGORY_DESCRIPTIONS[cat])

    sev_start = 3 + len(ERROR_CATEGORIES) + 2
    instr_ws.cell(row=sev_start, column=1, value="Error severities")
    instr_ws.cell(row=sev_start, column=1).font = Font(bold=True, size=13)
    instr_ws.cell(row=sev_start + 1, column=1, value="Severity")
    instr_ws.cell(row=sev_start + 1, column=2, value="Description")
    instr_ws.cell(row=sev_start + 1, column=1).font = Font(bold=True)
    instr_ws.cell(row=sev_start + 1, column=2).font = Font(bold=True)
    instr_ws.cell(row=sev_start + 1, column=1).fill = PatternFill("solid", fgColor=blue)
    instr_ws.cell(row=sev_start + 1, column=2).fill = PatternFill("solid", fgColor=blue)
    for offset, sev in enumerate(ERROR_SEVERITIES, start=sev_start + 2):
        instr_ws.cell(row=offset, column=1, value=sev)
        instr_ws.cell(row=offset, column=2, value=SEVERITY_DESCRIPTIONS[sev])

    apply_widths(instr_ws, {"A": 24, "B": 95})

    for sheet in [ws, score_ws, instr_ws]:
        style_sheet_base(sheet)
        for row in sheet.iter_rows():
            for cell in row:
                cell.border = Border(left=border, right=border, top=border, bottom=border)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for idx in range(1, sheet.max_row + 1):
            sheet.row_dimensions[idx].height = 28

    # Validation for editable category / severity columns in QA Eval Sheet.
    cat_validation = DataValidation(type="list", formula1='"Accuracy,Readability,Style and Tone,Grammar,Country Standards"', allow_blank=True)
    sev_validation = DataValidation(type="list", formula1='"Minor,Major,Critical"', allow_blank=True)
    yesno_validation = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    ws.add_data_validation(cat_validation)
    ws.add_data_validation(sev_validation)
    ws.add_data_validation(yesno_validation)
    last_row = max(header_row + 1, header_row + len(records))
    cat_validation.add(f"F{header_row+1}:F{last_row}")
    cat_validation.add(f"L{header_row+1}:L{last_row}")
    sev_validation.add(f"G{header_row+1}:G{last_row}")
    sev_validation.add(f"M{header_row+1}:M{last_row}")
    yesno_validation.add(f"I{header_row+1}:I{last_row}")

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


def page_scorecards() -> None:
    hero("Scorecards", "Translator vs reviewer quality score", "Compare translator output with reviewer/final output and generate an Excel-only LQA scorecard.")
    source = st.file_uploader("Source file (optional)", type=["xlsx", "csv", "docx", "txt"], key="score_source")
    translator = st.file_uploader("Translator file", type=["xlsx", "csv", "docx", "txt"], key="score_translator")
    reviewer = st.file_uploader("Reviewer/final file", type=["xlsx", "csv", "docx", "txt"], key="score_reviewer")

    st.info("Scorecard output is always generated as an Excel workbook with: QA Eval Sheet, Quality Evaluation, and LQA Instructions.")

    if st.button("Generate Excel Scorecard", use_container_width=True, disabled=translator is None or reviewer is None):
        trans_rows = extract_rows_from_upload(translator)
        rev_rows = extract_rows_from_upload(reviewer)
        src_rows = extract_rows_from_upload(source) if source else []
        records, summary = build_scorecard_records(trans_rows, rev_rows, src_rows)

        metrics([
            ("LQA Score", summary["score"], summary["result"]),
            ("Segments", summary["segments"], "compared"),
            ("Changed", summary["changed_count"], "reviewer edits"),
            ("Penalty", summary["total_penalty"], "points"),
        ])

        preview_cols = ["Item No.", "Source Text", "Original Translation", "Suggested Translation", "Error Category", "Error Severity", "Reviewer's Comment"]
        st.dataframe(pd.DataFrame(records)[preview_cols], use_container_width=True, hide_index=True)

        xlsx_bytes = create_scorecard_excel(records, summary)
        st.download_button(
            "Download Excel Scorecard",
            xlsx_bytes,
            file_name="ErrorSweep_Translator_Scorecard.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

def page_memory_rules() -> None:
    hero("Memory & Rules", "Reusable language assets", "Manage translation memory, glossary, DNT terms, and client instructions.")
    tab_tm, tab_gloss, tab_dnt = st.tabs(["Translation Memory", "Glossary", "DNT"])

    with tab_tm:
        st.markdown("### Translation Memory")
        with st.form("add_tm"):
            c1, c2 = st.columns(2)
            src = c1.text_area("Source", height=90)
            tgt = c2.text_area("Target", height=90)
            lang = st.text_input("Target language")
            submitted = st.form_submit_button("Add TM entry", use_container_width=True)
        if submitted and src and tgt:
            st.session_state.tm.append({"source": src, "target": tgt, "language": lang, "created": now_stamp(), "approved_by": (current_user() or {}).get("email","")})
            st.success("TM entry added.")
        st.dataframe(pd.DataFrame(st.session_state.tm), use_container_width=True, hide_index=True)

    with tab_gloss:
        st.markdown("### Glossary")
        with st.form("add_gloss"):
            c1, c2, c3 = st.columns(3)
            src = c1.text_input("Source term")
            tgt = c2.text_input("Target term")
            notes = c3.text_input("Notes")
            submitted = st.form_submit_button("Add glossary term", use_container_width=True)
        if submitted and src:
            st.session_state.glossary.append({"source": src, "target": tgt, "notes": notes})
            st.success("Glossary term added.")
        st.dataframe(pd.DataFrame(st.session_state.glossary), use_container_width=True, hide_index=True)

    with tab_dnt:
        st.markdown("### Do-not-translate terms")
        term = st.text_input("Add DNT term")
        if st.button("Add DNT", use_container_width=True) and term:
            st.session_state.dnt.append(term)
            st.success("DNT term added.")
        st.dataframe(pd.DataFrame({"DNT term": st.session_state.dnt}), use_container_width=True, hide_index=True)


def page_team_roles() -> None:
    hero("Team & Roles", "Workspace access control", "Manage workspace users and role-level access.")
    if current_role() not in ("Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager"):
        st.error("You do not have permission to manage team roles.")
        return
    st.dataframe(pd.DataFrame(st.session_state.users), use_container_width=True, hide_index=True)
    with st.form("add_user"):
        c1, c2, c3 = st.columns(3)
        email = c1.text_input("User email")
        role = c2.selectbox("Role", ["Workspace Owner", "Workspace Admin", "Project Manager", "Translator", "Reviewer", "Client Viewer", "Billing Admin", "User"])
        status = c3.selectbox("Status", ["Active", "Suspended"])
        submitted = st.form_submit_button("Add user", use_container_width=True)
    if submitted and email:
        st.session_state.users.append({"email": email, "workspace": (current_user() or {}).get("workspace", "Demo Workspace"), "role": role, "plan": "Trial", "status": status})
        add_audit("User added", email)
        st.success("User added.")


def page_billing() -> None:
    hero("Billing", "Plans and usage", "Workspace plan, credits, invoices, and payment gateway setup.")
    metrics([
        ("Plan", "Demo", "upgrade flow pending"),
        ("Credits", "Unlimited", "during platform build"),
        ("Invoices", len(st.session_state.payments), "demo records"),
        ("Gateway", "Razorpay / Stripe", "future integration"),
    ])
    st.info("Billing integration can be connected after project/jobs/review workflows are stable.")


def page_account() -> None:
    hero("Account", "Profile and workspace preferences", "Manage user profile, workspace settings, and notification preferences.")
    user = current_user() or {}
    st.write("Email:", user.get("email"))
    st.write("Role:", user.get("role"))
    st.write("Workspace:", user.get("workspace"))

    st.markdown("### AI access")
    st.caption("Use included AI, or add your own OpenAI key for BYO-Key mode. Your key is kept only in this session for the MVP.")
    current_mode = "BYO key active" if st.session_state.get("byo_openai_api_key") else current_ai_route_label()
    st.info(f"Current route: {current_mode}")
    with st.form("byo_key_form"):
        byo_key = st.text_input("Your OpenAI API key (optional)", type="password", placeholder="sk-...", help="Leave blank to use included Managed AI if enabled.")
        byo_model = st.text_input("OpenAI model for BYO key", value=st.session_state.get("byo_openai_model", secret("ERRORSWEEP_OPENAI_DEFAULT_MODEL", DEFAULT_MODEL)))
        col_a, col_b = st.columns(2)
        save_key = col_a.form_submit_button("Use this key", use_container_width=True)
        clear_key = col_b.form_submit_button("Clear BYO key", use_container_width=True)
    if save_key:
        if byo_key.strip():
            st.session_state["byo_openai_api_key"] = byo_key.strip()
            st.session_state["byo_openai_model"] = byo_model.strip() or DEFAULT_MODEL
            st.success("BYO OpenAI key activated for this session.")
        else:
            st.warning("No key entered. Included AI will be used if configured.")
    if clear_key:
        st.session_state.pop("byo_openai_api_key", None)
        st.session_state.pop("byo_openai_model", None)
        st.success("BYO key cleared. Included AI will be used if configured.")

    st.checkbox("Email notifications", value=True)
    st.checkbox("Show review hints", value=True)


def page_admin() -> None:
    hero("Admin", "Workspace admin", "Workspace-level configuration and maintenance.")
    if current_role() not in ("Platform Owner", "Workspace Owner", "Workspace Admin"):
        st.error("Admin access is restricted.")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Workspace summary")
        metrics([
            ("Projects", len(st.session_state.projects), ""),
            ("Jobs", len(st.session_state.jobs), ""),
            ("Review rows", len(st.session_state.review_segments), ""),
            ("TM", len(st.session_state.tm), ""),
        ])
    with c2:
        st.markdown("### Maintenance")
        if st.button("Clear demo jobs/review only", use_container_width=True):
            st.session_state.jobs = []
            st.session_state.review_segments = []
            st.session_state.subtitle_segments = []
            st.success("Demo jobs and review rows cleared.")
        if st.button("Clear all demo workspace data", use_container_width=True):
            for key in ["projects", "jobs", "tm", "review_segments", "subtitle_segments", "last_pro_review_segments", "latest_human_review_segments", "pro_review_rows"]:
                st.session_state[key] = []
            st.session_state["pro_post_editing_ready"] = False
            st.success("Demo workspace data cleared.")


# Owner pages

def page_owner_console() -> None:
    hero("Owner Console", "Private platform owner view", "Only your master account can see global payments, users, workspaces, usage, and platform controls.")
    metrics([
        ("Workspaces", len(st.session_state.workspaces), "all customer/client spaces"),
        ("Users", len(st.session_state.users), "all access records"),
        ("Payments", len(st.session_state.payments), "received or demo records"),
        ("Audit Logs", len(st.session_state.audit_logs), "platform events"),
    ])

    st.markdown("### Release persistence")
    if persistence_health is not None:
        health = persistence_health()
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Storage", health.get("storage_mode", "unknown"))
        h2.metric("Supabase", "Ready" if health.get("supabase_configured") else "Fallback")
        h3.metric("Jobs table", health.get("editor_jobs_table", "unknown"))
        h4.metric("Usage table", health.get("usage_events_table", "unknown"))
        with st.expander("Persistence diagnostics", expanded=False):
            st.json(health)
    else:
        st.warning("production_persistence.py is not available. Editor jobs are using session/local fallback only.")

    st.markdown("### Current / recent task details")
    active_job_id = st.session_state.get("active_review_session_id", "")
    active_rows = st.session_state.get("review_segments") or st.session_state.get("last_pro_review_segments") or []
    last_task = st.session_state.get("last_pro_task_details") or {}
    session_jobs = st.session_state.get("owner_recent_editor_jobs", [])

    if active_job_id or last_task or active_rows:
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Active job", str(active_job_id or last_task.get("id", "—"))[:10] if (active_job_id or last_task.get("id")) else "—")
        t2.metric("File", last_task.get("file_name", st.session_state.get("review_workspace_file_name", "—")) or "—")
        t3.metric("Rows", len(active_rows) or int(last_task.get("row_count") or 0))
        t4.metric("Target", last_task.get("target_language", st.session_state.get("review_workspace_language", "—")) or "—")

        with st.expander("Current task row preview", expanded=False):
            preview_rows = []
            for i, row in enumerate(active_rows[:25], start=1):
                preview_rows.append({
                    "No": i,
                    "Source": safe_text(row.get("source", ""))[:180],
                    "Target": safe_text(row.get("target", row.get("translation", "")))[:180],
                    "Status": safe_text(row.get("status", "")),
                    "Match": safe_text(row.get("match", "")),
                    "Location": safe_text(row.get("location", "")),
                })
            if preview_rows:
                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
            else:
                st.info("The active task exists, but no row preview is available in session.")
    else:
        st.info("No active Pro review task is currently stored in this browser session.")

    if session_jobs:
        with st.expander("Session-created editor jobs", expanded=True):
            st.dataframe(pd.DataFrame(session_jobs), use_container_width=True, hide_index=True)

    st.markdown("### Owner actions")
    c1, c2, c3 = st.columns(3)
    c1.info("Review all workspace access from User Access Matrix.")
    c2.info("Track received payments from Payments Received.")
    c3.info("Control global feature flags from Platform Settings.")

    st.markdown("### Translation / AI usage")
    persistent_usage = []
    if fetch_persistent_usage_events is not None:
        try:
            persistent_usage = fetch_persistent_usage_events(300)
        except Exception:
            persistent_usage = []
    usage_rows = persistent_usage or st.session_state.get("ai_usage_events", [])
    if usage_rows:
        usage_df = pd.DataFrame(usage_rows)
        st.dataframe(usage_df, use_container_width=True, hide_index=True)
        if "characters" in usage_df.columns:
            st.caption(f"Total characters logged: {int(pd.to_numeric(usage_df['characters'], errors='coerce').fillna(0).sum())}")
    else:
        st.info("No usage logged yet.")

    st.markdown("### Recent editor jobs")
    editor_jobs = []
    if fetch_persistent_editor_jobs is not None:
        try:
            editor_jobs = fetch_persistent_editor_jobs(100)
        except Exception:
            editor_jobs = []
    combined_jobs = []
    if editor_jobs:
        combined_jobs.extend(editor_jobs)
    for job in st.session_state.get("owner_recent_editor_jobs", []):
        if not any(str(j.get("id")) == str(job.get("id")) for j in combined_jobs):
            combined_jobs.append(job)

    if combined_jobs:
        st.dataframe(pd.DataFrame(combined_jobs), use_container_width=True, hide_index=True)
    else:
        st.info("No persisted editor jobs found yet. Run Pro, click Open Human Review Editor, then return here.")


def page_payments_received() -> None:
    hero("Payments Received", "Revenue and payment records", "Owner-only list of payments, plans, access granted, and payment status.")
    with st.form("add_payment"):
        c1, c2, c3, c4 = st.columns(4)
        workspace = c1.text_input("Workspace")
        user = c2.text_input("User email")
        plan = c3.selectbox("Plan", ["Trial", "Pro", "Agency", "Enterprise"])
        amount = c4.number_input("Amount", min_value=0.0, value=0.0)
        submitted = st.form_submit_button("Add payment record", use_container_width=True)
    if submitted:
        st.session_state.payments.insert(0, {"date": now_stamp(), "workspace": workspace, "user": user, "plan": plan, "amount": amount, "currency": "USD", "status": "Recorded"})
        add_audit("Payment record added", f"{workspace}: {amount}")
        st.success("Payment record added.")
    st.dataframe(pd.DataFrame(st.session_state.payments), use_container_width=True, hide_index=True)


def page_user_access_matrix() -> None:
    hero("User Access Matrix", "Who has what access", "Owner-only view of user roles, workspaces, plans, statuses, and allowed pages.")
    rows = []
    for u in st.session_state.users:
        role = u.get("role", "User")
        rows.append({**u, "allowed_pages": ", ".join(ROLE_PAGE_ACCESS.get(role, []))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_all_workspaces() -> None:
    hero("All Workspaces", "Customer workspace overview", "Owner-only list of all organizations, plans, users, and job counts.")
    st.dataframe(pd.DataFrame(st.session_state.workspaces), use_container_width=True, hide_index=True)


def page_platform_settings() -> None:
    hero("Platform Settings", "Global feature controls", "Owner-only controls for platform features and public availability.")
    settings = {
        "Main API translation": True,
        "Pro post-editing Human Review": True,
        "Scorecards": True,
        "Subtitle / Transcription Editor": True,
        "Public registration": False,
        "Billing collection": False,
        "Self-hosted engines": False,
    }
    for label, val in settings.items():
        st.checkbox(label, value=val)

    st.markdown("### Release readiness diagnostics")
    if persistence_health is not None:
        health = persistence_health()
        st.json(health)
        if health.get("supabase_configured") and health.get("editor_jobs_table") == "ok" and health.get("usage_events_table") == "ok":
            st.success("Production persistence is connected. Editor jobs and usage events can survive app reboot.")
        else:
            st.warning("Production persistence is not fully connected. Run the v42 Supabase SQL schema and add SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets.")
    else:
        st.warning("production_persistence.py is missing.")


def page_platform_audit_logs() -> None:
    hero("Platform Audit Logs", "Owner event trail", "Owner-only view of sign-ins, payments, access changes, and administrative actions.")
    if st.session_state.audit_logs:
        st.dataframe(pd.DataFrame(st.session_state.audit_logs), use_container_width=True, hide_index=True)
    else:
        st.info("No audit logs yet.")


PAGE_RENDERERS = {
    "Dashboard": page_dashboard,
    "Projects": page_projects,
    "Jobs": page_jobs,
    "ErrorSweep QA": page_qa,
    "ErrorSweep Pro": page_pro,
    "Subtitle / Transcription Editor": page_subtitle_transcription_editor,
    "Human Review Workspace": page_human_review_workspace,
    "Subtitle Workspace": page_subtitle_workspace,
    "Transcription Workspace": page_transcription_workspace,
    "Scorecards": page_scorecards,
    "Memory & Rules": page_memory_rules,
    "Team & Roles": page_team_roles,
    "Billing": page_billing,
    "Account": page_account,
    "Admin": page_admin,
    "Owner Console": page_owner_console,
    "Payments Received": page_payments_received,
    "User Access Matrix": page_user_access_matrix,
    "All Workspaces": page_all_workspaces,
    "Platform Settings": page_platform_settings,
    "Platform Audit Logs": page_platform_audit_logs,
}


# ==========================================================
# Main app
# ==========================================================

def render_app() -> None:
    user = current_user()
    if not user:
        render_login()
        return

    # v41: external editor routes open as full-window pages in a new tab.
    # They must render before normal dashboard routing/navigation.
    if render_external_editor_router():
        return

    # Restore selected page from URL query when navigation links are used.
    requested_page = query_get("es_page")
    if requested_page in allowed_pages():
        st.session_state.page = requested_page

    # Ensure selected page is allowed.
    if st.session_state.page not in allowed_pages():
        st.session_state.page = allowed_pages()[0] if allowed_pages() else "Dashboard"

    page = st.session_state.page
    renderer = PAGE_RENDERERS.get(page, page_dashboard)

    # Dedicated editor workspaces should feel like full web applications, not
    # like a normal dashboard page squeezed beside the platform navigation.
    # This is especially important for the CAT-style Human Review editor.
    if page in {"Human Review Workspace", "Subtitle Workspace", "Transcription Workspace"}:
        renderer()
        return

    nav_col, main_col = st.columns([0.23, 0.77], gap="large")
    with nav_col:
        render_navigation()
    with main_col:
        renderer()


render_app()

