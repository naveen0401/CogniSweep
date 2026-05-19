from __future__ import annotations

import base64
import csv
import difflib
import hashlib
import hmac
import io
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from docx import Document
from openpyxl import load_workbook

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ==========================================================
# ErrorSweep Platform v24
# Platform-owner console + workspace-user separation
# ==========================================================

st.set_page_config(
    page_title="ErrorSweep",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_VERSION = "v24 Owner Console"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
SESSION_QUERY_KEY = "es_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

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
]

OWNER_ONLY_PAGES = [
    "Owner Console",
    "Payments Received",
    "User Access Matrix",
    "All Workspaces",
    "Platform Settings",
    "Platform Audit Logs",
]

ALL_PAGES = OWNER_ONLY_PAGES + WORKSPACE_PAGES

ROLES = [
    "Platform Owner",
    "Workspace Owner",
    "Workspace Admin",
    "Project Manager",
    "Translator",
    "Reviewer",
    "Client Viewer",
    "Billing Admin",
]

ROLE_ACCESS = {
    "Platform Owner": OWNER_ONLY_PAGES + WORKSPACE_PAGES,
    "Workspace Owner": WORKSPACE_PAGES,
    "Workspace Admin": [p for p in WORKSPACE_PAGES if p not in {"Billing"}],
    "Project Manager": ["Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Human Review", "Scorecards", "Memory & Rules", "Account"],
    "Translator": ["Dashboard", "Jobs", "ErrorSweep Pro", "Human Review", "Memory & Rules", "Account"],
    "Reviewer": ["Dashboard", "Jobs", "ErrorSweep QA", "Human Review", "Scorecards", "Memory & Rules", "Account"],
    "Client Viewer": ["Dashboard", "Jobs", "Scorecards", "Account"],
    "Billing Admin": ["Dashboard", "Billing", "Account"],
}

SUPPORTED_LANGUAGES = [
    "French", "Spanish", "German", "Italian", "Portuguese", "Arabic", "Chinese",
    "Japanese", "Korean", "Russian", "Telugu", "Hindi", "Tamil", "Malayalam",
    "Kannada", "Bengali", "Marathi", "Gujarati", "Urdu", "English",
]

DOMAINS = [
    "Auto-detect", "Software UI", "Marketing", "Legal", "Medical", "E-learning",
    "Subtitles", "Gaming", "Finance", "General",
]

PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[sd]|\$\w+|<[^>]+>)")
NUMBER_RE = re.compile(r"\d+(?:[.,:]\d+)*")

# ==========================================================
# Styling
# ==========================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');
:root{
  --bg:#070913;
  --panel:#101424;
  --panel2:#151a2e;
  --line:rgba(125,145,255,.22);
  --text:#f5f7fb;
  --muted:#9aa6c7;
  --green:#00e785;
  --cyan:#35bdf7;
  --purple:#8b5cf6;
  --red:#ff4d6d;
  --yellow:#fbbf24;
}
html, body, [class*="css"] { font-family:'DM Sans', sans-serif; }
.stApp {
  background:
    radial-gradient(circle at 10% 16%, rgba(0,231,133,.12), transparent 30%),
    radial-gradient(circle at 90% 10%, rgba(53,189,247,.11), transparent 32%),
    radial-gradient(circle at 52% 100%, rgba(139,92,246,.12), transparent 45%),
    var(--bg);
  color:var(--text);
}
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stDeployButton"], .stAppDeployButton, [data-testid="stStatusWidget"] {
  visibility:hidden!important; display:none!important;
}
section[data-testid="stSidebar"] { display:none!important; }
.block-container { padding-top:28px!important; max-width:1480px!important; }
.es-card {
  background:rgba(16,20,36,.78);
  border:1px solid rgba(125,145,255,.20);
  border-radius:22px;
  padding:20px 22px;
  box-shadow:0 20px 60px rgba(0,0,0,.22);
}
.es-hero {
  background:
    linear-gradient(135deg, rgba(0,231,133,.14), rgba(53,189,247,.08) 45%, rgba(139,92,246,.18)),
    rgba(16,20,36,.80);
  border:1px solid rgba(53,189,247,.28);
  border-radius:24px;
  padding:32px;
  margin:18px 0 22px 0;
}
.es-eyebrow {
  display:inline-flex; align-items:center; gap:6px;
  padding:5px 11px; border-radius:999px;
  color:#9fffd1; background:rgba(0,231,133,.10);
  border:1px solid rgba(0,231,133,.25);
  font-family:'Space Mono', monospace; font-size:12px; font-weight:700;
  text-transform:uppercase;
}
.es-title {font-size:36px; line-height:1.05; font-weight:900; letter-spacing:-.7px; margin:16px 0 8px 0;}
.es-sub {color:#c5d0f0; font-size:15px; max-width:860px;}
.es-brand-row {display:flex; align-items:center; justify-content:space-between; gap:18px; flex-wrap:wrap;}
.es-brand {font-size:22px; font-weight:900;}
.es-brand small {display:block; color:var(--muted); font-size:12px; font-weight:500; margin-top:4px;}
.es-pill {display:inline-block; padding:5px 11px; border-radius:999px; color:#9fffd1; background:rgba(0,231,133,.10); border:1px solid rgba(0,231,133,.25); font-size:12px; font-weight:800;}
.es-pill-yellow {display:inline-block; padding:5px 11px; border-radius:999px; color:#fde68a; background:rgba(251,191,36,.10); border:1px solid rgba(251,191,36,.25); font-size:12px; font-weight:800;}
.es-grid-4 {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:12px 0 18px 0;}
.es-grid-3 {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin:12px 0 18px 0;}
.es-metric {background:rgba(16,20,36,.76); border:1px solid rgba(125,145,255,.18); border-radius:18px; padding:17px; min-height:104px;}
.es-label {font-family:'Space Mono', monospace; font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#aab4df;}
.es-value {font-size:28px; font-weight:900; margin-top:8px; color:#fff;}
.es-help {color:#9aa6c7; font-size:13px; margin-top:5px;}
.es-section-title {font-size:24px; font-weight:900; margin:22px 0 12px 0;}
.es-note {background:rgba(31,41,85,.65); color:#b7c7ff; padding:13px 16px; border-radius:14px; border:1px solid rgba(125,145,255,.16); margin:10px 0;}
.es-danger {background:rgba(255,77,109,.12); border:1px solid rgba(255,77,109,.25); color:#ffd1dc; padding:13px 16px; border-radius:14px; margin:10px 0;}
.es-ok {background:rgba(0,231,133,.10); border:1px solid rgba(0,231,133,.25); color:#bafbd7; padding:13px 16px; border-radius:14px; margin:10px 0;}
button[kind="primary"], .stButton > button, .stDownloadButton > button {
  border-radius:14px!important;
  border:1px solid rgba(0,231,133,.25)!important;
  background:linear-gradient(90deg,#00cc6a,#0ea5e9)!important;
  color:white!important; font-weight:800!important;
}
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
  border-radius:12px!important;
}
[data-testid="stFileUploader"] {background:rgba(16,20,36,.72); border:1px solid rgba(125,145,255,.16); border-radius:16px; padding:8px 12px;}
@media (max-width: 900px){ .es-grid-4,.es-grid-3{grid-template-columns:1fr;} .es-title{font-size:30px;} }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ==========================================================
# Small helpers
# ==========================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_label() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def secret(name: str, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ.get(name, default)
    try:
        value = st.secrets.get(name, default)
        return value if value is not None else default
    except Exception:
        return default


def allow_demo_login() -> bool:
    return str(secret("ERRORSWEEP_ALLOW_DEMO_LOGIN", "true")).lower() in {"1", "true", "yes", "on"}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\u00A0", " ").strip()


def safe_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def csv_bytes(rows: List[Dict[str, Any]]) -> bytes:
    return safe_df(rows).to_csv(index=False).encode("utf-8-sig")


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().lower().encode("utf-8")).hexdigest()[:16]


def extract_placeholders(text: str) -> List[str]:
    return PLACEHOLDER_RE.findall(text or "")


def extract_numbers(text: str) -> List[str]:
    return NUMBER_RE.findall(text or "")


def is_owner() -> bool:
    return st.session_state.get("role") == "Platform Owner"


def has_page_access(page: str) -> bool:
    return page in ROLE_ACCESS.get(st.session_state.get("role", "Client Viewer"), [])


def format_money(amount: float, currency: str = "USD") -> str:
    symbol = {"USD": "$", "EUR": "€", "INR": "₹", "GBP": "£"}.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"


def htmlesc(value: Any) -> str:
    return escape(str(value))

# ==========================================================
# Session persistence
# ==========================================================

def session_secret() -> str:
    return (
        secret("ERRORSWEEP_SESSION_SECRET", "")
        or secret("ERRORSWEEP_OWNER_PASSWORD", "")
        or secret("OPENAI_API_KEY", "")
        or "errorsweep-development-session-secret"
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("utf-8"))


def make_session_token(username: str, role: str, workspace_id: str) -> str:
    payload = {
        "u": username,
        "r": role,
        "w": workspace_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(session_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(session_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def set_url_session() -> None:
    try:
        st.query_params[SESSION_QUERY_KEY] = make_session_token(
            st.session_state.username,
            st.session_state.role,
            st.session_state.workspace_id,
        )
    except Exception:
        pass


def clear_url_session() -> None:
    try:
        if SESSION_QUERY_KEY in st.query_params:
            del st.query_params[SESSION_QUERY_KEY]
    except Exception:
        pass

# ==========================================================
# Initial state
# ==========================================================

def init_state() -> None:
    defaults = {
        "authenticated": False,
        "username": "",
        "role": "Client Viewer",
        "workspace_id": "ws_demo",
        "workspace_name": "Demo Workspace",
        "active_page": "Dashboard",
        "projects": [],
        "jobs": [],
        "review_segments": [],
        "tm_entries": [],
        "glossary": [],
        "dnt_terms": [],
        "team": [],
        "platform_payments": [],
        "platform_workspaces": [],
        "platform_users": [],
        "platform_audit_logs": [],
        "feature_flags": {},
        "owner_notes": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.platform_workspaces:
        st.session_state.platform_workspaces = [
            {"Workspace ID": "ws_demo", "Workspace": "Demo Workspace", "Owner Email": "admin@client.local", "Plan": "Trial", "Status": "Active", "Users": 4, "Jobs": 0, "Created": today_label()},
            {"Workspace ID": "ws_acme", "Workspace": "Acme Localization", "Owner Email": "pm@acme.local", "Plan": "Pro", "Status": "Active", "Users": 7, "Jobs": 18, "Created": (datetime.now() - timedelta(days=16)).strftime("%Y-%m-%d")},
        ]
    if not st.session_state.platform_users:
        st.session_state.platform_users = [
            {"User ID": "u_owner", "Email": "owner@errorsweep.local", "Name": "Platform Owner", "Workspace": "Platform", "Role": "Platform Owner", "Plan": "Internal", "Status": "Active", "Last Login": now_iso(), "Allowed Pages": ", ".join(OWNER_ONLY_PAGES + WORKSPACE_PAGES)},
            {"User ID": "u_admin", "Email": "admin@client.local", "Name": "Workspace Admin", "Workspace": "Demo Workspace", "Role": "Workspace Admin", "Plan": "Trial", "Status": "Active", "Last Login": now_iso(), "Allowed Pages": ", ".join(ROLE_ACCESS["Workspace Admin"])},
            {"User ID": "u_reviewer", "Email": "reviewer@client.local", "Name": "Reviewer", "Workspace": "Demo Workspace", "Role": "Reviewer", "Plan": "Trial", "Status": "Active", "Last Login": "", "Allowed Pages": ", ".join(ROLE_ACCESS["Reviewer"])},
            {"User ID": "u_client", "Email": "client@client.local", "Name": "Client Viewer", "Workspace": "Demo Workspace", "Role": "Client Viewer", "Plan": "Trial", "Status": "Active", "Last Login": "", "Allowed Pages": ", ".join(ROLE_ACCESS["Client Viewer"])},
        ]
    if not st.session_state.platform_payments:
        st.session_state.platform_payments = [
            {"Payment ID": "pay_demo_001", "Date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"), "Workspace": "Acme Localization", "User Email": "pm@acme.local", "Plan": "Pro", "Amount": 29.00, "Currency": "USD", "Gateway": "Manual", "Status": "Paid", "Access Granted": "Pro"},
            {"Payment ID": "pay_demo_002", "Date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"), "Workspace": "Beta Agency", "User Email": "owner@beta.local", "Plan": "Agency", "Amount": 99.00, "Currency": "USD", "Gateway": "Manual", "Status": "Pending", "Access Granted": "Pending"},
        ]
    if not st.session_state.feature_flags:
        st.session_state.feature_flags = {
            "Main API Translation": True,
            "Human Review": True,
            "Scorecards": True,
            "Self-hosted engines": False,
            "Billing collection": False,
            "Public registration": False,
        }
    if not st.session_state.team:
        st.session_state.team = [
            {"Name": "Workspace Admin", "Email": "admin@client.local", "Role": "Workspace Admin", "Status": "Active"},
            {"Name": "Reviewer", "Email": "reviewer@client.local", "Role": "Reviewer", "Status": "Invited"},
        ]


def log_audit(action: str, detail: str) -> None:
    st.session_state.platform_audit_logs.insert(0, {
        "Time": now_iso(),
        "Actor": st.session_state.get("username", "system"),
        "Role": st.session_state.get("role", "system"),
        "Action": action,
        "Detail": detail,
    })


def restore_session_from_url() -> None:
    if st.session_state.get("authenticated"):
        return
    try:
        token = st.query_params.get(SESSION_QUERY_KEY, "")
    except Exception:
        token = ""
    if isinstance(token, list):
        token = token[0] if token else ""
    if not token:
        return
    payload = verify_session_token(str(token))
    if not payload:
        clear_url_session()
        return
    sign_in(payload.get("u", "user@errorsweep.local"), payload.get("r", "Client Viewer"), payload.get("w", "ws_demo"), remember=False)


def sign_in(username: str, role: str, workspace_id: str = "ws_demo", remember: bool = True) -> None:
    st.session_state.authenticated = True
    st.session_state.username = username
    st.session_state.role = role if role in ROLES else "Client Viewer"
    st.session_state.workspace_id = workspace_id
    ws = next((w for w in st.session_state.platform_workspaces if w.get("Workspace ID") == workspace_id), None)
    st.session_state.workspace_name = ws.get("Workspace", "Demo Workspace") if ws else "Demo Workspace"
    st.session_state.active_page = "Owner Console" if role == "Platform Owner" else "Dashboard"
    if remember:
        set_url_session()
    log_audit("Sign in", f"{username} signed in as {role}")


def logout() -> None:
    log_audit("Logout", f"{st.session_state.get('username', '')} logged out")
    for key in ["authenticated", "username", "role", "workspace_id", "workspace_name", "active_page"]:
        if key in st.session_state:
            del st.session_state[key]
    clear_url_session()
    st.rerun()

# ==========================================================
# File extraction
# ==========================================================

def read_uploaded_text(file) -> str:
    data = file.getvalue()
    for enc in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def detect_cols(headers: List[str]) -> Tuple[Optional[str], Optional[str]]:
    lows = {str(h).strip().lower(): h for h in headers}
    src = None
    tgt = None
    for k, v in lows.items():
        if src is None and any(x in k for x in ["source", "english", "src"]):
            src = v
        if tgt is None and any(x in k for x in ["target", "translation", "translated", "original translation"]):
            tgt = v
    return src, tgt


def extract_segments_from_file(file, assume_source_only: bool = False) -> List[Dict[str, Any]]:
    name = file.name.lower()
    segments: List[Dict[str, Any]] = []
    if name.endswith(".xlsx"):
        wb = load_workbook(io.BytesIO(file.getvalue()), data_only=True)
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            headers = [clean_text(x) for x in rows[0]]
            src_col, tgt_col = detect_cols(headers)
            if src_col and src_col in headers:
                si = headers.index(src_col)
                ti = headers.index(tgt_col) if tgt_col and tgt_col in headers else None
                for ridx, row in enumerate(rows[1:], start=2):
                    src = clean_text(row[si] if si < len(row) else "")
                    tgt = clean_text(row[ti] if ti is not None and ti < len(row) else "")
                    if src or tgt:
                        segments.append({"Segment ID": len(segments)+1, "Location": f"{ws.title}!R{ridx}", "Source": src or tgt, "Target": "" if assume_source_only else tgt, "Status": "Untranslated" if not tgt else "Existing", "Match": ""})
            else:
                for ridx, row in enumerate(rows, start=1):
                    vals = [clean_text(x) for x in row if clean_text(x)]
                    if vals:
                        segments.append({"Segment ID": len(segments)+1, "Location": f"{ws.title}!R{ridx}", "Source": vals[0], "Target": "", "Status": "Untranslated", "Match": ""})
    elif name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file.getvalue()))
        src_col, tgt_col = detect_cols(list(df.columns))
        if not src_col:
            src_col = df.columns[0]
        for i, row in df.iterrows():
            src = clean_text(row.get(src_col, ""))
            tgt = clean_text(row.get(tgt_col, "")) if tgt_col else ""
            if src or tgt:
                segments.append({"Segment ID": len(segments)+1, "Location": f"Row {i+2}", "Source": src or tgt, "Target": "" if assume_source_only else tgt, "Status": "Untranslated" if not tgt else "Existing", "Match": ""})
    elif name.endswith(".docx"):
        doc = Document(io.BytesIO(file.getvalue()))
        for tidx, table in enumerate(doc.tables, start=1):
            if not table.rows:
                continue
            headers = [clean_text(c.text) for c in table.rows[0].cells]
            src_col, tgt_col = detect_cols(headers)
            if src_col:
                si = headers.index(src_col)
                ti = headers.index(tgt_col) if tgt_col and tgt_col in headers else None
                for ridx, row in enumerate(table.rows[1:], start=2):
                    src = clean_text(row.cells[si].text if si < len(row.cells) else "")
                    tgt = clean_text(row.cells[ti].text if ti is not None and ti < len(row.cells) else "")
                    if src or tgt:
                        segments.append({"Segment ID": len(segments)+1, "Location": f"Table {tidx}, Row {ridx}", "Source": src or tgt, "Target": "" if assume_source_only else tgt, "Status": "Untranslated" if not tgt else "Existing", "Match": ""})
        if not segments:
            for i, p in enumerate(doc.paragraphs, start=1):
                txt = clean_text(p.text)
                if txt:
                    segments.append({"Segment ID": len(segments)+1, "Location": f"Paragraph {i}", "Source": txt, "Target": "", "Status": "Untranslated", "Match": ""})
    else:
        text = read_uploaded_text(file)
        nonempty = [clean_text(x) for x in text.splitlines() if clean_text(x)]
        for i, line in enumerate(nonempty, start=1):
            if line.lower() in {"source", "target", "translation"}:
                continue
            segments.append({"Segment ID": len(segments)+1, "Location": f"Line {i}", "Source": line, "Target": "", "Status": "Untranslated", "Match": ""})
    return segments

# ==========================================================
# API functions
# ==========================================================

def openai_client():
    if OpenAI is None:
        return None
    key = secret("OPENAI_API_KEY", "")
    if not key:
        return None
    return OpenAI(api_key=key)


def parse_json_list(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    t = text.strip()
    t = re.sub(r"^```json\s*", "", t, flags=re.I).strip()
    t = re.sub(r"^```\s*", "", t).strip()
    t = re.sub(r"\s*```$", "", t).strip()
    start, end = t.find("["), t.rfind("]")
    if start >= 0 and end > start:
        t = t[start:end+1]
    try:
        data = json.loads(t)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def api_translate_segments(segments: List[Dict[str, Any]], target_language: str, domain: str, rules_text: str = "") -> List[Dict[str, Any]]:
    client = openai_client()
    if client is None:
        raise RuntimeError("Main API key is not configured.")
    rows = []
    batch_size = 20
    for start in range(0, len(segments), batch_size):
        batch = segments[start:start+batch_size]
        payload = "\n".join([f"[{x['Segment ID']}] {x['Source']}" for x in batch])
        prompt = f"""
Translate these localization segments into {target_language}.
Domain: {domain}
Rules: {rules_text or 'None'}
Preserve placeholders like {{{{name}}}}, numbers, tags, URLs, emojis, and bracket structure.
Return ONLY JSON array: [{{"segment_id": 1, "translation": "...", "status": "MT", "match": "MT"}}]
Segments:
{payload}
"""
        resp = client.responses.create(
            model=secret("OPENAI_MODEL", DEFAULT_MODEL),
            instructions="You are a professional localization translator. Return valid JSON only.",
            input=prompt,
            max_output_tokens=3500,
        )
        data = parse_json_list(resp.output_text)
        by_id = {int(item.get("segment_id", -1)): item for item in data if str(item.get("segment_id", "")).isdigit()}
        for seg in batch:
            item = by_id.get(int(seg["Segment ID"]), {})
            rows.append({
                **seg,
                "Target": item.get("translation", ""),
                "Status": item.get("status", "MT") or "MT",
                "Match": item.get("match", "MT") or "MT",
            })
    return rows


def run_simple_qa(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for seg in segments:
        src = seg.get("Source", "")
        tgt = seg.get("Target", "")
        if not tgt:
            issues.append({"Segment ID": seg["Segment ID"], "Location": seg["Location"], "Issue": "Blank target", "Severity": "Major", "Suggestion": "Translate or review this segment."})
            continue
        for ph in extract_placeholders(src):
            if ph not in tgt:
                issues.append({"Segment ID": seg["Segment ID"], "Location": seg["Location"], "Issue": "Missing placeholder", "Severity": "Critical", "Suggestion": f"Preserve {ph}."})
        for num in extract_numbers(src):
            if num not in tgt:
                issues.append({"Segment ID": seg["Segment ID"], "Location": seg["Location"], "Issue": "Missing number", "Severity": "Major", "Suggestion": f"Check number {num}."})
        if src.strip().lower() == tgt.strip().lower() and len(src.strip()) > 3:
            issues.append({"Segment ID": seg["Segment ID"], "Location": seg["Location"], "Issue": "Source copied", "Severity": "Review", "Suggestion": "Confirm translation is not source copy."})
    return issues


def domain_auto_detect(segments: List[Dict[str, Any]]) -> str:
    sample = " ".join([x.get("Source", "") for x in segments[:20]]).lower()
    if any(x in sample for x in ["dashboard", "settings", "password", "upload", "account"]):
        return "Software UI"
    if any(x in sample for x in ["invoice", "payment", "bank", "amount"]):
        return "Finance"
    if any(x in sample for x in ["workout", "fitness", "calories"]):
        return "General"
    return "General"

# ==========================================================
# Rendering helpers
# ==========================================================

def page_header(label: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="es-hero">
          <span class="es-eyebrow">{htmlesc(label)}</span>
          <div class="es-title">{htmlesc(title)}</div>
          <div class="es-sub">{htmlesc(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_cards(items: List[Tuple[str, Any, str]], columns: int = 4) -> None:
    klass = "es-grid-4" if columns == 4 else "es-grid-3"
    html = [f'<div class="{klass}">']
    for label, value, help_text in items:
        html.append(f'<div class="es-metric"><div class="es-label">{htmlesc(label)}</div><div class="es-value">{htmlesc(value)}</div><div class="es-help">{htmlesc(help_text)}</div></div>')
    html.append("</div>")
    st.markdown("\n".join(html), unsafe_allow_html=True)


def allowed_pages() -> List[str]:
    role = st.session_state.get("role", "Client Viewer")
    return ROLE_ACCESS.get(role, ROLE_ACCESS["Client Viewer"])


def render_top_nav() -> str:
    pages = allowed_pages()
    current = st.session_state.get("active_page", pages[0])
    if current not in pages:
        current = pages[0]
    account_badge = "Owner" if is_owner() else st.session_state.get("role", "User")
    st.markdown(
        f"""
        <div class="es-card">
          <div class="es-brand-row">
            <div class="es-brand">🌐 ErrorSweep <small>{APP_VERSION} · signed in as {htmlesc(st.session_state.get('username',''))} · workspace: {htmlesc(st.session_state.get('workspace_name',''))}</small></div>
            <span class="es-pill">{htmlesc(account_badge)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([5, 1])
    with c1:
        selected = st.selectbox("Open page", pages, index=pages.index(current), key="nav_page")
    with c2:
        st.write("")
        st.write("")
        if st.button("Logout", use_container_width=True):
            logout()
    st.session_state.active_page = selected
    return selected

# ==========================================================
# Login
# ==========================================================

def login_page() -> None:
    page_header("Account required", "ErrorSweep", "Platform-owner controls are separated from workspace-user workflows.")
    tab_owner, tab_user, tab_demo = st.tabs(["Platform owner", "Workspace user", "Demo access"])

    with tab_owner:
        st.markdown('<div class="es-note">The platform owner account is the only account that can see all payments, all users, all workspaces, feature flags, and platform audit logs.</div>', unsafe_allow_html=True)
        with st.form("owner_login"):
            u = st.text_input("Owner email / username", value="")
            p = st.text_input("Owner password", type="password")
            if st.form_submit_button("Sign in as platform owner", use_container_width=True):
                expected_u = secret("ERRORSWEEP_OWNER_USERNAME", secret("ERRORSWEEP_USERNAME", "owner@errorsweep.local"))
                expected_p = secret("ERRORSWEEP_OWNER_PASSWORD", secret("ERRORSWEEP_PASSWORD", ""))
                if expected_p and hmac.compare_digest(u.strip(), expected_u.strip()) and hmac.compare_digest(p, expected_p):
                    sign_in(u.strip(), "Platform Owner", "platform")
                    st.rerun()
                elif allow_demo_login() and not expected_p:
                    sign_in("owner@errorsweep.local", "Platform Owner", "platform")
                    st.rerun()
                else:
                    st.error("Invalid owner credentials. Use Demo access while building, or configure owner secrets.")

    with tab_user:
        with st.form("user_login"):
            u = st.text_input("User email / username", key="user_u")
            p = st.text_input("User password", type="password", key="user_p")
            if st.form_submit_button("Sign in as workspace user", use_container_width=True):
                expected_u = secret("ERRORSWEEP_USER_USERNAME", "admin@client.local")
                expected_p = secret("ERRORSWEEP_USER_PASSWORD", "")
                default_role = secret("ERRORSWEEP_DEFAULT_USER_ROLE", "Workspace Admin")
                if expected_p and hmac.compare_digest(u.strip(), expected_u.strip()) and hmac.compare_digest(p, expected_p):
                    sign_in(u.strip(), default_role if default_role in ROLES else "Workspace Admin", "ws_demo")
                    st.rerun()
                elif allow_demo_login() and not expected_p:
                    sign_in("admin@client.local", "Workspace Admin", "ws_demo")
                    st.rerun()
                else:
                    st.error("Invalid workspace credentials.")

    with tab_demo:
        if allow_demo_login():
            st.markdown("Choose a demo role. Owner-only pages will appear only for Platform Owner.")
            role = st.selectbox("Demo role", ROLES, index=0)
            if st.button("Enter demo workspace", use_container_width=True):
                username = "owner@errorsweep.local" if role == "Platform Owner" else f"{role.lower().replace(' ', '.')}@client.local"
                workspace_id = "platform" if role == "Platform Owner" else "ws_demo"
                sign_in(username, role, workspace_id)
                st.rerun()
        else:
            st.warning("Demo access is disabled.")

# ==========================================================
# Platform owner-only pages
# ==========================================================

def owner_console_page() -> None:
    if not is_owner():
        restricted_page("Owner Console")
        return
    page_header("Platform owner only", "Owner command center", "See payments received, all users, access levels, workspaces, platform usage, and private owner controls.")
    payments = st.session_state.platform_payments
    paid_total = sum(float(p.get("Amount", 0)) for p in payments if str(p.get("Status", "")).lower() == "paid")
    pending_total = sum(float(p.get("Amount", 0)) for p in payments if str(p.get("Status", "")).lower() == "pending")
    metric_cards([
        ("Payments received", format_money(paid_total), "paid payments across all workspaces"),
        ("Pending payments", format_money(pending_total), "manual or gateway pending"),
        ("Active workspaces", sum(1 for w in st.session_state.platform_workspaces if w.get("Status") == "Active"), "customer/client workspaces"),
        ("Users", len(st.session_state.platform_users), "all platform users"),
    ])

    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.markdown("### Recent payments received")
        st.dataframe(pd.DataFrame(payments), use_container_width=True, hide_index=True)
        st.download_button("Download payment ledger", csv_bytes(payments), "errorsweep_payment_ledger.csv", "text/csv", use_container_width=True)
    with c2:
        st.markdown("### User access snapshot")
        access = [{"Email": u["Email"], "Workspace": u["Workspace"], "Role": u["Role"], "Plan": u["Plan"], "Status": u["Status"]} for u in st.session_state.platform_users]
        st.dataframe(pd.DataFrame(access), use_container_width=True, hide_index=True)
        st.markdown('<div class="es-note">These records are visible only from the platform owner account. Workspace users cannot access this console.</div>', unsafe_allow_html=True)

    st.markdown("### Owner quick actions")
    a, b, c = st.columns(3)
    if a.button("Add demo payment", use_container_width=True):
        st.session_state.platform_payments.insert(0, {
            "Payment ID": new_id("pay"), "Date": today_label(), "Workspace": "Demo Workspace", "User Email": "admin@client.local", "Plan": "Pro", "Amount": 29.00, "Currency": "USD", "Gateway": "Manual", "Status": "Paid", "Access Granted": "Pro"
        })
        log_audit("Owner payment entry", "Added demo payment")
        st.rerun()
    if b.button("Add audit event", use_container_width=True):
        log_audit("Owner note", "Manual owner audit event added")
        st.rerun()
    if c.button("Export owner data", use_container_width=True):
        st.info("Use the export buttons in Payments, User Access Matrix, and All Workspaces.")


def payments_received_page() -> None:
    if not is_owner():
        restricted_page("Payments Received")
        return
    page_header("Owner only", "Payments received", "A private ledger of payments, subscriptions, plan grants, and gateway status across all workspaces.")
    with st.expander("Add manual payment / payment adjustment", expanded=False):
        with st.form("add_payment"):
            c1, c2, c3 = st.columns(3)
            workspace = c1.text_input("Workspace", value="Demo Workspace")
            email = c2.text_input("User email", value="admin@client.local")
            plan = c3.selectbox("Plan", ["Trial", "Pro", "Agency", "Enterprise", "Custom"])
            c4, c5, c6 = st.columns(3)
            amount = c4.number_input("Amount", min_value=0.0, value=29.0, step=1.0)
            currency = c5.selectbox("Currency", ["USD", "INR", "EUR", "GBP"])
            status = c6.selectbox("Status", ["Paid", "Pending", "Failed", "Refunded"])
            if st.form_submit_button("Save payment", use_container_width=True):
                st.session_state.platform_payments.insert(0, {
                    "Payment ID": new_id("pay"), "Date": today_label(), "Workspace": workspace, "User Email": email,
                    "Plan": plan, "Amount": float(amount), "Currency": currency, "Gateway": "Manual", "Status": status,
                    "Access Granted": plan if status == "Paid" else "Pending",
                })
                log_audit("Payment saved", f"{status} {currency} {amount} for {workspace}")
                st.success("Payment saved to owner ledger.")
    df = pd.DataFrame(st.session_state.platform_payments)
    if not df.empty:
        status_filter = st.multiselect("Filter by status", sorted(df["Status"].unique()), default=list(sorted(df["Status"].unique())))
        df = df[df["Status"].isin(status_filter)]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download payment ledger CSV", df.to_csv(index=False).encode("utf-8-sig"), "payments_received.csv", "text/csv", use_container_width=True)


def user_access_matrix_page() -> None:
    if not is_owner():
        restricted_page("User Access Matrix")
        return
    page_header("Owner only", "User access matrix", "Review which user has what access, role, plan, status, last login, and allowed pages.")
    users = st.session_state.platform_users
    with st.expander("Add or update platform user", expanded=False):
        with st.form("add_platform_user"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name")
            email = c2.text_input("Email")
            workspace = c3.text_input("Workspace", value="Demo Workspace")
            c4, c5, c6 = st.columns(3)
            role = c4.selectbox("Role", ROLES, index=1)
            plan = c5.selectbox("Plan", ["Trial", "Pro", "Agency", "Enterprise", "Internal"])
            status = c6.selectbox("Status", ["Active", "Invited", "Suspended"])
            if st.form_submit_button("Save user access", use_container_width=True):
                users.insert(0, {"User ID": new_id("usr"), "Email": email, "Name": name, "Workspace": workspace, "Role": role, "Plan": plan, "Status": status, "Last Login": "", "Allowed Pages": ", ".join(ROLE_ACCESS.get(role, []))})
                log_audit("User access updated", f"{email} set to {role} in {workspace}")
                st.success("User access saved.")
    df = pd.DataFrame(users)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download user access matrix", df.to_csv(index=False).encode("utf-8-sig"), "user_access_matrix.csv", "text/csv", use_container_width=True)


def all_workspaces_page() -> None:
    if not is_owner():
        restricted_page("All Workspaces")
        return
    page_header("Owner only", "All workspaces", "Private platform-level view of every client workspace, plan, user count, and job volume.")
    with st.expander("Create workspace", expanded=False):
        with st.form("create_owner_workspace"):
            name = st.text_input("Workspace name")
            owner = st.text_input("Owner email")
            plan = st.selectbox("Plan", ["Trial", "Pro", "Agency", "Enterprise"])
            if st.form_submit_button("Create workspace", use_container_width=True):
                st.session_state.platform_workspaces.insert(0, {"Workspace ID": new_id("ws"), "Workspace": name, "Owner Email": owner, "Plan": plan, "Status": "Active", "Users": 1, "Jobs": 0, "Created": today_label()})
                log_audit("Workspace created", f"{name} created by owner")
                st.success("Workspace created.")
    df = pd.DataFrame(st.session_state.platform_workspaces)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download workspace list", df.to_csv(index=False).encode("utf-8-sig"), "all_workspaces.csv", "text/csv", use_container_width=True)


def platform_settings_page() -> None:
    if not is_owner():
        restricted_page("Platform Settings")
        return
    page_header("Owner only", "Platform settings", "Global feature flags, plan access controls, registration settings, and platform-level switches.")
    st.markdown("### Feature flags")
    for flag, current in list(st.session_state.feature_flags.items()):
        st.session_state.feature_flags[flag] = st.toggle(flag, value=bool(current), key=f"flag_{flag}")
    st.markdown("### Plan defaults")
    plan_rows = [
        {"Plan": "Trial", "Users": 1, "Projects": 1, "Monthly Jobs": 10, "Human Review": "Yes", "Scorecards": "No"},
        {"Plan": "Pro", "Users": 3, "Projects": 5, "Monthly Jobs": 100, "Human Review": "Yes", "Scorecards": "Yes"},
        {"Plan": "Agency", "Users": 20, "Projects": 50, "Monthly Jobs": 1000, "Human Review": "Yes", "Scorecards": "Yes"},
        {"Plan": "Enterprise", "Users": "Custom", "Projects": "Custom", "Monthly Jobs": "Custom", "Human Review": "Yes", "Scorecards": "Yes"},
    ]
    st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)
    st.markdown('<div class="es-note">These settings are intentionally owner-only. Workspace users cannot see or change platform-wide feature flags.</div>', unsafe_allow_html=True)


def platform_audit_logs_page() -> None:
    if not is_owner():
        restricted_page("Platform Audit Logs")
        return
    page_header("Owner only", "Platform audit logs", "Private event trail for sign-ins, payment updates, workspace creation, role changes, and owner actions.")
    df = pd.DataFrame(st.session_state.platform_audit_logs)
    if df.empty:
        st.info("No audit events yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download audit log", df.to_csv(index=False).encode("utf-8-sig"), "platform_audit_log.csv", "text/csv", use_container_width=True)


def restricted_page(page_name: str) -> None:
    page_header("Restricted", page_name, "This page is visible only to the platform owner account.")
    st.markdown('<div class="es-danger">This workspace user account cannot access platform-owner information such as payment ledgers, all-user access, all-workspace data, or platform feature controls.</div>', unsafe_allow_html=True)

# ==========================================================
# Workspace/user pages
# ==========================================================

def dashboard_page() -> None:
    page_header("Dashboard", "Localization operations hub", "Manage projects, jobs, review work, scorecards, and memory from one workspace.")
    metric_cards([
        ("Projects", len(st.session_state.projects), "workspace projects"),
        ("Jobs", len(st.session_state.jobs), "QA / Pro / Scorecard"),
        ("TM Entries", len(st.session_state.tm_entries), "approved translations"),
        ("Pending review", len([x for x in st.session_state.review_segments if x.get("Status") != "Approved"]), "segments"),
    ])
    st.markdown("### Recommended next steps")
    metric_cards([
        ("1", "Create a project", "Set languages, domain, and rules."),
        ("2", "Run QA or Pro", "Generate segments and review-ready jobs."),
        ("3", "Human Review", "Approve corrections and save verified TM."),
    ], columns=3)
    st.markdown("### Recent jobs")
    if st.session_state.jobs:
        st.dataframe(pd.DataFrame(st.session_state.jobs[:10]), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet.")


def projects_page() -> None:
    page_header("Projects", "Project workspaces", "Create client/product workspaces with source language, target languages, domain, and rules.")
    with st.form("project_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Project name")
        client = c2.text_input("Client / product")
        source = c1.selectbox("Source language", SUPPORTED_LANGUAGES, index=SUPPORTED_LANGUAGES.index("English"))
        target = c2.multiselect("Target languages", SUPPORTED_LANGUAGES, default=["French"])
        domain = st.selectbox("Default domain", DOMAINS, index=DOMAINS.index("Software UI"))
        if st.form_submit_button("Create project", use_container_width=True):
            if name:
                st.session_state.projects.insert(0, {"Project ID": new_id("prj"), "Project": name, "Client": client, "Source": source, "Targets": ", ".join(target), "Domain": domain, "Owner": st.session_state.username, "Created": today_label()})
                log_audit("Project created", name)
                st.success("Project created.")
    if st.session_state.projects:
        st.dataframe(pd.DataFrame(st.session_state.projects), use_container_width=True, hide_index=True)
    else:
        st.info("No projects yet.")


def jobs_page() -> None:
    page_header("Jobs", "Workflow history", "Track QA, Pro, Human Review, and Scorecard jobs created in this workspace.")
    if st.session_state.jobs:
        st.dataframe(pd.DataFrame(st.session_state.jobs), use_container_width=True, hide_index=True)
        st.download_button("Download jobs CSV", csv_bytes(st.session_state.jobs), "jobs.csv", "text/csv", use_container_width=True)
    else:
        st.info("No jobs yet.")


def qa_page() -> None:
    page_header("ErrorSweep QA", "Quality review", "Upload an existing bilingual file and generate deterministic QA findings.")
    file = st.file_uploader("Upload bilingual file", type=["xlsx", "csv", "docx", "txt"], key="qa_upload")
    if st.button("Run QA", type="primary", use_container_width=True, disabled=file is None):
        segments = extract_segments_from_file(file, assume_source_only=False)
        issues = run_simple_qa(segments)
        job = {"Job ID": new_id("job"), "Type": "QA", "File": file.name, "Segments": len(segments), "Issues": len(issues), "Status": "Completed", "Created": now_iso()}
        st.session_state.jobs.insert(0, job)
        st.session_state.review_segments = segments
        log_audit("QA job", f"{file.name}: {len(segments)} segments, {len(issues)} issues")
        st.success("QA completed. Segments are available in Human Review.")
        metric_cards([("Segments", len(segments), "checked"), ("Issues", len(issues), "found"), ("Status", "Completed", "sent to Human Review")], columns=3)
        if issues:
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)
            st.download_button("Download QA report", csv_bytes(issues), "qa_report.csv", "text/csv", use_container_width=True)


def pro_page() -> None:
    page_header("ErrorSweep Pro", "Translate + QA + Human Review", "Use the main API to translate, run safeguards, and route uncertain segments to review.")
    st.markdown('<div class="es-note">Source/bilingual file is required for Pro translation. For Scorecards and Human Review, the separate source file is optional.</div>', unsafe_allow_html=True)
    file = st.file_uploader("Upload source or bilingual file", type=["xlsx", "csv", "docx", "txt"], key="pro_upload")
    c1, c2, c3 = st.columns(3)
    target = c1.selectbox("Target language", SUPPORTED_LANGUAGES, index=SUPPORTED_LANGUAGES.index("French"))
    domain = c2.selectbox("Domain", DOMAINS, index=0)
    review_threshold = c3.slider("Allow with review threshold", 0, 30, 12)
    run = st.button("Run Translate + Review", type="primary", use_container_width=True, disabled=file is None)
    if run and file:
        segments = extract_segments_from_file(file, assume_source_only=True)
        actual_domain = domain_auto_detect(segments) if domain == "Auto-detect" else domain
        try:
            with st.spinner("Translating with main API..."):
                translated = api_translate_segments(segments, target, actual_domain)
        except Exception as exc:
            st.error(str(exc))
            return
        issues = run_simple_qa(translated)
        missing = [x for x in translated if not clean_text(x.get("Target"))]
        missing_rate = len(missing) / max(len(translated), 1)
        status = "Completed" if not missing else ("Needs Human Review" if missing_rate <= review_threshold / 100 else "Blocked")
        st.session_state.review_segments = translated
        st.session_state.jobs.insert(0, {"Job ID": new_id("job"), "Type": "Pro", "File": file.name, "Language": target, "Domain": actual_domain, "Segments": len(translated), "Issues": len(issues), "Status": status, "Created": now_iso()})
        log_audit("Pro job", f"{file.name}: {target}, {status}")
        metric_cards([("Segments", len(translated), "translated"), ("Missing", len(missing), "needs review"), ("Domain", actual_domain, "auto-detected" if domain == "Auto-detect" else "selected"), ("Status", status, "workflow result")])
        st.dataframe(pd.DataFrame(translated), use_container_width=True, hide_index=True)
        if status == "Blocked":
            st.markdown('<div class="es-danger">Too many blank/unusable segments. Output is blocked until reviewed.</div>', unsafe_allow_html=True)
        elif status == "Needs Human Review":
            st.markdown('<div class="es-note">Output is allowed for internal review. Open Human Review before delivery.</div>', unsafe_allow_html=True)
        st.download_button("Download translation table", csv_bytes(translated), "translated_segments.csv", "text/csv", use_container_width=True)


def best_tm_match(source: str) -> Tuple[str, str]:
    if not st.session_state.tm_entries:
        return "", ""
    choices = [x.get("Source", "") for x in st.session_state.tm_entries]
    match = difflib.get_close_matches(source, choices, n=1, cutoff=0.40)
    if not match:
        return "", ""
    entry = next((x for x in st.session_state.tm_entries if x.get("Source") == match[0]), None)
    if not entry:
        return "", ""
    ratio = int(difflib.SequenceMatcher(None, source.lower(), match[0].lower()).ratio() * 100)
    label = "101%" if source == match[0] else ("100%" if ratio >= 98 else f"{ratio}% fuzzy")
    return entry.get("Target", ""), label


def human_review_page() -> None:
    page_header("Human Review", "CAT-style segment editor", "Upload a file directly or open a generated job. Edit target text, see TM/glossary/DNT, and approve verified translations.")
    upload = st.file_uploader("Direct upload for Human Review", type=["xlsx", "csv", "docx", "txt"], key="hr_direct_upload")
    if upload and st.button("Load file into Human Review", use_container_width=True):
        st.session_state.review_segments = extract_segments_from_file(upload, assume_source_only=False)
        log_audit("Human Review upload", upload.name)
        st.success("File loaded into Human Review.")
    if not st.session_state.review_segments:
        st.info("No review segments yet. Upload a file here or run ErrorSweep QA / Pro first.")
        return

    segments = st.session_state.review_segments
    for seg in segments:
        if not seg.get("Status"):
            seg["Status"] = "Untranslated" if not seg.get("Target") else "Existing"
        if not seg.get("Match"):
            _, label = best_tm_match(seg.get("Source", ""))
            seg["Match"] = label or seg.get("Status", "")

    left, center, right = st.columns([1.1, 1.6, 1.0])
    with left:
        st.markdown("### Source segments")
        labels = [f"{s['Segment ID']}. {s.get('Match') or s.get('Status')} · {s.get('Source','')[:70]}" for s in segments]
        idx = st.radio("Select segment", range(len(segments)), format_func=lambda i: labels[i], label_visibility="collapsed")
    seg = segments[idx]
    with center:
        st.markdown(f"### Segment {seg['Segment ID']} · {seg.get('Status','')}")
        st.caption(seg.get("Location", ""))
        st.text_area("Source", value=seg.get("Source", ""), height=140, disabled=True)
        new_target = st.text_area("Target", value=seg.get("Target", ""), height=170, key=f"target_{seg['Segment ID']}")
        status = st.selectbox("Segment status", ["MT", "Existing", "Needs Review", "Approved", "Rejected", "Needs Rework", "100%", "101%", "Fuzzy %", "Untranslated"], index=0 if seg.get("Status") not in ["Approved", "Rejected", "Needs Rework"] else ["MT", "Existing", "Needs Review", "Approved", "Rejected", "Needs Rework", "100%", "101%", "Fuzzy %", "Untranslated"].index(seg.get("Status")))
        c1, c2, c3 = st.columns(3)
        if c1.button("Save segment", use_container_width=True):
            seg["Target"] = new_target
            seg["Status"] = status
            st.success("Saved.")
        if c2.button("Approve", use_container_width=True):
            seg["Target"] = new_target
            seg["Status"] = "Approved"
            st.success("Approved.")
        if c3.button("Approve + Save TM", use_container_width=True):
            seg["Target"] = new_target
            seg["Status"] = "Approved"
            st.session_state.tm_entries.insert(0, {"TM ID": new_id("tm"), "Source Hash": text_hash(seg.get("Source", "")), "Source": seg.get("Source", ""), "Target": new_target, "Language": "", "Approved By": st.session_state.username, "Created": now_iso()})
            log_audit("TM saved", f"Segment {seg['Segment ID']} approved and saved to TM")
            st.success("Approved and saved to TM.")
    with right:
        st.markdown("### Matches & rules")
        tm_target, tm_label = best_tm_match(seg.get("Source", ""))
        if tm_target:
            st.markdown(f'<div class="es-ok"><b>TM {tm_label}</b><br>{htmlesc(tm_target)}</div>', unsafe_allow_html=True)
        else:
            st.info("No TM match.")
        st.markdown("#### Glossary")
        matches = [g for g in st.session_state.glossary if g.get("Source Term", "").lower() in seg.get("Source", "").lower()]
        if matches:
            st.dataframe(pd.DataFrame(matches), use_container_width=True, hide_index=True)
        else:
            st.caption("No glossary hits.")
        st.markdown("#### DNT")
        dnt_hits = [d for d in st.session_state.dnt_terms if d.get("Term", "").lower() in seg.get("Source", "").lower()]
        if dnt_hits:
            st.dataframe(pd.DataFrame(dnt_hits), use_container_width=True, hide_index=True)
        else:
            st.caption("No DNT hits.")

    st.markdown("### Bulk review grid")
    edited = st.data_editor(pd.DataFrame(segments), use_container_width=True, hide_index=True, num_rows="fixed", key="review_grid")
    if st.button("Save bulk grid", use_container_width=True):
        st.session_state.review_segments = edited.to_dict("records")
        st.success("Bulk grid saved.")
    st.download_button("Download reviewed segments", edited.to_csv(index=False).encode("utf-8-sig"), "reviewed_segments.csv", "text/csv", use_container_width=True)


def scorecards_page() -> None:
    page_header("Scorecards", "Translator vs reviewer quality score", "Compare translator output with reviewer/final output. Source file is optional.")
    src = st.file_uploader("Source file (optional)", type=["xlsx", "csv", "docx", "txt"], key="score_src")
    trans = st.file_uploader("Translator file", type=["xlsx", "csv", "docx", "txt"], key="score_trans")
    rev = st.file_uploader("Reviewer/final file", type=["xlsx", "csv", "docx", "txt"], key="score_rev")
    if st.button("Generate Scorecard", type="primary", use_container_width=True, disabled=(trans is None or rev is None)):
        trans_seg = extract_segments_from_file(trans, assume_source_only=False)
        rev_seg = extract_segments_from_file(rev, assume_source_only=False)
        src_seg = extract_segments_from_file(src, assume_source_only=True) if src else []
        rows = []
        total_penalty = 0
        max_len = max(len(trans_seg), len(rev_seg))
        for i in range(max_len):
            t = trans_seg[i] if i < len(trans_seg) else {}
            r = rev_seg[i] if i < len(rev_seg) else {}
            s = src_seg[i].get("Source", "") if i < len(src_seg) else t.get("Source", r.get("Source", ""))
            old = t.get("Target", t.get("Source", ""))
            new = r.get("Target", r.get("Source", ""))
            changed = clean_text(old) != clean_text(new)
            penalty = 0 if not changed else (5 if len(str(old)) > 0 else 10)
            total_penalty += penalty
            rows.append({"Segment ID": i+1, "Source": s, "Translator": old, "Reviewer": new, "Changed": "Yes" if changed else "No", "Severity": "Major" if penalty >= 5 else "Pass", "Penalty": penalty})
        score = max(0, 100 - total_penalty)
        metric_cards([("Score", f"{score}/100", "quality score"), ("Changed", sum(1 for r in rows if r["Changed"] == "Yes"), "segments"), ("Penalty", total_penalty, "total points")], columns=3)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.download_button("Download scorecard", csv_bytes(rows), "translator_scorecard.csv", "text/csv", use_container_width=True)
        st.session_state.jobs.insert(0, {"Job ID": new_id("job"), "Type": "Scorecard", "File": trans.name, "Segments": len(rows), "Issues": sum(1 for r in rows if r["Changed"] == "Yes"), "Status": "Completed", "Created": now_iso()})


def memory_rules_page() -> None:
    page_header("Memory & Rules", "Translation memory, glossary, and DNT", "Manage reusable knowledge for review and future jobs.")
    tab_tm, tab_glossary, tab_dnt = st.tabs(["Translation Memory", "Glossary", "DNT"])
    with tab_tm:
        st.dataframe(pd.DataFrame(st.session_state.tm_entries), use_container_width=True, hide_index=True)
        with st.form("manual_tm"):
            source = st.text_area("Source")
            target = st.text_area("Target")
            if st.form_submit_button("Add TM", use_container_width=True) and source and target:
                st.session_state.tm_entries.insert(0, {"TM ID": new_id("tm"), "Source Hash": text_hash(source), "Source": source, "Target": target, "Language": "", "Approved By": st.session_state.username, "Created": now_iso()})
                st.success("TM added.")
    with tab_glossary:
        st.dataframe(pd.DataFrame(st.session_state.glossary), use_container_width=True, hide_index=True)
        with st.form("manual_gloss"):
            s = st.text_input("Source term")
            t = st.text_input("Target term")
            if st.form_submit_button("Add glossary", use_container_width=True) and s and t:
                st.session_state.glossary.insert(0, {"Source Term": s, "Target Term": t, "Rule Source": "Manual"})
                st.success("Glossary term added.")
    with tab_dnt:
        st.dataframe(pd.DataFrame(st.session_state.dnt_terms), use_container_width=True, hide_index=True)
        with st.form("manual_dnt"):
            term = st.text_input("DNT term")
            if st.form_submit_button("Add DNT", use_container_width=True) and term:
                st.session_state.dnt_terms.insert(0, {"Term": term, "Rule Source": "Manual"})
                st.success("DNT term added.")


def team_roles_page() -> None:
    if st.session_state.role not in {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager"}:
        page_header("Team & Roles", "Restricted", "Only workspace managers can invite or edit team roles.")
        st.warning("You cannot manage team roles from this account.")
        return
    page_header("Team & Roles", "Workspace access", "Manage only this workspace team. Platform-wide user access is visible only in the owner console.")
    with st.form("team_add"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name")
        email = c2.text_input("Email")
        role = c3.selectbox("Role", [r for r in ROLES if r != "Platform Owner"])
        if st.form_submit_button("Add user", use_container_width=True) and email:
            st.session_state.team.insert(0, {"Name": name, "Email": email, "Role": role, "Status": "Invited"})
            st.success("Workspace user added.")
    st.dataframe(pd.DataFrame(st.session_state.team), use_container_width=True, hide_index=True)


def billing_page() -> None:
    page_header("Billing", "Workspace billing", "Workspace users see only their own workspace plan and invoices. Platform-wide payments are owner-only.")
    metric_cards([("Plan", "Trial", "workspace plan"), ("Credits", "Unlimited", "during build"), ("Invoices", 0, "workspace invoices"), ("Gateway", "Pending", "future integration")])
    st.markdown('<div class="es-note">Only the platform owner can see the complete payments received ledger across all customers.</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(columns=["Invoice", "Date", "Amount", "Status"]), use_container_width=True, hide_index=True)


def account_page() -> None:
    page_header("Account", "Profile", "View your account identity, role, and workspace access.")
    metric_cards([("Email", st.session_state.username, "signed-in account"), ("Role", st.session_state.role, "access level"), ("Workspace", st.session_state.workspace_name, "current workspace")], columns=3)
    st.markdown("### Pages you can access")
    st.dataframe(pd.DataFrame({"Page": allowed_pages()}), use_container_width=True, hide_index=True)

# ==========================================================
# Router
# ==========================================================

def render_app() -> None:
    page = st.session_state.get("active_page", "Dashboard")
    if page not in allowed_pages():
        st.session_state.active_page = allowed_pages()[0]
    page = render_top_nav()
    routes = {
        "Owner Console": owner_console_page,
        "Payments Received": payments_received_page,
        "User Access Matrix": user_access_matrix_page,
        "All Workspaces": all_workspaces_page,
        "Platform Settings": platform_settings_page,
        "Platform Audit Logs": platform_audit_logs_page,
        "Dashboard": dashboard_page,
        "Projects": projects_page,
        "Jobs": jobs_page,
        "ErrorSweep QA": qa_page,
        "ErrorSweep Pro": pro_page,
        "Human Review": human_review_page,
        "Scorecards": scorecards_page,
        "Memory & Rules": memory_rules_page,
        "Team & Roles": team_roles_page,
        "Billing": billing_page,
        "Account": account_page,
    }
    routes.get(page, dashboard_page)()
    st.markdown(f'<div class="es-help" style="margin-top:40px;">ErrorSweep {APP_VERSION} · Main API first · Platform-owner private controls separated from workspace users.</div>', unsafe_allow_html=True)


init_state()
restore_session_from_url()
if not st.session_state.get("authenticated"):
    login_page()
else:
    render_app()

