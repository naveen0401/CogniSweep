
import io
import os
import re
import json
import time
import uuid
import zipfile
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.comments import Comment
from docx import Document

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


# ==========================================================
# ErrorSweep Platform v19
# Main API first. Local/Libre/Indic engines are optional later.
# ==========================================================

st.set_page_config(
    page_title="ErrorSweep Platform",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "v19 Platform Shell"
DEFAULT_OPENAI_MODEL = os.getenv("ERRORSWEEP_OPENAI_MODEL", "gpt-4o-mini")
SMART_REVIEW_THRESHOLD = 0.12
NEEDS_REVIEW_MARKER = "⟦NEEDS HUMAN REVIEW⟧"

SUPPORTED_API_LANGUAGES = [
    "French", "Spanish", "German", "Italian", "Portuguese",
    "Telugu", "Hindi", "Tamil", "Malayalam", "Kannada",
    "Arabic", "Chinese", "Japanese", "Korean", "Russian",
]

BETA_LOCAL_LANGUAGES = {
    "LibreTranslate": ["French", "Spanish", "German", "Italian", "Portuguese"],
    "IndicTrans2": ["Telugu", "Hindi", "Tamil", "Malayalam", "Kannada"],
}

ROLE_PERMISSIONS = {
    "Owner": {
        "dashboard", "projects", "jobs", "qa", "pro", "review", "scorecards",
        "memory", "team", "billing", "account", "admin", "engine_status"
    },
    "Admin": {
        "dashboard", "projects", "jobs", "qa", "pro", "review", "scorecards",
        "memory", "team", "account", "admin", "engine_status"
    },
    "Project Manager": {
        "dashboard", "projects", "jobs", "qa", "pro", "review",
        "scorecards", "memory", "account", "engine_status"
    },
    "Translator": {"dashboard", "jobs", "pro", "review", "memory", "account"},
    "Reviewer": {"dashboard", "jobs", "qa", "review", "scorecards", "memory", "account"},
    "Client Viewer": {"dashboard", "jobs", "scorecards", "account"},
    "Billing Admin": {"dashboard", "billing", "account"},
    "Super Admin": {
        "dashboard", "projects", "jobs", "qa", "pro", "review", "scorecards",
        "memory", "team", "billing", "account", "admin", "engine_status"
    },
}

PAGE_META = {
    "Dashboard": ("dashboard", "📊"),
    "Projects": ("projects", "🗂️"),
    "Jobs": ("jobs", "🧾"),
    "ErrorSweep QA": ("qa", "🧹"),
    "ErrorSweep Pro": ("pro", "🚀"),
    "Human Review": ("review", "✍️"),
    "Scorecards": ("scorecards", "🏆"),
    "Memory & Rules": ("memory", "📚"),
    "Team & Roles": ("team", "👥"),
    "Billing": ("billing", "💳"),
    "Account": ("account", "⚙️"),
    "Admin": ("admin", "🛡️"),
    "Engine Status": ("engine_status", "🧪"),
}


# ==========================================================
# Visual system
# ==========================================================

def inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background:
        radial-gradient(circle at 12% 8%, rgba(16,185,129,0.14), transparent 30%),
        radial-gradient(circle at 92% 2%, rgba(59,130,246,0.14), transparent 28%),
        radial-gradient(circle at 52% 105%, rgba(139,92,246,0.12), transparent 36%),
        #070A12;
    color: #E5E7EB;
}
#MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
    visibility: hidden !important;
    display: none !important;
}
.block-container {
    padding-top: 1.5rem !important;
}
.es-hero {
    position: relative;
    overflow: hidden;
    padding: 34px 34px 30px;
    margin: 0 0 20px;
    border-radius: 26px;
    border: 1px solid rgba(59,130,246,0.22);
    background:
        linear-gradient(135deg, rgba(16,185,129,0.18), rgba(59,130,246,0.10), rgba(139,92,246,0.12)),
        rgba(15, 23, 42, 0.78);
    box-shadow: 0 30px 90px rgba(0,0,0,0.35);
}
.es-hero:after {
    content: "";
    position: absolute;
    width: 360px;
    height: 360px;
    right: -100px;
    top: -160px;
    background: radial-gradient(circle, rgba(34,211,238,0.23), transparent 65%);
}
.es-kicker {
    display: inline-flex;
    gap: 8px;
    align-items: center;
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid rgba(16,185,129,0.28);
    color: #34D399;
    background: rgba(16,185,129,0.08);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .3px;
    text-transform: uppercase;
}
.es-title {
    margin: 14px 0 8px;
    font-size: 44px;
    line-height: 1.05;
    font-weight: 850;
    letter-spacing: -1.2px;
    background: linear-gradient(90deg, #F8FAFC, #A7F3D0, #93C5FD);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.es-subtitle {
    color: #B8C0D9;
    font-size: 16px;
    max-width: 920px;
}
.es-card {
    border-radius: 20px;
    border: 1px solid rgba(148,163,184,0.18);
    background: rgba(15, 23, 42, 0.72);
    box-shadow: 0 18px 50px rgba(0,0,0,0.20);
    padding: 18px;
}
.es-card h3, .es-card h4 {
    margin-top: 0;
}
.es-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin: 16px 0;
}
.es-grid-4 {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin: 16px 0;
}
.es-tile {
    border-radius: 18px;
    border: 1px solid rgba(59,130,246,0.18);
    background: rgba(15,23,42,.66);
    padding: 16px;
}
.es-tile .label {
    font-size: 11px;
    color: #94A3B8;
    font-weight: 800;
    letter-spacing: .6px;
    text-transform: uppercase;
}
.es-tile .value {
    margin-top: 5px;
    font-size: 22px;
    font-weight: 850;
    color: #F8FAFC;
}
.es-badge {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    padding: 5px 10px;
    margin: 2px 4px 2px 0;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    border: 1px solid rgba(148,163,184,.22);
    background: rgba(15,23,42,.65);
}
.es-badge.green { color:#34D399; border-color:rgba(52,211,153,.35); background:rgba(16,185,129,.08);}
.es-badge.yellow { color:#FBBF24; border-color:rgba(251,191,36,.35); background:rgba(251,191,36,.08);}
.es-badge.red { color:#FB7185; border-color:rgba(251,113,133,.35); background:rgba(251,113,133,.08);}
.es-badge.blue { color:#93C5FD; border-color:rgba(147,197,253,.35); background:rgba(59,130,246,.08);}
.es-muted { color:#94A3B8; font-size:13px; }
.es-section-title {
    margin: 20px 0 10px;
    font-weight: 850;
    letter-spacing: -0.4px;
}
.stButton > button, .stDownloadButton > button {
    border-radius: 14px !important;
    border: 1px solid rgba(16,185,129,0.28) !important;
    background: linear-gradient(90deg, #10B981, #0EA5E9) !important;
    color: white !important;
    font-weight: 800 !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 32px rgba(14,165,233,0.20);
}
[data-testid="stMetric"] {
    border-radius: 18px;
    border: 1px solid rgba(59,130,246,0.18);
    background: rgba(15,23,42,.66);
    padding: 16px;
}
div[data-testid="stExpander"] {
    border-radius: 16px !important;
    border: 1px solid rgba(148,163,184,0.20) !important;
    background: rgba(15, 23, 42, 0.66) !important;
}
.es-editor {
    border-radius: 18px;
    border: 1px solid rgba(59,130,246,.22);
    background: rgba(15,23,42,.68);
    padding: 14px;
}
.es-footer-note {
    color:#64748B;
    font-size:12px;
    padding: 12px 0;
}
@media (max-width: 1000px) {
    .es-grid, .es-grid-4 { grid-template-columns: 1fr; }
    .es-title { font-size: 34px; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, kicker: str = "ErrorSweep Platform") -> None:
    st.markdown(
        f"""
<div class="es-hero">
    <div class="es-kicker">🌐 {kicker}</div>
    <div class="es-title">{escape_html(title)}</div>
    <div class="es-subtitle">{escape_html(subtitle)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def badge(text: str, color: str = "blue") -> str:
    return f'<span class="es-badge {color}">{escape_html(text)}</span>'


def card_html(title: str, body: str, icon: str = "•") -> None:
    st.markdown(
        f"""
<div class="es-card">
    <h3>{icon} {escape_html(title)}</h3>
    <div class="es-muted">{body}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def metric_tile(label: str, value: str, sub: str = "") -> str:
    return f"""
<div class="es-tile">
  <div class="label">{escape_html(label)}</div>
  <div class="value">{escape_html(value)}</div>
  <div class="es-muted">{escape_html(sub)}</div>
</div>
"""


def escape_html(value: Any) -> str:
    import html
    return html.escape("" if value is None else str(value))


# ==========================================================
# Session state
# ==========================================================

def init_state() -> None:
    defaults = {
        "authenticated": False,
        "active_role": "Owner",
        "active_org": "Nawin Corp",
        "active_project_id": None,
        "projects": [],
        "jobs": [],
        "review_sessions": [],
        "translation_memory": [],
        "glossary": [],
        "dnt_terms": [],
        "style_guides": [],
        "team": [
            {"name": "Naveen", "email": "owner@example.com", "role": "Owner", "status": "Active"},
        ],
        "last_output_bytes": None,
        "last_output_name": "",
        "last_output_mime": "text/csv",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ==========================================================
# Secrets / clients / auth
# ==========================================================

def get_secret(name: str, default: str = "") -> str:
    if os.getenv(name):
        return os.getenv(name, default)
    try:
        value = st.secrets.get(name)
        if value is not None:
            return str(value)
    except Exception:
        pass
    return default


def get_openai_client() -> Optional[OpenAI]:
    key = get_secret("OPENAI_API_KEY")
    if not key:
        return None
    try:
        return OpenAI(api_key=key, timeout=90, max_retries=1)
    except Exception:
        return None


def supabase_available() -> bool:
    return bool(get_secret("SUPABASE_URL") and get_secret("SUPABASE_ANON_KEY"))


def supabase_url(path: str) -> str:
    return get_secret("SUPABASE_URL").rstrip("/") + path


def supabase_headers(access_token: Optional[str] = None, service: bool = False) -> Dict[str, str]:
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY") if service else get_secret("SUPABASE_ANON_KEY")
    token = access_token or key
    return {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def supabase_post(path: str, payload: Dict[str, Any], access_token: Optional[str] = None, service: bool = False) -> Tuple[bool, Any]:
    try:
        res = requests.post(supabase_url(path), headers=supabase_headers(access_token, service), json=payload, timeout=30)
        if res.status_code >= 400:
            try:
                return False, res.json()
            except Exception:
                return False, res.text
        try:
            return True, res.json()
        except Exception:
            return True, {}
    except Exception as exc:
        return False, str(exc)


def format_error(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("message", "msg", "error_description", "error"):
            if data.get(key):
                return str(data[key])
        return json.dumps(data)[:500]
    return str(data)[:500]


def render_login() -> None:
    hero("ErrorSweep", "Secure localization QA, translation review, scorecards, and memory workflows.", "Account required")

    demo_allowed = get_secret("ERRORSWEEP_ALLOW_DEMO_LOGIN", "true").lower() in {"1", "true", "yes"}
    use_supabase = supabase_available()
    local_user = get_secret("ERRORSWEEP_USERNAME")
    local_pass = get_secret("ERRORSWEEP_PASSWORD")

    tab1, tab2, tab3 = st.tabs(["Sign in", "Create account", "Demo access"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email / username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign in", use_container_width=True, type="primary")

        if submit:
            if use_supabase and "@" in email:
                ok, data = supabase_post("/auth/v1/token?grant_type=password", {"email": email.strip().lower(), "password": password})
                if ok and data.get("access_token"):
                    st.session_state["authenticated"] = True
                    st.session_state["user_email"] = data.get("user", {}).get("email", email)
                    st.session_state["sb_access_token"] = data.get("access_token")
                    st.success("Signed in.")
                    st.rerun()
                else:
                    st.error(format_error(data))
            elif local_user and local_pass:
                if hmac.compare_digest(email.strip(), local_user.strip()) and hmac.compare_digest(password, local_pass):
                    st.session_state["authenticated"] = True
                    st.session_state["user_email"] = email.strip()
                    st.success("Signed in.")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
            else:
                st.error("No auth provider is configured. Use Demo access or add Supabase/local credentials.")

    with tab2:
        st.caption("Supabase sign-up is used when Supabase secrets are configured.")
        with st.form("signup_form"):
            full_name = st.text_input("Full name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm = st.text_input("Confirm password", type="password")
            submit = st.form_submit_button("Create account", use_container_width=True)
        if submit:
            if not use_supabase:
                st.error("Supabase is not configured.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                ok, data = supabase_post(
                    "/auth/v1/signup",
                    {"email": email.strip().lower(), "password": password, "data": {"full_name": full_name}},
                )
                if ok:
                    st.success("Account created. Confirm email if required, then sign in.")
                else:
                    st.error(format_error(data))

    with tab3:
        st.caption("For development and demos only.")
        if demo_allowed and st.button("Continue as Owner", use_container_width=True):
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = "demo@errorsweep.local"
            st.session_state["active_role"] = "Owner"
            st.rerun()
        elif not demo_allowed:
            st.warning("Demo login disabled by admin.")


def require_auth() -> None:
    if not st.session_state.get("authenticated"):
        render_login()
        st.stop()


# ==========================================================
# Data helpers
# ==========================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def active_project() -> Optional[Dict[str, Any]]:
    pid = st.session_state.get("active_project_id")
    for p in st.session_state["projects"]:
        if p["id"] == pid:
            return p
    return st.session_state["projects"][0] if st.session_state["projects"] else None


def add_job(job: Dict[str, Any]) -> None:
    st.session_state["jobs"].insert(0, job)


def can(page: str) -> bool:
    role = st.session_state.get("active_role", "Owner")
    return page in ROLE_PERMISSIONS.get(role, set())


# ==========================================================
# File extraction and output
# ==========================================================

PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|<[^>]+>)")
NUMBER_RE = re.compile(r"\d+(?:[.,:]\d+)*")
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\ufe0f\u200d]+", re.UNICODE)

SOURCE_HEADER_CANDIDATES = {"source", "source text", "source string", "source segment", "english", "src"}
TARGET_HEADER_CANDIDATES = {"target", "target text", "translation", "original translation", "translated text", "localized"}


def norm(text: Any) -> str:
    if text is None:
        return ""
    return str(text).replace("\u00a0", " ").strip()


def find_source_target(headers: List[str]) -> Tuple[Optional[str], Optional[str]]:
    lower = {str(h).strip().lower(): h for h in headers}
    src = None
    tgt = None
    for key, original in lower.items():
        if key in SOURCE_HEADER_CANDIDATES or "source" in key:
            src = original
            break
    for key, original in lower.items():
        if key in TARGET_HEADER_CANDIDATES or "translation" in key or "target" in key:
            tgt = original
            break
    return src, tgt


def is_translatable_line(text: str) -> bool:
    t = norm(text)
    if len(t) < 2:
        return False
    if t.lower() in {"source", "target", "source text", "translation", "original translation"}:
        return False
    return True


def extract_segments(uploaded_file, mode: str = "pro") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    name = uploaded_file.name
    lower = name.lower()
    context: Dict[str, Any] = {"file_name": name, "file_type": lower.rsplit(".", 1)[-1] if "." in lower else "txt"}
    segments: List[Dict[str, Any]] = []

    if lower.endswith(".xlsx"):
        wb = load_workbook(uploaded_file)
        context["workbook"] = wb
        context["cell_targets"] = {}
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=False))
            if not rows:
                continue
            best_row = None
            best_src = None
            best_tgt = None
            for i, row in enumerate(rows[:30]):
                headers = [norm(c.value) for c in row]
                if not any(headers):
                    continue
                src, tgt = find_source_target(headers)
                score = (2 if src else 0) + (2 if tgt else 0)
                if src and score >= 2:
                    best_row = i
                    best_src = headers.index(src)
                    best_tgt = headers.index(tgt) if tgt in headers else None
                    break
            if best_row is None:
                continue
            if mode == "pro" and best_tgt is None:
                best_tgt = ws.max_column
                ws.cell(row=best_row + 1, column=best_tgt + 1).value = "AI Translation"
            for r_idx in range(best_row + 2, ws.max_row + 1):
                src_val = norm(ws.cell(r_idx, best_src + 1).value)
                tgt_val = norm(ws.cell(r_idx, best_tgt + 1).value) if best_tgt is not None else ""
                if not is_translatable_line(src_val):
                    continue
                if mode == "qa" and not tgt_val:
                    continue
                loc = f"{ws.title}!R{r_idx}"
                segments.append({
                    "id": len(segments) + 1,
                    "location": loc,
                    "sheet": ws.title,
                    "row": r_idx,
                    "source": src_val,
                    "translation": tgt_val,
                    "target_cell": (ws.title, r_idx, best_tgt + 1) if best_tgt is not None else None,
                    "file_type": "xlsx",
                })
        return segments, context

    if lower.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        context["dataframe"] = df
        headers = list(df.columns)
        src_col, tgt_col = find_source_target(headers)
        if src_col is None:
            src_col = headers[0]
        if mode == "pro" and (tgt_col is None or tgt_col not in df.columns):
            tgt_col = "AI Translation"
            df[tgt_col] = ""
        context["target_column"] = tgt_col
        for idx, row in df.iterrows():
            src = norm(row.get(src_col, ""))
            tgt = norm(row.get(tgt_col, "")) if tgt_col else ""
            if not is_translatable_line(src):
                continue
            if mode == "qa" and not tgt:
                continue
            segments.append({
                "id": len(segments) + 1,
                "location": f"Row {idx + 2}",
                "row": idx,
                "source": src,
                "translation": tgt,
                "file_type": "csv",
            })
        return segments, context

    if lower.endswith(".docx"):
        doc = Document(uploaded_file)
        context["doc"] = doc
        context["doc_targets"] = {}
        for table_i, table in enumerate(doc.tables, start=1):
            header_i = None
            src_idx = None
            tgt_idx = None
            for r_i, row in enumerate(table.rows[:20]):
                headers = [norm(c.text) for c in row.cells]
                src, tgt = find_source_target(headers)
                if src:
                    header_i = r_i
                    src_idx = headers.index(src)
                    tgt_idx = headers.index(tgt) if tgt in headers else None
                    break
            if header_i is None:
                continue
            for r_i in range(header_i + 1, len(table.rows)):
                row = table.rows[r_i]
                if len(row.cells) <= src_idx:
                    continue
                src = norm(row.cells[src_idx].text)
                tgt = norm(row.cells[tgt_idx].text) if tgt_idx is not None and len(row.cells) > tgt_idx else ""
                if not is_translatable_line(src):
                    continue
                if mode == "qa" and not tgt:
                    continue
                loc = f"Table {table_i}, Row {r_i + 1}"
                segments.append({
                    "id": len(segments) + 1,
                    "location": loc,
                    "source": src,
                    "translation": tgt,
                    "file_type": "docx",
                })
                if tgt_idx is not None:
                    context["doc_targets"][loc] = row.cells[tgt_idx]
        if not segments:
            for i, p in enumerate(doc.paragraphs, start=1):
                src = norm(p.text)
                if is_translatable_line(src):
                    loc = f"Paragraph {i}"
                    segments.append({
                        "id": len(segments) + 1,
                        "location": loc,
                        "source": src,
                        "translation": "",
                        "file_type": "docx",
                    })
                    context["doc_targets"][loc] = p
        return segments, context

    raw = uploaded_file.read()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("cp1252", errors="replace")
    context["text"] = text
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        src = norm(line)
        if is_translatable_line(src):
            segments.append({
                "id": len(segments) + 1,
                "location": f"Line {i}",
                "line": i,
                "source": src,
                "translation": "",
                "file_type": "text",
            })
    return segments, context


def set_docx_cell_text(cell, text: str) -> None:
    if hasattr(cell, "paragraphs"):
        for p in cell.paragraphs:
            for run in p.runs:
                run.text = ""
        if cell.paragraphs:
            cell.paragraphs[0].add_run(text)
        else:
            cell.add_paragraph(text)


def build_output_file(context: Dict[str, Any], segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str]) -> Tuple[bytes, str, str]:
    file_name = context.get("file_name", "output")
    ftype = context.get("file_type", "csv")
    base = re.sub(r"\.[^.]+$", "", file_name)

    if ftype == "xlsx":
        wb = context["workbook"]
        for seg in segments:
            tgt = seg.get("target_cell")
            if tgt:
                ws, row, col = tgt
                wb[ws].cell(row=row, column=col).value = translations_by_loc.get(seg["location"], "")
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue(), f"{base}_translated.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    if ftype == "csv":
        df = context["dataframe"]
        target_col = context.get("target_column", "AI Translation")
        if target_col not in df.columns:
            df[target_col] = ""
        for seg in segments:
            df.at[seg["row"], target_col] = translations_by_loc.get(seg["location"], "")
        return df.to_csv(index=False).encode("utf-8-sig"), f"{base}_translated.csv", "text/csv"

    if ftype == "docx":
        doc = context["doc"]
        targets = context.get("doc_targets", {})
        for seg in segments:
            loc = seg["location"]
            tgt_obj = targets.get(loc)
            translation = translations_by_loc.get(loc, "")
            if tgt_obj is None:
                continue
            if hasattr(tgt_obj, "runs"):  # paragraph
                tgt_obj.add_run("\n" + translation)
            else:
                set_docx_cell_text(tgt_obj, translation)
        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue(), f"{base}_translated.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    table = []
    for seg in segments:
        table.append({
            "Location": seg["location"],
            "Source": seg["source"],
            "Translation": translations_by_loc.get(seg["location"], ""),
        })
    return pd.DataFrame(table).to_csv(index=False).encode("utf-8-sig"), f"{base}_translations.csv", "text/csv"


# ==========================================================
# Rule pack
# ==========================================================

def parse_rules_zip(uploaded_zip) -> Dict[str, Any]:
    rules = {"glossary": [], "dnt": [], "style": [], "raw": ""}
    if not uploaded_zip:
        return rules
    try:
        zf = zipfile.ZipFile(io.BytesIO(uploaded_zip.getvalue()))
    except Exception:
        return rules
    pieces = []
    for info in zf.infolist()[:40]:
        if info.is_dir() or info.file_size > 8_000_000:
            continue
        name = info.filename
        data = zf.read(info)
        text = ""
        try:
            if name.lower().endswith((".txt", ".md", ".json", ".xml", ".csv")):
                text = data.decode("utf-8", errors="ignore")
            elif name.lower().endswith(".docx"):
                doc = Document(io.BytesIO(data))
                text = "\n".join(p.text for p in doc.paragraphs)
            elif name.lower().endswith(".pdf") and PdfReader:
                reader = PdfReader(io.BytesIO(data))
                text = "\n".join((p.extract_text() or "") for p in reader.pages[:10])
        except Exception:
            text = ""
        if not text.strip():
            continue
        pieces.append(f"# {name}\n{text[:4000]}")
        for line in text.splitlines():
            low = line.lower()
            if "do not translate" in low or low.startswith("dnt"):
                rules["dnt"].append({"term": line.split(":")[-1].strip(), "source": name})
            if "=>" in line:
                left, right = line.split("=>", 1)
                rules["glossary"].append({"source": left.strip(), "target": right.strip(), "source_file": name})
    rules["raw"] = "\n\n".join(pieces)[:12000]
    return rules


def rules_text_for_prompt(rules: Dict[str, Any]) -> str:
    parts = []
    if st.session_state.get("glossary"):
        parts.append("Saved Glossary:\n" + "\n".join(f"{g['source']} => {g['target']}" for g in st.session_state["glossary"][:100]))
    if st.session_state.get("dnt_terms"):
        parts.append("Saved DNT:\n" + "\n".join(d["term"] for d in st.session_state["dnt_terms"][:100]))
    if rules.get("raw"):
        parts.append("Uploaded Rule Pack:\n" + rules["raw"][:8000])
    return "\n\n".join(parts)


# ==========================================================
# Translation / QA with main API
# ==========================================================

def mask_protected(text: str) -> Tuple[str, Dict[str, str]]:
    tokens = {}
    def repl(m):
        key = f"ZXQ{len(tokens)}QXZ"
        tokens[key] = m.group(0)
        return key
    combined = re.compile(
        f"({URL_RE.pattern}|{EMAIL_RE.pattern}|{PLACEHOLDER_RE.pattern})",
        re.UNICODE,
    )
    return combined.sub(repl, text), tokens


def unmask_protected(text: str, tokens: Dict[str, str], source: str = "") -> str:
    out = text or ""
    for key, value in tokens.items():
        out = re.sub(re.escape(key), value, out, flags=re.IGNORECASE)
        if value not in out:
            out += " " + value
    # Preserve leading emojis/icons if model dropped them.
    src_emoji = EMOJI_RE.findall(source or "")
    for e in src_emoji:
        if e and e not in out:
            out = e + " " + out.lstrip()
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def parse_json_array(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    cleaned = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.I)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end+1]
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def call_openai_json(client: OpenAI, instructions: str, prompt: str, max_tokens: int = 4000) -> List[Dict[str, Any]]:
    response = client.responses.create(
        model=DEFAULT_OPENAI_MODEL,
        instructions=instructions,
        input=prompt,
        max_output_tokens=max_tokens,
    )
    return parse_json_array(response.output_text)


def translate_batch_api(client: OpenAI, batch: List[Dict[str, Any]], target_language: str, domain: str, rules_text: str) -> List[Dict[str, str]]:
    prepared = []
    token_maps = {}
    for i, seg in enumerate(batch, start=1):
        masked, tokens = mask_protected(seg["source"])
        token_maps[seg["location"]] = (tokens, seg["source"])
        prepared.append(f"[{i}]\nLocation: {seg['location']}\nSource: {masked}")

    prompt = f"""
Translate the following localization strings into {target_language}.

Domain: {domain}

Client rules, glossary, DNT, and style notes:
{rules_text if rules_text else "(none)"}

Critical rules:
- Preserve all placeholder tokens exactly, including ZXQ0QXZ style masked tokens.
- Preserve URLs, emails, numbers, units, HTML/XML tags, and product names.
- Preserve leading bullets/icons/emojis.
- Square-bracket UI labels can be localized inside brackets.
- Return JSON only.

Segments:
{chr(10).join(prepared)}

Return:
[
  {{"location":"exact location","translation":"translated text"}}
]
"""
    instructions = "You are a senior software localization translator. Return only a valid JSON array."
    raw = call_openai_json(client, instructions, prompt, max_tokens=5000)
    results = []
    for item in raw:
        loc = str(item.get("location", ""))
        translation = str(item.get("translation", ""))
        if loc:
            tokens, source = token_maps.get(loc, ({}, ""))
            translation = unmask_protected(translation, tokens, source)
            results.append({"location": loc, "translation": translation})
    return results


def qa_batch_api(client: OpenAI, batch: List[Dict[str, Any]], domain: str, rules_text: str) -> List[Dict[str, Any]]:
    parts = []
    for i, seg in enumerate(batch, start=1):
        parts.append(
            f"[{i}]\nLocation: {seg['location']}\nSource: {seg.get('source','')}\nTarget: {seg.get('translation','')}"
        )
    prompt = f"""
Review these localization segments.

Domain: {domain}
Rules:
{rules_text if rules_text else "(none)"}

Find only real localization QA issues:
- missing/changed placeholders, URLs, emails, tags, numbers, units
- source copied to target
- untranslated target
- wrong language or mixed script
- glossary/DNT violations
- accuracy, terminology, grammar, punctuation, or formatting defects

Do not flag personal preference.

Segments:
{chr(10).join(parts)}

Return JSON only:
[
  {{
    "location": "exact location",
    "error_type": "Accuracy|Terminology|Placeholder|Number|Formatting|Language|DNT|Glossary|Grammar|Style",
    "severity": "Critical|Major|Minor|Review",
    "wrong_part": "exact issue",
    "suggestion": "fix",
    "explanation": "short reason"
  }}
]
"""
    instructions = "You are ErrorSweep, a conservative localization QA reviewer. Return only valid JSON."
    return call_openai_json(client, instructions, prompt, max_tokens=5000)


def deterministic_issues(seg: Dict[str, Any], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    source = seg.get("source", "")
    target = seg.get("translation", "")
    rows = []
    if not target.strip():
        rows.append(issue_row(seg, "Completeness", "Critical", "Blank target", "Translate this segment.", "Target is blank."))
        return rows

    for ph in PLACEHOLDER_RE.findall(source):
        if ph not in target:
            rows.append(issue_row(seg, "Placeholder", "Major", ph, f"Keep {ph}", "Placeholder from source is missing."))
    for n in NUMBER_RE.findall(source):
        if n not in target:
            rows.append(issue_row(seg, "Number", "Major", n, f"Keep number {n}", "Number from source is missing or changed."))

    if source.strip().lower() == target.strip().lower() and re.search(r"[A-Za-z]{3,}", source):
        rows.append(issue_row(seg, "Language", "Major", target, "Translate instead of copying source.", "Target appears copied from source."))

    for d in st.session_state.get("dnt_terms", []):
        term = d.get("term", "")
        if term and term in source and term not in target:
            rows.append(issue_row(seg, "DNT", "Major", term, f"Keep {term}", "DNT term changed or omitted."))

    for g in st.session_state.get("glossary", []):
        src = g.get("source", "")
        tgt = g.get("target", "")
        if src and tgt and src.lower() in source.lower() and tgt not in target:
            rows.append(issue_row(seg, "Glossary", "Major", src, tgt, "Glossary target term missing."))

    return rows


def issue_row(seg: Dict[str, Any], error_type: str, severity: str, wrong: str, suggestion: str, explanation: str) -> Dict[str, Any]:
    return {
        "Location": seg.get("location", ""),
        "Source": seg.get("source", ""),
        "Translation": seg.get("translation", ""),
        "Error Type": error_type,
        "Severity": severity,
        "Wrong Part": wrong,
        "Suggestion": suggestion,
        "Explanation": explanation,
    }


def is_bad_translation(source: str, target: str) -> bool:
    s = norm(source)
    t = norm(target)
    if not t:
        return True
    if t == NEEDS_REVIEW_MARKER:
        return True
    stripped = PLACEHOLDER_RE.sub("", t)
    stripped = NUMBER_RE.sub("", stripped)
    stripped = re.sub(r"[\s\[\]{}():;,.!?\"'`~\-–—_/\\|•∙·*]+", "", stripped)
    if stripped == "" and len(re.sub(r"\W+", "", s)) > 3:
        return True
    if s.lower() == t.lower() and re.search(r"[A-Za-z]{3,}", s):
        return True
    return False


def smart_completion_gate(segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str]) -> Tuple[bool, bool, List[Dict[str, str]], float]:
    missing = []
    for seg in segments:
        loc = seg["location"]
        target = translations_by_loc.get(loc, "")
        if is_bad_translation(seg["source"], target):
            missing.append({
                "Location": loc,
                "Source": seg["source"],
                "Current Translation": target,
                "Action": "Human Review required",
            })
    missing_rate = len(missing) / max(len(segments), 1)
    if not missing:
        return True, False, missing, missing_rate
    if missing_rate <= SMART_REVIEW_THRESHOLD:
        for item in missing:
            translations_by_loc[item["Location"]] = NEEDS_REVIEW_MARKER
        return True, True, missing, missing_rate
    return False, False, missing, missing_rate


# ==========================================================
# Reports
# ==========================================================

def dataframe_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def issues_excel(issues: List[Dict[str, Any]], status_rows: List[Dict[str, Any]]) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame(status_rows).to_excel(writer, index=False, sheet_name="All Segment Review")
        pd.DataFrame(issues).to_excel(writer, index=False, sheet_name="Issue Details")
    return bio.getvalue()


def make_status_rows(segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str], issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues_by_loc = {}
    for issue in issues:
        issues_by_loc.setdefault(issue.get("Location", ""), []).append(issue)
    rows = []
    for seg in segments:
        loc = seg["location"]
        target = translations_by_loc.get(loc, seg.get("translation", ""))
        irows = issues_by_loc.get(loc, [])
        rows.append({
            "Location": loc,
            "Source": seg["source"],
            "Translation": target,
            "Review Status": "Needs Review" if irows or target == NEEDS_REVIEW_MARKER else "Pass",
            "Issue Count": len(irows),
            "Highest Severity": highest_severity(irows),
            "Error Types": "; ".join(sorted({x.get("Error Type", "") for x in irows})),
        })
    return rows


def highest_severity(rows: List[Dict[str, Any]]) -> str:
    order = {"Critical": 4, "Major": 3, "Minor": 2, "Review": 1}
    if not rows:
        return "Pass"
    return max((r.get("Severity", "Review") for r in rows), key=lambda x: order.get(x, 1))


# ==========================================================
# Sidebar/navigation
# ==========================================================

def sidebar_nav() -> str:
    with st.sidebar:
        st.markdown("## 🌐 ErrorSweep")
        st.caption(APP_VERSION)

        role = st.selectbox("Active role", list(ROLE_PERMISSIONS.keys()), index=list(ROLE_PERMISSIONS.keys()).index(st.session_state.get("active_role", "Owner")))
        st.session_state["active_role"] = role

        if st.button("Logout", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

        st.divider()
        pages = []
        for label, (perm, icon) in PAGE_META.items():
            if can(perm):
                pages.append(f"{icon} {label}")

        selected = st.radio("Navigation", pages, label_visibility="collapsed")
        page = selected.split(" ", 1)[1]

        st.divider()
        project = active_project()
        st.caption("Active workspace")
        st.write(f"**{st.session_state.get('active_org','Organization')}**")
        if project:
            st.write(f"Project: **{project['name']}**")
        else:
            st.info("Create a project to organize jobs.")

        st.divider()
        st.caption("Main engine")
        if get_secret("OPENAI_API_KEY"):
            st.markdown(badge("Main API connected", "green"), unsafe_allow_html=True)
        else:
            st.markdown(badge("Main API missing", "red"), unsafe_allow_html=True)

    return page


# ==========================================================
# Pages
# ==========================================================

def page_dashboard() -> None:
    hero("Localization operations hub", "Manage projects, translation jobs, QA reports, human review, scorecards, and translation memory from one workspace.", "Dashboard")

    total_jobs = len(st.session_state["jobs"])
    total_projects = len(st.session_state["projects"])
    total_tm = len(st.session_state["translation_memory"])
    review_pending = sum(1 for s in st.session_state["review_sessions"] if s.get("status") != "Completed")

    st.markdown(
        f"""
<div class="es-grid-4">
{metric_tile("Projects", str(total_projects), "client/product workspaces")}
{metric_tile("Jobs", str(total_jobs), "QA / Pro / Scorecard")}
{metric_tile("TM entries", str(total_tm), "approved translations")}
{metric_tile("Pending review", str(review_pending), "segments or sessions")}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Recommended next steps")
    c1, c2, c3 = st.columns(3)
    with c1:
        card_html("Create a project", "Set source/target languages, domain, and reusable rules.", "🗂️")
    with c2:
        card_html("Run QA or Pro", "Upload a bilingual file or source file and generate review-ready output.", "🚀")
    with c3:
        card_html("Open Human Review", "Approve corrected segments and save only verified translations to TM.", "✍️")

    st.markdown("### Recent jobs")
    if st.session_state["jobs"]:
        st.dataframe(pd.DataFrame(st.session_state["jobs"][:12]), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet.")


def page_projects() -> None:
    hero("Projects", "Create localization workspaces for products, clients, domains, and target languages.", "Project management")

    with st.form("create_project"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Project name", placeholder="Mobile App UI")
        domain = c2.selectbox("Domain", ["Software UI", "Marketing", "Legal", "Medical", "E-learning", "General"])
        source_lang = c1.selectbox("Source language", ["English", "Telugu", "Hindi", "French", "Spanish"])
        targets = c2.multiselect("Target languages", SUPPORTED_API_LANGUAGES, default=["French"])
        submit = st.form_submit_button("Create project", use_container_width=True, type="primary")

    if submit and name:
        project = {
            "id": new_id("project"),
            "name": name,
            "domain": domain,
            "source_language": source_lang,
            "target_languages": ", ".join(targets),
            "created_at": now_iso(),
            "status": "Active",
        }
        st.session_state["projects"].insert(0, project)
        st.session_state["active_project_id"] = project["id"]
        st.success("Project created.")

    if st.session_state["projects"]:
        st.dataframe(pd.DataFrame(st.session_state["projects"]), use_container_width=True, hide_index=True)
        options = {p["name"]: p["id"] for p in st.session_state["projects"]}
        selected = st.selectbox("Set active project", list(options.keys()))
        if st.button("Use selected project", use_container_width=True):
            st.session_state["active_project_id"] = options[selected]
            st.rerun()
    else:
        st.info("No projects created yet.")


def page_jobs() -> None:
    hero("Jobs", "Track every upload, QA run, Pro translation, human review, and scorecard in one place.", "Workflow history")
    if not st.session_state["jobs"]:
        st.info("No jobs yet.")
        return
    df = pd.DataFrame(st.session_state["jobs"])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download job history CSV", dataframe_download(df), file_name="errorsweep_jobs.csv", mime="text/csv", use_container_width=True)


def page_qa() -> None:
    hero("ErrorSweep QA", "Review existing translations against placeholders, numbers, DNT, glossary, and API-based QA.", "QA workflow")
    render_upload_workflow(mode="qa")


def page_pro() -> None:
    hero("ErrorSweep Pro", "Translate source content using the main API, run QA, and send uncertain rows to Human Review.", "Translation workflow")
    render_upload_workflow(mode="pro")


def render_upload_workflow(mode: str) -> None:
    client = get_openai_client()
    if client is None:
        st.error("Main API is not configured. Add OPENAI_API_KEY in Streamlit secrets.")
        return

    project = active_project()
    default_target = "French"
    default_domain = project["domain"] if project else "Software UI"

    c1, c2, c3 = st.columns(3)
    domain = c1.selectbox("Domain", ["Software UI", "Marketing", "Legal", "Medical", "E-learning", "General"], index=["Software UI", "Marketing", "Legal", "Medical", "E-learning", "General"].index(default_domain) if default_domain in ["Software UI", "Marketing", "Legal", "Medical", "E-learning", "General"] else 0)
    target_language = c2.selectbox("Target language", SUPPORTED_API_LANGUAGES, index=SUPPORTED_API_LANGUAGES.index(default_target))
    batch_size = c3.number_input("Batch size", min_value=5, max_value=50, value=20)

    uploaded = st.file_uploader("Upload file", type=["xlsx", "csv", "docx", "txt", "json", "xml", "xlf", "xliff"], key=f"{mode}_upload")
    rules_zip = st.file_uploader("Upload Rules ZIP (optional)", type=["zip"], key=f"{mode}_rules")
    rules = parse_rules_zip(rules_zip) if rules_zip else {"raw": "", "glossary": [], "dnt": []}
    rules_text = rules_text_for_prompt(rules)

    if rules_zip:
        with st.expander("Rule pack summary", expanded=False):
            st.write(f"Glossary-like entries: {len(rules.get('glossary', []))}")
            st.write(f"DNT-like entries: {len(rules.get('dnt', []))}")
            st.text_area("Rule context preview", rules.get("raw", "")[:2000], height=160)

    run_label = "Run QA" if mode == "qa" else "Run Translate + Review"
    if st.button(run_label, type="primary", use_container_width=True, disabled=uploaded is None):
        if uploaded is None:
            st.stop()

        start = time.time()
        segments, context = extract_segments(uploaded, mode=mode)
        if not segments:
            st.error("No usable segments found.")
            st.stop()

        st.success(f"Extracted {len(segments)} segment(s).")
        progress = st.progress(0)
        status = st.empty()

        translations_by_loc = {seg["location"]: seg.get("translation", "") for seg in segments}
        issues: List[Dict[str, Any]] = []
        human_review_required = False
        missing_rows: List[Dict[str, str]] = []
        output_bytes = b""
        output_name = ""
        output_mime = "text/csv"

        if mode == "pro":
            for b, i in enumerate(range(0, len(segments), int(batch_size)), start=1):
                batch = segments[i:i + int(batch_size)]
                status.text(f"Translation batch {b}...")
                try:
                    results = translate_batch_api(client, batch, target_language, domain, rules_text)
                    for item in results:
                        translations_by_loc[item["location"]] = item["translation"]
                except Exception as exc:
                    st.warning(f"Translation batch failed: {exc}")
                progress.progress(min(0.45, (i + len(batch)) / len(segments) * 0.45))

            allow_download, human_review_required, missing_rows, missing_rate = smart_completion_gate(segments, translations_by_loc)
            if not allow_download:
                st.error(
                    f"Translation coverage failed: {len(missing_rows)}/{len(segments)} segment(s) "
                    f"({missing_rate:.1%}) are blank, placeholder-only, or clearly untranslated. Download blocked."
                )
                st.dataframe(pd.DataFrame(missing_rows), use_container_width=True, hide_index=True)
                add_job({
                    "id": new_id("job"),
                    "type": "Pro Translation",
                    "file": uploaded.name,
                    "target": target_language,
                    "status": "Blocked",
                    "segments": len(segments),
                    "issues": len(missing_rows),
                    "created_at": now_iso(),
                })
                st.stop()
            elif human_review_required:
                st.warning(
                    f"Translation mostly completed, but {len(missing_rows)}/{len(segments)} segment(s) "
                    f"({missing_rate:.1%}) need Human Review. Download is allowed for review, not final delivery."
                )
                st.dataframe(pd.DataFrame(missing_rows), use_container_width=True, hide_index=True)

            translated_segments = [{**seg, "translation": translations_by_loc.get(seg["location"], "")} for seg in segments]
        else:
            translated_segments = segments

        # Deterministic + API QA
        for seg in translated_segments:
            issues.extend(deterministic_issues(seg, rules))
        progress.progress(0.60)
        for b, i in enumerate(range(0, len(translated_segments), int(batch_size)), start=1):
            batch = translated_segments[i:i + int(batch_size)]
            status.text(f"QA batch {b}...")
            try:
                issues.extend(qa_batch_api(client, batch, domain, rules_text))
            except Exception as exc:
                st.warning(f"QA batch failed: {exc}")
            progress.progress(min(0.95, 0.60 + (i + len(batch)) / len(translated_segments) * 0.35))

        progress.progress(1.0)
        status.text(f"Completed in {round(time.time() - start, 1)} seconds.")

        status_rows = make_status_rows(translated_segments, translations_by_loc, issues)

        if mode == "pro":
            output_bytes, output_name, output_mime = build_output_file(context, segments, translations_by_loc)
        else:
            output_bytes = issues_excel(issues, status_rows)
            output_name = f"errorsweep_qa_{re.sub(r'\\.[^.]+$', '', uploaded.name)}.xlsx"
            output_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        job = {
            "id": new_id("job"),
            "type": "QA" if mode == "qa" else "Pro Translation",
            "file": uploaded.name,
            "target": target_language if mode == "pro" else "",
            "status": "Needs Human Review" if human_review_required or issues else "Completed",
            "segments": len(segments),
            "issues": len(issues) + len(missing_rows),
            "created_at": now_iso(),
        }
        add_job(job)

        review_session = {
            "id": new_id("review"),
            "job_id": job["id"],
            "name": f"{job['type']} · {uploaded.name}",
            "target_language": target_language,
            "status": "Needs Review" if human_review_required or issues else "Completed",
            "segments": [
                {
                    "Location": seg["location"],
                    "Source": seg["source"],
                    "Target": translations_by_loc.get(seg["location"], seg.get("translation", "")),
                    "Status": "Needs Review" if translations_by_loc.get(seg["location"], "") == NEEDS_REVIEW_MARKER else "Draft",
                    "Comment": "",
                }
                for seg in segments
            ],
            "created_at": now_iso(),
        }
        st.session_state["review_sessions"].insert(0, review_session)

        st.markdown("### Results")
        c1, c2, c3 = st.columns(3)
        c1.metric("Segments", len(segments))
        c2.metric("Issues", len(issues))
        c3.metric("Review required", "Yes" if human_review_required or issues else "No")

        st.dataframe(pd.DataFrame(status_rows).head(200), use_container_width=True, hide_index=True)

        if issues:
            with st.expander("Issue details", expanded=True):
                st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)

        if human_review_required or issues:
            st.warning("Human Review is recommended before final delivery.")
            if st.button("Open Human Review", use_container_width=True):
                st.session_state["nav_override"] = "Human Review"
                st.rerun()

        st.download_button("Download Output", output_bytes, output_name, output_mime, use_container_width=True)
        st.download_button("Download Segment Review CSV", dataframe_download(pd.DataFrame(status_rows)), "segment_review.csv", "text/csv", use_container_width=True)


def page_human_review() -> None:
    hero("Human Review", "CAT-style review workspace with source, editable target, QA issues, glossary, DNT, and TM context.", "Reviewer workspace")

    sessions = st.session_state["review_sessions"]
    if not sessions:
        st.info("No review sessions yet. Run QA or Pro first.")
        return

    session_names = [f"{s['name']} · {s['id']}" for s in sessions]
    selected_label = st.selectbox("Review session", session_names)
    session = sessions[session_names.index(selected_label)]
    segments = session["segments"]

    idx = st.number_input("Segment", min_value=1, max_value=max(len(segments), 1), value=1) - 1
    seg = segments[idx]

    left, center, right = st.columns([1.2, 1.4, 1.0])
    with left:
        st.markdown("#### Source")
        st.text_area("Source text", seg["Source"], height=220, disabled=True)
        st.markdown(badge(f"Location: {seg['Location']}", "blue"), unsafe_allow_html=True)
    with center:
        st.markdown("#### Target")
        edited = st.text_area("Editable target", seg["Target"], height=220)
        c1, c2, c3 = st.columns(3)
        if c1.button("Save", use_container_width=True):
            seg["Target"] = edited
            seg["Status"] = "Saved"
            st.success("Saved.")
        if c2.button("Approve", use_container_width=True):
            seg["Target"] = edited
            seg["Status"] = "Approved"
            st.success("Approved.")
        if c3.button("Needs Rework", use_container_width=True):
            seg["Target"] = edited
            seg["Status"] = "Needs Rework"
            st.warning("Marked needs rework.")
        comment = st.text_input("Reviewer comment", value=seg.get("Comment", ""))
        if st.button("Save comment", use_container_width=True):
            seg["Comment"] = comment
            st.success("Comment saved.")

        if st.button("Approve & Save to TM", use_container_width=True, type="primary"):
            seg["Target"] = edited
            seg["Status"] = "Approved"
            st.session_state["translation_memory"].insert(0, {
                "source": seg["Source"],
                "target": edited,
                "target_language": session.get("target_language", ""),
                "project": active_project()["name"] if active_project() else "",
                "approved_at": now_iso(),
                "approved_by": st.session_state.get("user_email", "reviewer"),
            })
            st.success("Approved and saved to TM.")

    with right:
        st.markdown("#### Context")
        st.markdown("**Glossary**")
        matching_glossary = [g for g in st.session_state["glossary"] if g.get("source", "").lower() in seg["Source"].lower()]
        if matching_glossary:
            st.dataframe(pd.DataFrame(matching_glossary), use_container_width=True, hide_index=True)
        else:
            st.caption("No glossary matches.")

        st.markdown("**DNT**")
        matching_dnt = [d for d in st.session_state["dnt_terms"] if d.get("term", "").lower() in seg["Source"].lower()]
        if matching_dnt:
            st.dataframe(pd.DataFrame(matching_dnt), use_container_width=True, hide_index=True)
        else:
            st.caption("No DNT matches.")

        st.markdown("**TM matches**")
        tm_matches = [tm for tm in st.session_state["translation_memory"] if tm.get("source", "").strip().lower() == seg["Source"].strip().lower()]
        if tm_matches:
            st.dataframe(pd.DataFrame(tm_matches[:5]), use_container_width=True, hide_index=True)
        else:
            st.caption("No exact TM match.")

    st.markdown("### Session progress")
    df = pd.DataFrame(segments)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download Human Review CSV", dataframe_download(df), "human_review_export.csv", "text/csv", use_container_width=True)


def page_scorecards() -> None:
    hero("Translator Scorecards", "Compare translator output against reviewer/final output and generate quality scores.", "LQA scoring")

    st.info("Upload files with Source and Translation/Target columns, or simple CSV/XLSX tables.")
    c1, c2 = st.columns(2)
    translator_file = c1.file_uploader("Translator file", type=["xlsx", "csv", "docx", "txt"], key="translator_file")
    reviewer_file = c2.file_uploader("Reviewer / final file", type=["xlsx", "csv", "docx", "txt"], key="reviewer_file")

    if st.button("Generate Scorecard", use_container_width=True, type="primary", disabled=not (translator_file and reviewer_file)):
        t_segments, _ = extract_segments(translator_file, mode="qa")
        r_segments, _ = extract_segments(reviewer_file, mode="qa")
        rows = []
        total_penalty = 0
        changed = 0
        for i, t in enumerate(t_segments):
            r = r_segments[i] if i < len(r_segments) else {}
            trans = t.get("translation") or t.get("source", "")
            final = r.get("translation") or r.get("source", "")
            source = t.get("source") or r.get("source", "")
            if norm(trans) == norm(final):
                severity = "Pass"
                penalty = 0
                change_type = "Unchanged"
            else:
                changed += 1
                penalty = 1
                severity = "Minor"
                change_type = "Changed"
                if not trans.strip() or PLACEHOLDER_RE.findall(source) != PLACEHOLDER_RE.findall(final):
                    severity = "Major"
                    penalty = 5
                if not final.strip():
                    severity = "Critical"
                    penalty = 10
            total_penalty += penalty
            rows.append({
                "Segment": i + 1,
                "Source": source,
                "Translator Translation": trans,
                "Reviewer Translation": final,
                "Change Type": change_type,
                "Severity": severity,
                "Penalty": penalty,
            })

        score = max(0, round(100 - (total_penalty / max(len(rows), 1) * 3), 2))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score", f"{score}/100")
        c2.metric("Segments", len(rows))
        c3.metric("Changed", changed)
        c4.metric("Penalty", total_penalty)
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            pd.DataFrame([{"Score": score, "Segments": len(rows), "Changed": changed, "Penalty": total_penalty}]).to_excel(writer, index=False, sheet_name="Summary")
            df.to_excel(writer, index=False, sheet_name="Segment Comparison")
        st.download_button("Download Scorecard", bio.getvalue(), "translator_scorecard.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def page_memory_rules() -> None:
    hero("Memory & Rules", "Manage translation memory, glossary, do-not-translate terms, and client rule packs.", "Knowledge base")

    tab_tm, tab_glossary, tab_dnt, tab_style = st.tabs(["Translation Memory", "Glossary", "DNT", "Style Guides"])

    with tab_tm:
        st.markdown("### Approved Translation Memory")
        if st.session_state["translation_memory"]:
            st.dataframe(pd.DataFrame(st.session_state["translation_memory"]), use_container_width=True, hide_index=True)
        else:
            st.info("No approved TM entries yet.")
        with st.form("manual_tm"):
            source = st.text_input("Source")
            target = st.text_input("Target")
            lang = st.selectbox("Target language", SUPPORTED_API_LANGUAGES)
            if st.form_submit_button("Add TM entry", use_container_width=True):
                if source and target:
                    st.session_state["translation_memory"].insert(0, {"source": source, "target": target, "target_language": lang, "approved_at": now_iso()})
                    st.success("TM added.")

    with tab_glossary:
        with st.form("glossary_form"):
            source = st.text_input("Source term")
            target = st.text_input("Target term")
            notes = st.text_input("Notes")
            if st.form_submit_button("Add glossary term", use_container_width=True):
                if source and target:
                    st.session_state["glossary"].insert(0, {"source": source, "target": target, "notes": notes})
                    st.success("Glossary term added.")
        if st.session_state["glossary"]:
            st.dataframe(pd.DataFrame(st.session_state["glossary"]), use_container_width=True, hide_index=True)

    with tab_dnt:
        with st.form("dnt_form"):
            term = st.text_input("Do-not-translate term")
            reason = st.text_input("Reason")
            if st.form_submit_button("Add DNT term", use_container_width=True):
                if term:
                    st.session_state["dnt_terms"].insert(0, {"term": term, "reason": reason})
                    st.success("DNT term added.")
        if st.session_state["dnt_terms"]:
            st.dataframe(pd.DataFrame(st.session_state["dnt_terms"]), use_container_width=True, hide_index=True)

    with tab_style:
        st.text_area("Style guide notes", height=220, key="style_guide_notes")
        st.caption("These notes will be used as project/client style context in future persistent storage.")


def page_team_roles() -> None:
    hero("Team & Roles", "Manage access levels for owners, admins, project managers, translators, reviewers, and clients.", "Access control")

    with st.form("add_member"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name")
        email = c2.text_input("Email")
        role = c3.selectbox("Role", list(ROLE_PERMISSIONS.keys()))
        submit = st.form_submit_button("Add team member", use_container_width=True)
    if submit and name and email:
        st.session_state["team"].append({"name": name, "email": email, "role": role, "status": "Invited"})
        st.success("Team member added.")

    st.dataframe(pd.DataFrame(st.session_state["team"]), use_container_width=True, hide_index=True)

    st.markdown("### Permission matrix")
    pages = list(PAGE_META.keys())
    matrix = []
    for role, perms in ROLE_PERMISSIONS.items():
        row = {"Role": role}
        for label in pages:
            perm, _ = PAGE_META[label]
            row[label] = "Yes" if perm in perms else "No"
        matrix.append(row)
    st.dataframe(pd.DataFrame(matrix), use_container_width=True, hide_index=True)


def page_billing() -> None:
    hero("Billing", "Plans, usage, and credits. Billing integration can connect to Razorpay/Stripe later.", "Commercial")
    st.markdown(
        """
<div class="es-grid">
  <div class="es-card"><h3>Starter</h3><p class="es-muted">QA reports, rule packs, and limited Pro jobs.</p><h2>₹0 / testing</h2></div>
  <div class="es-card"><h3>Pro</h3><p class="es-muted">Pro translation, human review, TM, scorecards.</p><h2>Coming soon</h2></div>
  <div class="es-card"><h3>Enterprise</h3><p class="es-muted">Private deployment, SSO, audit logs, custom engines.</p><h2>Custom</h2></div>
</div>
""",
        unsafe_allow_html=True,
    )


def page_account() -> None:
    hero("Account", "Profile, security, workspace, and session settings.", "Settings")
    st.write("Signed in as:", st.session_state.get("user_email", "demo"))
    st.write("Active role:", st.session_state.get("active_role"))
    st.write("Organization:", st.session_state.get("active_org"))
    if st.button("Clear local demo data", use_container_width=True):
        for key in ("projects", "jobs", "review_sessions", "translation_memory", "glossary", "dnt_terms"):
            st.session_state[key] = []
        st.success("Local demo data cleared.")


def page_admin() -> None:
    hero("Admin", "System configuration, platform controls, diagnostics, and future tenant administration.", "Admin")
    st.markdown("### Configuration")
    rows = [
        {"Setting": "OPENAI_API_KEY", "Status": "Configured" if get_secret("OPENAI_API_KEY") else "Missing"},
        {"Setting": "SUPABASE_URL", "Status": "Configured" if get_secret("SUPABASE_URL") else "Missing"},
        {"Setting": "LIBRETRANSLATE_ENDPOINT", "Status": "Optional / configured" if get_secret("LIBRETRANSLATE_ENDPOINT") else "Optional / empty"},
        {"Setting": "INDICTRANS2_ENDPOINT", "Status": "Optional / configured" if get_secret("INDICTRANS2_ENDPOINT") else "Optional / empty"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_engine_status() -> None:
    hero("Engine Status", "The main API is primary. LibreTranslate and IndicTrans2 are optional connectors for later performance testing.", "Engine registry")

    rows = []
    rows.append({
        "Engine": "Main API",
        "Endpoint": "OpenAI API",
        "Status": "Ready" if get_secret("OPENAI_API_KEY") else "Missing key",
        "Used For": "QA, Pro translation, review",
    })

    libre = get_secret("LIBRETRANSLATE_ENDPOINT")
    if libre:
        try:
            r = requests.get(libre.rstrip("/") + "/languages", timeout=10)
            status = f"HTTP {r.status_code}"
        except Exception as exc:
            status = f"Error: {exc}"
    else:
        status = "Not configured"
    rows.append({"Engine": "LibreTranslate", "Endpoint": libre or "", "Status": status, "Used For": "Optional later"})

    indic = get_secret("INDICTRANS2_ENDPOINT")
    if indic:
        base = indic.replace("/translate", "").rstrip("/")
        try:
            r = requests.get(base + "/health", timeout=10)
            status = f"HTTP {r.status_code}"
        except Exception as exc:
            status = f"Error: {exc}"
    else:
        status = "Not configured"
    rows.append({"Engine": "IndicTrans2", "Endpoint": indic or "", "Status": status, "Used For": "Optional later"})

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.info("For now, build and test the platform with the Main API. Re-enable local/free engines only after their direct /translate tests are stable.")


# ==========================================================
# Main
# ==========================================================

def main() -> None:
    inject_css()
    init_state()
    require_auth()

    if "nav_override" in st.session_state:
        page = st.session_state.pop("nav_override")
    else:
        page = sidebar_nav()

    page_func = {
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
        "Engine Status": page_engine_status,
    }.get(page, page_dashboard)

    page_func()

    st.markdown(f'<div class="es-footer-note">ErrorSweep {APP_VERSION} · Main API-first platform mode · Local/free engines optional.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()