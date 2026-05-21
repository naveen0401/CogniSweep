
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

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from docx import Document


# ==========================================================
# ErrorSweep Platform v30
# Website-style localization platform shell + two-phase built-in translation engine
# Phase 1: Azure Translator | Phase 2: NLLB self-hosted
# Owner console + workspace workflows + Human Review + Focused Subtitle/Transcription workspace
# ==========================================================

APP_VERSION = "v30 Built-in Translation Engine"
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
    "Human Review",
    "Scorecards",
    "Memory & Rules",
    "Team & Roles",
    "Billing",
    "Account",
    "Admin",
]

ROLE_PAGE_ACCESS = {
    "Platform Owner": OWNER_PAGES + WORKSPACE_PAGES,
    "Workspace Owner": WORKSPACE_PAGES,
    "Workspace Admin": ["Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Human Review", "Scorecards", "Memory & Rules", "Team & Roles", "Account", "Admin"],
    "Project Manager": ["Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Human Review", "Scorecards", "Memory & Rules", "Account"],
    "Translator": ["Dashboard", "Jobs", "Human Review", "Account"],
    "Reviewer": ["Dashboard", "Jobs", "ErrorSweep QA", "Human Review", "Scorecards", "Memory & Rules", "Account"],
    "Client Viewer": ["Dashboard", "Jobs", "Account"],
    "Billing Admin": ["Dashboard", "Billing", "Account"],
    "User": ["Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Human Review", "Scorecards", "Memory & Rules", "Account"],
}


def current_user() -> Optional[Dict[str, Any]]:
    return st.session_state.get("user")


def current_role() -> str:
    user = current_user() or {}
    return user.get("role", "User")


def allowed_pages() -> List[str]:
    return ROLE_PAGE_ACCESS.get(current_role(), ROLE_PAGE_ACCESS["User"])


def is_owner() -> bool:
    return current_role() == "Platform Owner"


def page_link(page: str) -> str:
    token = query_get("es_session")
    page_param = quote(page)
    if token:
        return f"?es_session={token}&es_page={page_param}"
    return f"?es_page={page_param}"


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
    """Session-level MVP usage log. Later this can be saved in Supabase ai_usage_events."""
    st.session_state.setdefault("ai_usage_events", [])
    st.session_state.ai_usage_events.insert(0, {
        "time": now_stamp() if "now_stamp" in globals() else datetime.now().strftime("%Y-%m-%d %H:%M"),
        "purpose": purpose,
        "provider": usage.get("provider", "unknown"),
        "model": usage.get("model", ""),
        "managed": usage.get("managed", False),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "success": usage.get("success", False),
        "error": usage.get("error", ""),
        "segments": segment_count,
    })


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
        st.markdown("### ✍️ Open Human Review")
        st.caption("Edit text, subtitles, or transcription output and save approved TM.")

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
    hero("Jobs", "Workflow queue", "Track uploads, translation, QA, Human Review, scorecards, and delivery status.")
    if st.session_state.jobs:
        st.dataframe(pd.DataFrame(st.session_state.jobs), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet.")
    st.markdown("### Create manual job")
    with st.form("manual_job"):
        c1, c2, c3 = st.columns(3)
        job_type = c1.selectbox("Job type", ["QA", "Pro Translation", "Human Review", "Subtitle Review", "Transcription", "Scorecard"])
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
    c1, c2, c3 = st.columns(3)
    strictness = c1.selectbox("Strictness", ["Lenient", "Standard", "Strict", "Very Strict"], index=2)
    domain = c2.selectbox("Domain", ["Auto-detect", "Software UI", "Marketing", "Legal", "Medical", "E-learning", "Subtitling", "General"])
    route_review = c3.checkbox("Send findings to Human Review", value=True)

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

        st.session_state.review_segments = findings
        st.session_state.jobs.insert(0, {"created": now_stamp(), "type": "QA", "language": "", "status": "Needs Review", "segments": len(findings)})
        add_audit("QA run", f"{len(findings)} segments")
        st.success("QA completed and review segments prepared.")
        st.dataframe(pd.DataFrame(findings), use_container_width=True, hide_index=True)
        st.download_button("Download QA CSV", rows_to_csv(findings), file_name="errorsweep_qa_findings.csv", mime="text/csv", use_container_width=True)


def page_pro() -> None:
    hero("ErrorSweep Pro", "Translate + QA + Human Review", "Use main API translation first, then route uncertain segments to Human Review.")
    st.caption(f"AI access: {current_ai_route_label()}")
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
        st.session_state.review_segments = review_rows
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
            st.success("Translation completed.")

        st.dataframe(pd.DataFrame(review_rows), use_container_width=True, hide_index=True)
        st.download_button("Download Review CSV", rows_to_csv(review_rows), file_name="errorsweep_pro_review.csv", mime="text/csv", use_container_width=True)
        st.info("Open Human Review to edit, approve, and save verified segments to TM.")


# ==========================================================
# Human Review Editors
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
    st.markdown("### Text Review Editor")
    uploaded = st.file_uploader("Upload review file directly", type=["xlsx", "csv", "docx", "txt", "srt", "vtt"], key="text_review_file")
    c1, c2 = st.columns([1, 1])
    if c1.button("Load uploaded file into review editor", use_container_width=True, disabled=uploaded is None):
        st.session_state.review_segments = extract_rows_from_upload(uploaded)
        st.session_state.selected_review_index = 0
        add_audit("Review file loaded", uploaded.name if uploaded else "")
        st.success("File loaded into Human Review.")

    if c2.button("Use latest QA/Pro segments", use_container_width=True):
        if st.session_state.review_segments:
            st.success("Latest review segments loaded.")
        else:
            st.warning("No latest QA/Pro segments available.")

    rows = st.session_state.review_segments
    if not rows:
        st.info("Upload a file or run ErrorSweep QA/Pro first.")
        return

    idx = min(st.session_state.selected_review_index, len(rows)-1)
    row = rows[idx]

    left, center, right = st.columns([2.2, 3.6, 1.8])

    with left:
        st.markdown("#### Source segments")
        for i, seg in enumerate(rows):
            status = seg.get("status", "Untranslated")
            match = seg.get("match", "")
            label = f"{i+1}. {seg.get('source','')[:70] or seg.get('target','')[:70]}"
            st.markdown(f'<div class="es-small"><span class="es-chip {"green" if status=="Approved" else "amber" if "Review" in status else ""}">{escape(status)}</span> {escape(match)}</div>', unsafe_allow_html=True)
            if st.button(label, key=f"review_pick_{i}", use_container_width=True):
                st.session_state.selected_review_index = i
                st.rerun()

    with center:
        st.markdown(f"#### Segment {idx+1} / {len(rows)}")
        st.markdown(f'<span class="es-chip">{escape(row.get("match","") or "No match")}</span> <span class="es-chip amber">{escape(row.get("status","Untranslated"))}</span>', unsafe_allow_html=True)
        source_text = st.text_area("Source", value=row.get("source", ""), height=150, disabled=True, key=f"source_{idx}")
        target_text = st.text_area("Target", value=row.get("target", ""), height=220, key=f"target_{idx}")
        status = st.selectbox("Segment status", ["MT", "Fuzzy 75%", "Fuzzy 85%", "100%", "101%", "Needs Review", "Approved", "Rejected", "Needs Rework", "Untranslated"], index=0 if row.get("status") not in ["Approved","Rejected"] else ["MT","Fuzzy 75%","Fuzzy 85%","100%","101%","Needs Review","Approved","Rejected","Needs Rework","Untranslated"].index(row.get("status")), key=f"status_{idx}")

        b1, b2, b3, b4 = st.columns(4)
        if b1.button("Save", key=f"save_{idx}", use_container_width=True):
            rows[idx]["target"] = target_text
            rows[idx]["status"] = status
            st.success("Saved.")
        if b2.button("Approve", key=f"approve_{idx}", use_container_width=True):
            rows[idx]["target"] = target_text
            rows[idx]["status"] = "Approved"
            st.success("Approved.")
        if b3.button("Save to TM", key=f"tm_{idx}", use_container_width=True):
            rows[idx]["target"] = target_text
            rows[idx]["status"] = "Approved"
            st.session_state.tm.append({"source": row.get("source",""), "target": target_text, "language": "", "created": now_stamp(), "approved_by": (current_user() or {}).get("email","")})
            st.success("Approved and saved to TM.")
        if b4.button("Next", key=f"next_{idx}", use_container_width=True):
            rows[idx]["target"] = target_text
            rows[idx]["status"] = status
            st.session_state.selected_review_index = min(idx+1, len(rows)-1)
            st.rerun()

    with right:
        render_assist_panel(row.get("source", ""))

    st.markdown("### Bulk target grid")
    edited = st.data_editor(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="review_bulk_grid",
    )
    if st.button("Save bulk grid", use_container_width=True):
        st.session_state.review_segments = edited.to_dict("records")
        st.success("Bulk grid saved.")

    st.download_button("Download reviewed CSV", rows_to_csv(st.session_state.review_segments), "human_review_output.csv", "text/csv", use_container_width=True)



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
    st.caption("Create a dedicated editor workspace. Transcription needs only a video. Subtitling can optionally use an English source script/subtitle file.")

    workflow = st.radio("Editor workflow", ["Subtitling", "Transcription"], horizontal=True, key="subtitle_workflow_picker")
    video = st.file_uploader("Upload video", type=["mp4", "mov", "m4v", "webm"], key="subtitle_video_setup")

    if video:
        preview_col, info_col = st.columns([0.55, 0.45], gap="large")
        with preview_col:
            st.video(video.getvalue())
        with info_col:
            st.success("Video loaded. Create the editor to open the focused workspace.")
            st.caption("The next screen keeps the video compact at the top, script editor in the middle, and timing/text grid in a collapsible panel.")
    else:
        st.info("Upload a video to begin.")

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
        if st.button("Create subtitling workspace", use_container_width=True, disabled=video is None):
            if source_file:
                rows = extract_rows_from_upload(source_file)
                for i, r in enumerate(rows):
                    r.setdefault("start", i * 4.0)
                    r.setdefault("end", i * 4.0 + 3.5)
                    r.setdefault("target", "")
                    r.setdefault("status", "Untranslated")
                    r.setdefault("match", "")
            else:
                rows = default_subtitle_segments(8, transcription=False)
            if target_file:
                target_rows = extract_rows_from_upload(target_file)
                for i, tr in enumerate(target_rows):
                    if i < len(rows):
                        rows[i]["target"] = tr.get("target") or tr.get("source") or ""
                        rows[i]["status"] = "Existing" if rows[i]["target"] else rows[i].get("status", "Untranslated")
            enter_subtitle_workspace("Subtitling", rows, video)
            st.rerun()
    else:
        st.caption("Transcription mode does not need a source file. You write the transcript while watching the video.")
        starter_count = st.number_input("Starter transcript rows", min_value=1, max_value=200, value=10, key="transcription_starter_count")
        if st.button("Create transcription workspace", use_container_width=True, disabled=video is None):
            rows = default_subtitle_segments(int(starter_count), transcription=True)
            enter_subtitle_workspace("Transcription", rows, video)
            st.rerun()

    if st.session_state.subtitle_segments:
        if st.button("Open existing subtitle/transcription workspace", use_container_width=True):
            st.session_state.subtitle_editor_active = True
            st.rerun()


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
            st.rerun()

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


def page_human_review() -> None:
    # Dedicated editor mode should feel like a new page and avoid the large hero consuming space.
    if st.session_state.get("subtitle_editor_active"):
        render_focused_subtitle_workspace()
        return
    hero("Human Review", "CAT, subtitling, and transcription editors", "Review translations, edit subtitles, create transcripts, sync timing, and save verified translations.")
    tab_text, tab_sub = st.tabs(["Text Review Editor", "Subtitle / Transcription Editor"])
    with tab_text:
        render_text_review_editor()
    with tab_sub:
        render_subtitle_transcription_editor()



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
            for key in ["projects", "jobs", "tm", "review_segments", "subtitle_segments"]:
                st.session_state[key] = []
            st.success("Demo workspace data cleared.")


# Owner pages

def page_owner_console() -> None:
    hero("Owner Console", "Private platform owner view", "Only your master account can see global payments, users, workspaces, and platform controls.")
    metrics([
        ("Workspaces", len(st.session_state.workspaces), "all customer/client spaces"),
        ("Users", len(st.session_state.users), "all access records"),
        ("Payments", len(st.session_state.payments), "received or demo records"),
        ("Audit Logs", len(st.session_state.audit_logs), "platform events"),
    ])
    st.markdown("### Owner actions")
    c1, c2, c3 = st.columns(3)
    c1.info("Review all workspace access from User Access Matrix.")
    c2.info("Track received payments from Payments Received.")
    c3.info("Control global feature flags from Platform Settings.")

    st.markdown("### Managed AI usage")
    usage_rows = st.session_state.get("ai_usage_events", [])
    if usage_rows:
        st.dataframe(pd.DataFrame(usage_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No Managed AI/BYO usage logged in this session yet.")


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
        "Human Review": True,
        "Scorecards": True,
        "Subtitle / Transcription Editor": True,
        "Public registration": False,
        "Billing collection": False,
        "Self-hosted engines": False,
    }
    for label, val in settings.items():
        st.checkbox(label, value=val)
    st.info("These are MVP owner controls. Persistent settings can be connected to Supabase later.")


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
    "Human Review": page_human_review,
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

    # Restore selected page from URL query when navigation links are used.
    requested_page = query_get("es_page")
    if requested_page in allowed_pages():
        st.session_state.page = requested_page

    # Ensure selected page is allowed.
    if st.session_state.page not in allowed_pages():
        st.session_state.page = allowed_pages()[0] if allowed_pages() else "Dashboard"

    nav_col, main_col = st.columns([0.23, 0.77], gap="large")
    with nav_col:
        render_navigation()
    with main_col:
        page = st.session_state.page
        renderer = PAGE_RENDERERS.get(page, page_dashboard)
        renderer()


render_app()

