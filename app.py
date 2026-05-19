from __future__ import annotations

import difflib
import hashlib
import io
import json
import os
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from docx import Document
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


# ==========================================================
# ErrorSweep Platform v22
# Website-first localization platform shell
# ==========================================================

st.set_page_config(page_title="ErrorSweep", page_icon="🌐", layout="wide", initial_sidebar_state="collapsed")

APP_VERSION = "v23 Owner/User Accounts"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
NEEDS_REVIEW_MARKER = "⟦NEEDS HUMAN REVIEW⟧"

SUPPORTED_LANGUAGES = [
    "French", "Spanish", "German", "Italian", "Portuguese", "Arabic", "Chinese",
    "Japanese", "Korean", "Russian", "Telugu", "Hindi", "Tamil", "Malayalam",
    "Kannada", "Bengali", "Marathi", "Gujarati", "Urdu", "English",
]

DOMAINS = [
    "Auto-detect", "Software UI", "Marketing", "Legal", "Medical", "E-learning",
    "Subtitles", "Gaming", "Finance", "General",
]

PAGES = [
    "Dashboard", "Projects", "Jobs", "ErrorSweep QA", "ErrorSweep Pro", "Human Review",
    "Scorecards", "Memory & Rules", "Team & Roles", "Billing", "Account", "Admin", "Platform Owner Console",
]

PLATFORM_ROLES = ["Platform Owner"]
WORKSPACE_ROLES = ["Workspace Owner", "Workspace Admin", "Project Manager", "Translator", "Reviewer", "Client Viewer", "Billing Admin"]
ROLES = PLATFORM_ROLES + WORKSPACE_ROLES

PAGE_ACCESS = {
    "Dashboard": set(ROLES),
    "Projects": {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager"},
    "Jobs": {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager", "Translator", "Reviewer", "Client Viewer"},
    "ErrorSweep QA": {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager", "Reviewer"},
    "ErrorSweep Pro": {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager"},
    "Human Review": {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager", "Translator", "Reviewer"},
    "Scorecards": {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager", "Reviewer"},
    "Memory & Rules": {"Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager", "Reviewer"},
    "Team & Roles": {"Platform Owner", "Workspace Owner", "Workspace Admin"},
    "Billing": {"Platform Owner", "Workspace Owner", "Billing Admin"},
    "Account": set(ROLES),
    "Admin": {"Workspace Owner", "Workspace Admin"},
    "Platform Owner Console": {"Platform Owner"},
}

def is_platform_owner() -> bool:
    return st.session_state.get("account_type") == "platform_owner" or st.session_state.get("role") == "Platform Owner"

def available_pages() -> List[str]:
    role = st.session_state.get("role", "Client Viewer")
    pages = [p for p in PAGES if role in PAGE_ACCESS.get(p, set())]
    return pages or ["Dashboard", "Account"]

def can_access(page: str) -> bool:
    return st.session_state.get("role", "Client Viewer") in PAGE_ACCESS.get(page, set())

PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[sd]|\$\w+|<[^>]+>)")
NUMBER_RE = re.compile(r"\d+(?:[.,:]\d+)*")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+", flags=re.UNICODE)


# ==========================================================
# Visual system
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

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp {
  background:
    radial-gradient(circle at 12% 18%, rgba(0,231,133,.13), transparent 28%),
    radial-gradient(circle at 88% 10%, rgba(53,189,247,.12), transparent 30%),
    radial-gradient(circle at 52% 100%, rgba(139,92,246,.11), transparent 45%),
    var(--bg);
  color: var(--text);
}
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stDeployButton"], .stAppDeployButton, [data-testid="stStatusWidget"] {
  visibility: hidden !important;
  display: none !important;
}
section[data-testid="stSidebar"] { display:none !important; }
.block-container { padding-top: 28px !important; max-width: 1480px !important; }

.es-shell { max-width: 1480px; margin: 0 auto; }
.es-topbar {
  background: rgba(16,20,36,.78);
  border: 1px solid rgba(125,145,255,.20);
  border-radius: 22px;
  padding: 18px 22px;
  margin-bottom: 16px;
  box-shadow: 0 20px 60px rgba(0,0,0,.22);
}
.es-brand-row { display:flex; align-items:center; justify-content:space-between; gap: 18px; flex-wrap:wrap; }
.es-brand { font-size: 21px; font-weight: 900; color:#fff; letter-spacing:-.3px; }
.es-brand small { display:block; color:var(--muted); font-size:12px; font-weight:500; margin-top:4px; }
.es-pill {
  display:inline-block;
  padding: 5px 11px;
  border-radius: 999px;
  color: #9fffd1;
  background: rgba(0,231,133,.10);
  border: 1px solid rgba(0,231,133,.28);
  font-family:'Space Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .4px;
  text-transform: uppercase;
}
.es-hero {
  padding: 34px;
  border: 1px solid rgba(53,189,247,.22);
  border-radius: 26px;
  background:
    linear-gradient(135deg, rgba(0,231,133,.12), rgba(53,189,247,.08) 42%, rgba(139,92,246,.18)),
    rgba(16,20,36,.82);
  box-shadow: 0 30px 90px rgba(0,0,0,.30);
  margin: 18px 0 24px 0;
}
.es-kicker {
  display:inline-block;
  color: var(--green);
  background: rgba(0,231,133,.10);
  border: 1px solid rgba(0,231,133,.28);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 11px;
  font-family:'Space Mono', monospace;
  font-weight: 700;
  letter-spacing: .6px;
  text-transform: uppercase;
}
.es-title {
  font-size: 38px;
  line-height: 1.05;
  font-weight: 900;
  margin: 18px 0 8px 0;
  background: linear-gradient(90deg, #fff, #bfffe1 35%, #9bdfff 70%, #d5c8ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.es-sub { color: #c4cbdf; font-size: 15px; max-width: 980px; }
.es-grid { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:14px; margin:14px 0 22px; }
.es-grid-3 { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:14px; margin:14px 0 22px; }
.es-card {
  background: rgba(16,20,36,.80);
  border: 1px solid rgba(125,145,255,.20);
  border-radius: 17px;
  padding: 18px;
  box-shadow: 0 15px 35px rgba(0,0,0,.18);
}
.es-card h3,.es-card h4 { margin:0 0 8px 0; color:#f8fbff; }
.es-card p { color:var(--muted); margin:0; font-size:13px; }
.es-metric-label { font-family:'Space Mono', monospace; font-size:11px; color:#a7b4d8; letter-spacing:.8px; text-transform:uppercase; }
.es-metric-value { font-size:30px; font-weight:900; color:#fff; margin: 6px 0; }
.es-badge { display:inline-block; padding:4px 10px; border-radius:999px; font-size:11px; font-weight:800; border:1px solid rgba(125,145,255,.25); color:#dfe7ff; background:rgba(125,145,255,.10); }
.es-badge-green { color:#9fffd1; border-color:rgba(0,231,133,.35); background:rgba(0,231,133,.12); }
.es-badge-yellow { color:#ffe8a3; border-color:rgba(251,191,36,.35); background:rgba(251,191,36,.12); }
.es-badge-red { color:#ffc2cd; border-color:rgba(255,77,109,.35); background:rgba(255,77,109,.12); }
.es-badge-cyan { color:#b9ebff; border-color:rgba(53,189,247,.35); background:rgba(53,189,247,.12); }
.es-note { background:rgba(33,44,84,.72); border:1px solid rgba(125,145,255,.20); border-radius:14px; padding:14px 16px; color:#c7d3ff; }
.es-cat-layout { display:grid; grid-template-columns: 0.95fr 1.15fr 0.85fr; gap:16px; align-items:start; }
.es-segment-list { max-height: 620px; overflow:auto; padding-right:4px; }
.es-seg-item { padding:12px; border:1px solid rgba(125,145,255,.16); border-radius:13px; margin-bottom:10px; background:rgba(16,20,36,.74); }
.es-seg-source { color:#f7fbff; font-size:13px; line-height:1.35; margin-top:8px; }
.es-assist-box { border:1px solid rgba(125,145,255,.20); border-radius:14px; padding:13px; background:rgba(16,20,36,.74); margin-bottom:12px; }
.es-footer-note { color:#7d8bad; font-size:12px; margin-top:22px; }
.stButton > button, .stDownloadButton > button {
  border-radius: 13px !important;
  border: 1px solid rgba(0,231,133,.25) !important;
  background: linear-gradient(90deg, #00c876, #159fe8) !important;
  color: white !important;
  font-weight: 800 !important;
}
.stButton > button:hover, .stDownloadButton > button:hover { transform:translateY(-1px); box-shadow:0 16px 35px rgba(0,231,133,.15); }
div[data-testid="stExpander"] { border:1px solid rgba(125,145,255,.20)!important; background:rgba(16,20,36,.62)!important; border-radius:14px!important; }
[data-testid="stFileUploader"] { background:rgba(16,20,36,.72); border:1px solid rgba(125,145,255,.18); border-radius:14px; padding:12px; }
@media (max-width: 1000px) {
  .es-grid, .es-grid-3, .es-cat-layout { grid-template-columns: 1fr; }
  .es-title { font-size: 28px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ==========================================================
# State
# ==========================================================

def init_state() -> None:
    defaults = {
        "authenticated": False,
        "username": "",
        "role": "Client Viewer",
        "account_type": "workspace_user",
        "organization_name": "Demo Workspace",
        "active_page": "Dashboard",
        "projects": [],
        "jobs": [],
        "tm_entries": [],
        "glossary": [],
        "dnt_terms": [],
        "review_segments": [],
        "team": [],
        "workspaces": [],
        "admin_flags": {"demo_mode": True, "billing_enabled": False, "allow_demo_users": True},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.team:
        st.session_state.team = [
            {"Name": "Workspace Owner", "Email": "owner@demo-workspace.local", "Role": "Workspace Owner", "Status": "Active"},
            {"Name": "Reviewer Demo", "Email": "reviewer@demo-workspace.local", "Role": "Reviewer", "Status": "Invited"},
            {"Name": "Translator Demo", "Email": "translator@demo-workspace.local", "Role": "Translator", "Status": "Invited"},
        ]
    if not st.session_state.workspaces:
        st.session_state.workspaces = [
            {"Workspace": "Demo Workspace", "Owner": "owner@demo-workspace.local", "Plan": "Demo", "Status": "Active", "Users": len(st.session_state.team)},
        ]

init_state()


# ==========================================================
# Secrets / API
# ==========================================================

def secret(name: str, default: str = "") -> str:
    env_val = os.environ.get(name)
    if env_val:
        return env_val
    try:
        val = st.secrets.get(name)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return default


def allow_demo_login() -> bool:
    return secret("ERRORSWEEP_ALLOW_DEMO_LOGIN", "true").lower().strip() in {"1", "true", "yes", "on"}


def get_openai_client():
    key = secret("OPENAI_API_KEY")
    if not key or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=key, timeout=90, max_retries=1)
    except Exception:
        return None


def model_name() -> str:
    return secret("OPENAI_MODEL", DEFAULT_MODEL)


# ==========================================================
# General helpers
# ==========================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\u00A0", " ").replace("\u200B", "").strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(clean_text(text).lower().encode("utf-8")).hexdigest()[:16]


def truncate(text: Any, n: int = 220) -> str:
    t = clean_text(text)
    return t if len(t) <= n else t[: n - 1] + "…"


def extract_placeholders(text: str) -> List[str]:
    return PLACEHOLDER_RE.findall(text or "")


def extract_numbers(text: str) -> List[str]:
    return NUMBER_RE.findall(text or "")


def parse_json_array(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    t = text.strip()
    t = re.sub(r"^```json\s*", "", t, flags=re.I)
    t = re.sub(r"^```\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start = t.find("[")
    end = t.rfind("]")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    try:
        data = json.loads(t)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def preserve_protected(source: str, translation: str) -> str:
    output = translation or ""
    for token in extract_placeholders(source):
        if token and token not in output:
            output = (output.rstrip() + " " + token).strip()
    for emoji in EMOJI_RE.findall(source or ""):
        if emoji and emoji not in output:
            output = f"{emoji} {output}".strip()
    leading = re.match(r"^(\s*[•∙·\-\*]\s*)", source or "")
    if leading:
        marker = leading.group(1)
        if marker.strip() and not output.lstrip().startswith(marker.strip()):
            output = marker + output.lstrip()
    s = clean_text(source)
    t = clean_text(output)
    if s.startswith("[") and s.endswith("]") and t and not (t.startswith("[") and t.endswith("]")):
        output = f"[{t}]"
    return output.strip()


def is_bad_translation(source: str, translation: str, target_language: str = "") -> bool:
    src = clean_text(source)
    tgt = clean_text(translation)
    if not src:
        return False
    if not tgt:
        return True
    tokenless = PLACEHOLDER_RE.sub("", tgt)
    tokenless = NUMBER_RE.sub("", tokenless)
    tokenless = EMOJI_RE.sub("", tokenless)
    tokenless = re.sub(r"[\s\[\]{}():;,.!?\"'`~\-–—_/\\|•∙·*]+", "", tokenless)
    if tokenless == "" and (PLACEHOLDER_RE.search(src) or len(src) > 4):
        return True
    if src.lower() == tgt.lower() and target_language.lower() not in {"english", "en"}:
        return True
    return False


def infer_domain_from_texts(texts: List[str]) -> str:
    combined = " ".join(texts[:80]).lower()
    if any(k in combined for k in ["dashboard", "settings", "password", "upload", "button", "screen", "login", "menu"]):
        return "Software UI"
    if any(k in combined for k in ["terms", "contract", "liability", "clause", "agreement"]):
        return "Legal"
    if any(k in combined for k in ["doctor", "patient", "dose", "medicine", "clinical"]):
        return "Medical"
    if any(k in combined for k in ["sale", "offer", "campaign", "brand", "audience"]):
        return "Marketing"
    if any(k in combined for k in ["lesson", "course", "student", "module", "quiz"]):
        return "E-learning"
    if any(k in combined for k in ["subtitle", "caption", "speaker", "srt"]):
        return "Subtitles"
    return "General"


def smart_gate(missing_count: int, total_count: int, threshold: float = 0.12) -> Tuple[str, str]:
    total = max(total_count, 1)
    rate = missing_count / total
    if missing_count == 0:
        return "pass", "Complete"
    if rate <= threshold:
        return "review", f"Human Review Required: {missing_count}/{total} unresolved segment(s)."
    return "block", f"Blocked: {missing_count}/{total} unresolved segment(s)."


def download_excel(df: pd.DataFrame, sheet_name: str = "Report") -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return bio.getvalue()


def metric_cards(items: List[Tuple[str, Any, str]]) -> None:
    if not items:
        return
    cols = st.columns(min(4, len(items)))
    for idx, (label, value, caption) in enumerate(items):
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="es-card">
                  <div class="es-metric-label">{escape(str(label))}</div>
                  <div class="es-metric-value">{escape(str(value))}</div>
                  <p>{escape(str(caption))}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="es-hero">
          <span class="es-kicker">{escape(kicker)}</span>
          <div class="es-title">{escape(title)}</div>
          <div class="es-sub">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==========================================================
# File extraction
# ==========================================================

@dataclass
class ExtractedFile:
    kind: str
    name: str
    segments: List[Dict[str, Any]]
    raw: Any = None
    logs: Optional[List[str]] = None


def detect_columns(headers: List[str]) -> Tuple[Optional[str], Optional[str]]:
    source_terms = ["source text", "source", "src", "english", "source segment", "source string"]
    target_terms = ["target", "translation", "translated text", "original translation", "target text", "reviewer", "final"]
    source_col = None
    target_col = None
    for original in headers:
        key = clean_text(original).lower()
        if source_col is None and any(term == key or term in key for term in source_terms):
            source_col = original
        if target_col is None and any(term == key or term in key for term in target_terms):
            target_col = original
    return source_col, target_col


def extract_from_xlsx(uploaded_file, mode: str = "review") -> ExtractedFile:
    wb = load_workbook(uploaded_file)
    segments: List[Dict[str, Any]] = []
    logs: List[str] = []
    locations: Dict[str, Any] = {}

    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        source_idx = target_idx = None
        header_row_index = 0
        headers: List[str] = []
        for i, row in enumerate(rows[:35]):
            h = [clean_text(v) for v in row]
            if not any(h):
                continue
            s_col, t_col = detect_columns(h)
            if s_col or t_col or len([x for x in h if x]) >= 2:
                headers = h
                header_row_index = i
                if s_col and s_col in h:
                    source_idx = h.index(s_col)
                else:
                    source_idx = 0
                if t_col and t_col in h:
                    target_idx = h.index(t_col)
                elif len(h) > 1:
                    target_idx = 1
                break
        if source_idx is None:
            continue

        logs.append(f"{ws.title}: extracted source/target rows.")
        for r_i, row in enumerate(rows[header_row_index + 1:], start=header_row_index + 2):
            row_values = list(row)
            source = clean_text(row_values[source_idx] if source_idx < len(row_values) else "")
            target = clean_text(row_values[target_idx] if target_idx is not None and target_idx < len(row_values) else "")
            if not source and not target:
                continue
            loc = f"{ws.title}!R{r_i}"
            segments.append({
                "id": len(segments) + 1,
                "location": loc,
                "sheet": ws.title,
                "row": r_i,
                "source": source,
                "target": target,
                "translation": target,
                "target_col": target_idx,
                "file_type": "xlsx",
                "origin_status": "Existing" if target else "Untranslated",
            })
            if target_idx is not None:
                locations[loc] = (ws.title, r_i, target_idx)

    return ExtractedFile("xlsx", uploaded_file.name, segments, raw={"workbook": wb, "locations": locations}, logs=logs)


def extract_from_csv(uploaded_file, mode: str = "review") -> ExtractedFile:
    df = pd.read_csv(uploaded_file)
    if df.empty:
        return ExtractedFile("csv", uploaded_file.name, [], raw=df, logs=["CSV is empty."])
    source_col, target_col = detect_columns(list(df.columns))
    source_col = source_col or df.columns[0]
    if target_col is None:
        target_col = df.columns[1] if len(df.columns) > 1 else "Target"
        if target_col not in df.columns:
            df[target_col] = ""

    segments: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        source = clean_text(row.get(source_col, ""))
        target = clean_text(row.get(target_col, ""))
        if not source and not target:
            continue
        segments.append({
            "id": len(segments) + 1,
            "location": f"Row {idx + 2}",
            "sheet": "CSV",
            "row": int(idx),
            "source": source,
            "target": target,
            "translation": target,
            "target_col": target_col,
            "file_type": "csv",
            "origin_status": "Existing" if target else "Untranslated",
        })
    return ExtractedFile("csv", uploaded_file.name, segments, raw=df, logs=[f"CSV: {source_col} → {target_col}"])


def extract_from_docx(uploaded_file, mode: str = "review") -> ExtractedFile:
    doc = Document(uploaded_file)
    segments: List[Dict[str, Any]] = []
    locations: Dict[str, Any] = {}

    for t_i, table in enumerate(doc.tables, start=1):
        if not table.rows:
            continue
        headers = [clean_text(c.text) for c in table.rows[0].cells]
        source_col, target_col = detect_columns(headers)
        if not source_col and len(headers) < 2:
            continue
        source_idx = headers.index(source_col) if source_col and source_col in headers else 0
        target_idx = headers.index(target_col) if target_col and target_col in headers else (1 if len(headers) > 1 else None)
        for r_i, row in enumerate(table.rows[1:], start=2):
            source = clean_text(row.cells[source_idx].text) if source_idx < len(row.cells) else ""
            target = clean_text(row.cells[target_idx].text) if target_idx is not None and target_idx < len(row.cells) else ""
            if not source and not target:
                continue
            loc = f"Table {t_i}, Row {r_i}"
            segments.append({
                "id": len(segments) + 1,
                "location": loc,
                "sheet": f"Table {t_i}",
                "row": r_i,
                "source": source,
                "target": target,
                "translation": target,
                "file_type": "docx",
                "origin_status": "Existing" if target else "Untranslated",
            })
            if target_idx is not None and target_idx < len(row.cells):
                locations[loc] = row.cells[target_idx]
    if segments:
        return ExtractedFile("docx", uploaded_file.name, segments, raw={"doc": doc, "locations": locations}, logs=["DOCX: extracted table segments."])

    for i, p in enumerate(doc.paragraphs, start=1):
        text = clean_text(p.text)
        if not text:
            continue
        loc = f"Paragraph {i}"
        segments.append({
            "id": len(segments) + 1,
            "location": loc,
            "sheet": "Document",
            "row": i,
            "source": text,
            "target": "",
            "translation": "",
            "file_type": "docx",
            "origin_status": "Untranslated",
        })
        locations[loc] = p
    return ExtractedFile("docx", uploaded_file.name, segments, raw={"doc": doc, "locations": locations}, logs=["DOCX: paragraph fallback."])


def extract_from_text(uploaded_file, mode: str = "review") -> ExtractedFile:
    raw = uploaded_file.getvalue()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("cp1252", errors="replace")
    lines = text.splitlines()
    segments: List[Dict[str, Any]] = []

    # If the file is a Source/Target two-column plain text template, every non-empty
    # source line is a source-only segment. This supports direct Human Review upload.
    for i, line in enumerate(lines, start=1):
        value = clean_text(line)
        if not value:
            continue
        if i <= 2 and value.lower() in {"source", "target", "source text", "translation"}:
            continue
        segments.append({
            "id": len(segments) + 1,
            "location": f"Line {i}",
            "sheet": "Text",
            "row": i,
            "source": value,
            "target": "",
            "translation": "",
            "file_type": "text",
            "origin_status": "Untranslated",
        })
    return ExtractedFile("text", uploaded_file.name, segments, raw=text, logs=["Text: extracted editable lines."])


def extract_file(uploaded_file, mode: str = "review") -> ExtractedFile:
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx"):
        return extract_from_xlsx(uploaded_file, mode)
    if name.endswith(".csv"):
        return extract_from_csv(uploaded_file, mode)
    if name.endswith(".docx"):
        return extract_from_docx(uploaded_file, mode)
    return extract_from_text(uploaded_file, mode)


def build_review_export(segments: List[Dict[str, Any]]) -> bytes:
    df = pd.DataFrame(segments)
    columns = ["Location", "Status", "Match", "Source", "Target", "Comment", "Target Language"]
    rows = []
    for seg in segments:
        rows.append({
            "Location": seg.get("location", seg.get("Location", "")),
            "Status": seg.get("Status", seg.get("status", "")),
            "Match": seg.get("Match", seg.get("match", "")),
            "Source": seg.get("Source", seg.get("source", "")),
            "Target": seg.get("Target", seg.get("target", "")),
            "Comment": seg.get("Comment", seg.get("comment", "")),
            "Target Language": seg.get("Target Language", seg.get("target_language", "")),
        })
    return pd.DataFrame(rows, columns=columns).to_csv(index=False).encode("utf-8-sig")


def build_output_file(extracted: ExtractedFile, translations_by_loc: Dict[str, str]) -> Tuple[bytes, str, str]:
    name = extracted.name
    if extracted.kind == "xlsx":
        wb = extracted.raw["workbook"]
        locations = extracted.raw["locations"]
        for loc, target in translations_by_loc.items():
            if loc in locations:
                ws_name, row_num, col_idx = locations[loc]
                wb[ws_name].cell(row=int(row_num), column=int(col_idx) + 1).value = target
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"errorsweep_output_{name}"

    if extracted.kind == "csv":
        df = extracted.raw
        col = "Reviewed Translation"
        if col not in df.columns:
            df[col] = ""
        for seg in extracted.segments:
            df.at[int(seg["row"]), col] = translations_by_loc.get(seg["location"], "")
        return df.to_csv(index=False).encode("utf-8-sig"), "text/csv", re.sub(r"\.[^.]+$", ".csv", f"errorsweep_output_{name}")

    if extracted.kind == "docx":
        doc = extracted.raw["doc"]
        locations = extracted.raw["locations"]
        for loc, target in translations_by_loc.items():
            obj = locations.get(loc)
            if obj is None:
                continue
            if hasattr(obj, "paragraphs"):
                for p in obj.paragraphs:
                    for run in p.runs:
                        run.text = ""
                if obj.paragraphs:
                    obj.paragraphs[0].add_run(target)
                else:
                    obj.add_paragraph(target)
            else:
                obj.add_run("\n" + target)
        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"errorsweep_output_{name}"

    # Text output: source followed by reviewed target.
    rows = []
    for seg in extracted.segments:
        rows.append(seg.get("source", ""))
        target = translations_by_loc.get(seg["location"], "")
        if target:
            rows.append(target)
    return "\n".join(rows).encode("utf-8-sig"), "text/plain", f"errorsweep_output_{name}"


# ==========================================================
# Rules, TM, QA, API
# ==========================================================

def parse_rules_zip(uploaded_zip) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], str]:
    glossary: List[Dict[str, str]] = []
    dnt_terms: List[Dict[str, str]] = []
    combined = ""
    if not uploaded_zip:
        return glossary, dnt_terms, combined
    try:
        zf = zipfile.ZipFile(io.BytesIO(uploaded_zip.getvalue()))
    except Exception:
        return glossary, dnt_terms, combined

    for info in zf.infolist()[:50]:
        if info.is_dir():
            continue
        name = info.filename
        lower = name.lower()
        data = zf.read(info)
        text = ""
        if lower.endswith((".txt", ".md", ".csv")):
            text = data.decode("utf-8", errors="replace")
        elif lower.endswith(".xlsx"):
            try:
                wb = load_workbook(io.BytesIO(data), data_only=True)
                parts = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        vals = [clean_text(v) for v in row if clean_text(v)]
                        if vals:
                            parts.append(" | ".join(vals))
                text = "\n".join(parts)
            except Exception:
                text = ""
        combined += f"\n# {name}\n{text}\n"
        if lower.endswith(".csv"):
            try:
                df = pd.read_csv(io.StringIO(text))
                cols = {str(c).lower(): c for c in df.columns}
                src_col = next((cols[c] for c in cols if "source" in c or c == "term"), None)
                tgt_col = next((cols[c] for c in cols if "target" in c or "translation" in c), None)
                dnt_col = next((cols[c] for c in cols if "dnt" in c or "do not" in c), None)
                if src_col and tgt_col:
                    for _, row in df.iterrows():
                        s = clean_text(row.get(src_col, ""))
                        t = clean_text(row.get(tgt_col, ""))
                        if s and t:
                            glossary.append({"Source Term": s, "Target Term": t, "Rule Source": name})
                if dnt_col:
                    for value in df[dnt_col].fillna("").tolist():
                        term = clean_text(value)
                        if term:
                            dnt_terms.append({"Term": term, "Rule Source": name})
            except Exception:
                pass
    return glossary, dnt_terms, combined[:6000]


def best_tm_match(source: str) -> Tuple[str, str]:
    if not source or not st.session_state.tm_entries:
        return "No match", ""
    src_norm = clean_text(source).lower()
    exact = [t for t in st.session_state.tm_entries if clean_text(t.get("Source", "")).lower() == src_norm]
    if exact:
        # 101% = context/exact source match in this MVP.
        return "101%", exact[-1].get("Target", "")
    best_score = 0.0
    best_target = ""
    for item in st.session_state.tm_entries:
        candidate = clean_text(item.get("Source", ""))
        score = difflib.SequenceMatcher(None, src_norm, candidate.lower()).ratio()
        if score > best_score:
            best_score = score
            best_target = item.get("Target", "")
    if best_score >= 0.85:
        return "100%", best_target
    if best_score >= 0.55:
        return f"{round(best_score * 100)}% fuzzy", best_target
    return "No match", ""


def status_for_segment(source: str, target: str, origin_status: str = "") -> str:
    match, tm_target = best_tm_match(source)
    if match in {"101%", "100%"}:
        return match
    if "fuzzy" in match:
        return match
    if target and origin_status == "MT":
        return "MT"
    if target:
        return "Existing"
    return "Untranslated"


def deterministic_qa(segments: List[Dict[str, Any]], glossary: List[Dict[str, str]], dnt_terms: List[Dict[str, str]], target_language: str = "") -> List[Dict[str, Any]]:
    rows = []
    for seg in segments:
        source = seg.get("source") or seg.get("Source", "")
        target = seg.get("translation") or seg.get("target") or seg.get("Target", "")
        loc = seg.get("location") or seg.get("Location", "")
        if not target:
            rows.append({"Location": loc, "Source": source, "Translation": target, "Issue Type": "Blank target", "Severity": "Major", "Suggestion": "Translate or send to Human Review.", "Reason": "Target is blank."})
            continue
        if clean_text(source).lower() == clean_text(target).lower() and target_language.lower() not in {"english", "en"}:
            rows.append({"Location": loc, "Source": source, "Translation": target, "Issue Type": "Source copied", "Severity": "Major", "Suggestion": "Review and translate this segment.", "Reason": "Source and target are identical."})
        missing_ph = [p for p in extract_placeholders(source) if p not in extract_placeholders(target)]
        if missing_ph:
            rows.append({"Location": loc, "Source": source, "Translation": target, "Issue Type": "Placeholder", "Severity": "Critical", "Suggestion": "Preserve: " + ", ".join(missing_ph), "Reason": "Placeholder(s) from source are missing."})
        missing_num = [n for n in extract_numbers(source) if n not in extract_numbers(target)]
        if missing_num:
            rows.append({"Location": loc, "Source": source, "Translation": target, "Issue Type": "Number mismatch", "Severity": "Major", "Suggestion": "Check number(s): " + ", ".join(missing_num), "Reason": "Number(s) from source are missing or changed."})
        for item in dnt_terms:
            term = item.get("Term", "")
            if term and term.lower() in source.lower() and term not in target:
                rows.append({"Location": loc, "Source": source, "Translation": target, "Issue Type": "DNT", "Severity": "Major", "Suggestion": f"Keep '{term}' unchanged.", "Reason": f"DNT term missing. Rule: {item.get('Rule Source','')}"})
        for item in glossary:
            src_term = item.get("Source Term", "")
            tgt_term = item.get("Target Term", "")
            if src_term and tgt_term and src_term.lower() in source.lower() and tgt_term not in target:
                rows.append({"Location": loc, "Source": source, "Translation": target, "Issue Type": "Glossary", "Severity": "Major", "Suggestion": tgt_term, "Reason": f"Glossary target term missing. Rule: {item.get('Rule Source','')}"})
    return rows


def ai_json_call(system: str, prompt: str, max_tokens: int = 6000) -> List[Dict[str, Any]]:
    client = get_openai_client()
    if client is None:
        raise RuntimeError("Main API is not configured.")
    response = client.responses.create(
        model=model_name(),
        instructions=system,
        input=prompt,
        max_output_tokens=max_tokens,
    )
    text = getattr(response, "output_text", "") or ""
    return parse_json_array(text)


def translate_with_main_api(segments: List[Dict[str, Any]], target_language: str, domain: str, rule_context: str = "") -> Dict[str, str]:
    output: Dict[str, str] = {}
    batch_size = int(secret("ERRORSWEEP_API_BATCH_SIZE", "20") or 20)
    for start in range(0, len(segments), batch_size):
        batch = segments[start:start + batch_size]
        payload = [{"location": seg["location"], "source": seg["source"]} for seg in batch]
        prompt = f"""
Translate these localization segments into {target_language}.
Domain: {domain}

Rules:
- Preserve placeholders exactly, e.g. {{{{email}}}}, {{{{user_name}}}}.
- Preserve numbers and units.
- Preserve emoji/icons and leading bullet characters.
- Preserve bracket structure for UI labels, but localize the text inside brackets.
- Return only JSON array with location and translation.

Company rules context:
{rule_context or "(none)"}

Segments:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            data = ai_json_call("You are a professional localization translation engine. Return only valid JSON.", prompt, max_tokens=7000)
        except Exception as exc:
            st.error(f"Main API translation failed: {exc}")
            data = []
        for item in data if isinstance(data, list) else []:
            loc = clean_text(item.get("location", ""))
            tr = clean_text(item.get("translation", ""))
            source = next((s["source"] for s in batch if s["location"] == loc), "")
            if loc:
                output[loc] = preserve_protected(source, tr)
    return output


def qa_with_main_api(segments: List[Dict[str, Any]], target_language: str, domain: str, rule_context: str = "") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if get_openai_client() is None:
        return rows
    batch_size = int(secret("ERRORSWEEP_API_BATCH_SIZE", "20") or 20)
    for start in range(0, len(segments), batch_size):
        batch = segments[start:start + batch_size]
        payload = [{"location": seg["location"], "source": seg.get("source", ""), "translation": seg.get("translation") or seg.get("target", "")} for seg in batch]
        prompt = f"""
Review the following localization segments for real errors.
Target language: {target_language}
Domain: {domain}
Company rules: {rule_context or "(none)"}
Segments: {json.dumps(payload, ensure_ascii=False)}
Return only JSON array with location, issue_type, severity, wrong_part, suggestion, reason.
"""
        try:
            data = ai_json_call("You are ErrorSweep, a conservative localization QA engine. Return only valid JSON.", prompt, max_tokens=6500)
        except Exception as exc:
            rows.append({"Location": "API", "Source": "", "Translation": "", "Issue Type": "API warning", "Severity": "Review", "Suggestion": "Retry this job.", "Reason": str(exc)[:400]})
            data = []
        loc_map = {seg["location"]: seg for seg in batch}
        for item in data if isinstance(data, list) else []:
            loc = clean_text(item.get("location", ""))
            seg = loc_map.get(loc, {})
            rows.append({
                "Location": loc,
                "Source": seg.get("source", ""),
                "Translation": seg.get("translation") or seg.get("target", ""),
                "Issue Type": item.get("issue_type", "AI QA"),
                "Severity": item.get("severity", "Review"),
                "Wrong Part": item.get("wrong_part", ""),
                "Suggestion": item.get("suggestion", ""),
                "Reason": item.get("reason", ""),
            })
    return rows


# ==========================================================
# Navigation/auth
# ==========================================================

def login_page() -> None:
    page_header("Account required", "ErrorSweep", "Secure localization QA, translation review, scorecards, and memory workflows.")
    st.info("Use Platform Owner for product/admin operations. Use Workspace User for client/team workflows.")

    tab_owner, tab_user, tab_demo = st.tabs(["Platform owner", "Workspace user", "Demo access"])

    with tab_owner:
        st.markdown("### Platform owner sign in")
        owner_user = st.text_input("Owner email / username", key="owner_login_user")
        owner_pass = st.text_input("Owner password", type="password", key="owner_login_pass")
        if st.button("Sign in as platform owner", type="primary", use_container_width=True):
            expected_user = secret("ERRORSWEEP_OWNER_USERNAME", secret("ERRORSWEEP_USERNAME", "owner"))
            expected_pass = secret("ERRORSWEEP_OWNER_PASSWORD", secret("ERRORSWEEP_PASSWORD", ""))
            if expected_pass and owner_user == expected_user and owner_pass == expected_pass:
                st.session_state.authenticated = True
                st.session_state.username = owner_user
                st.session_state.role = "Platform Owner"
                st.session_state.account_type = "platform_owner"
                st.session_state.organization_name = "ErrorSweep Platform"
                st.session_state.active_page = "Platform Owner Console"
                st.rerun()
            elif allow_demo_login() and not expected_pass:
                st.session_state.authenticated = True
                st.session_state.username = owner_user or "platform-owner@errorsweep.local"
                st.session_state.role = "Platform Owner"
                st.session_state.account_type = "platform_owner"
                st.session_state.organization_name = "ErrorSweep Platform"
                st.session_state.active_page = "Platform Owner Console"
                st.rerun()
            else:
                st.error("Invalid platform owner credentials.")

    with tab_user:
        st.markdown("### Workspace user sign in")
        user_email = st.text_input("User email / username", key="workspace_login_user")
        user_pass = st.text_input("Password", type="password", key="workspace_login_pass")
        if st.button("Sign in to workspace", type="primary", use_container_width=True):
            expected_user = secret("ERRORSWEEP_USERNAME", "admin")
            expected_pass = secret("ERRORSWEEP_PASSWORD", "")
            default_role = secret("ERRORSWEEP_DEFAULT_ROLE", "Workspace Owner")
            if default_role not in WORKSPACE_ROLES:
                default_role = "Workspace Owner"
            if expected_pass and user_email == expected_user and user_pass == expected_pass:
                st.session_state.authenticated = True
                st.session_state.username = user_email
                st.session_state.role = default_role
                st.session_state.account_type = "workspace_user"
                st.session_state.organization_name = secret("ERRORSWEEP_ORG_NAME", "Demo Workspace")
                st.session_state.active_page = "Dashboard"
                st.rerun()
            elif allow_demo_login() and not expected_pass:
                st.session_state.authenticated = True
                st.session_state.username = user_email or "workspace-admin@demo-workspace.local"
                st.session_state.role = "Workspace Owner"
                st.session_state.account_type = "workspace_user"
                st.session_state.organization_name = "Demo Workspace"
                st.session_state.active_page = "Dashboard"
                st.rerun()
            else:
                st.error("Invalid workspace credentials.")

    with tab_demo:
        st.markdown("### Demo access")
        demo_role = st.selectbox(
            "Demo role",
            ["Platform Owner", "Workspace Owner", "Workspace Admin", "Project Manager", "Translator", "Reviewer", "Client Viewer", "Billing Admin"],
            index=1,
        )
        demo_name = st.text_input("Demo email", value="demo@errorsweep.local")
        if st.button("Enter demo workspace", type="primary", use_container_width=True, disabled=not allow_demo_login()):
            st.session_state.authenticated = True
            st.session_state.username = demo_name or "demo@errorsweep.local"
            st.session_state.role = demo_role
            st.session_state.account_type = "platform_owner" if demo_role == "Platform Owner" else "workspace_user"
            st.session_state.organization_name = "ErrorSweep Platform" if demo_role == "Platform Owner" else "Demo Workspace"
            st.session_state.active_page = "Platform Owner Console" if demo_role == "Platform Owner" else "Dashboard"
            st.rerun()

def top_nav() -> str:
    pages = available_pages()
    current = st.session_state.active_page if st.session_state.active_page in pages else pages[0]
    st.session_state.active_page = current
    account_label = "Platform owner" if is_platform_owner() else "Workspace user"
    org = st.session_state.get("organization_name", "Workspace")
    st.markdown(
        f"""
        <div class="es-topbar">
          <div class="es-brand-row">
            <div class="es-brand">🌐 ErrorSweep <small>{escape(APP_VERSION)} · {escape(account_label)} · {escape(org)} · signed in as {escape(str(st.session_state.username or 'demo user'))}</small></div>
            <span class="es-pill">{escape(str(st.session_state.role))}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([5, 1])
    selected = c1.selectbox("Open page", pages, index=pages.index(current), label_visibility="visible")
    if c2.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.role = "Client Viewer"
        st.session_state.account_type = "workspace_user"
        st.session_state.active_page = "Dashboard"
        st.rerun()
    st.session_state.active_page = selected
    return selected


def access_denied_page(page: str) -> None:
    page_header("Access restricted", page, "Your current role does not have permission to open this workspace area.")
    st.warning(f"Signed in as {st.session_state.get('role', 'User')}. Ask a workspace owner or platform owner for access.")


# ==========================================================
# Pages
# ==========================================================

def dashboard_page() -> None:
    page_header("Dashboard", "Localization operations hub", "Manage projects, jobs, QA reports, human review, scorecards, and translation memory from one workspace.")
    metric_cards([
        ("Projects", len(st.session_state.projects), "client/product workspaces"),
        ("Jobs", len(st.session_state.jobs), "QA / Pro / Scorecard"),
        ("TM Entries", len(st.session_state.tm_entries), "approved translations"),
        ("Pending Review", len([s for s in st.session_state.review_segments if s.get("Status") != "Approved"]), "segments or sessions"),
    ])
    st.markdown("### Recommended next steps")
    st.markdown("""
    <div class="es-grid-3">
      <div class="es-card"><h3>🗂️ Create a project</h3><p>Set languages, domain, and reusable rules.</p></div>
      <div class="es-card"><h3>🚀 Run QA or Pro</h3><p>Generate review-ready output with the main API.</p></div>
      <div class="es-card"><h3>✍️ Human Review</h3><p>Upload files directly, edit segments, and save verified translations to TM.</p></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("### Recent jobs")
    if st.session_state.jobs:
        st.dataframe(pd.DataFrame(st.session_state.jobs).tail(10), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet.")


def projects_page() -> None:
    page_header("Projects", "Project workspaces", "Create client/product workspaces and attach languages, domain, rules, and memory.")
    with st.form("create_project"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Project name", placeholder="Mobile App UI")
        organization = c1.text_input("Organization", placeholder="Nawin Corp")
        source_lang = c2.selectbox("Source language", SUPPORTED_LANGUAGES, index=SUPPORTED_LANGUAGES.index("English"))
        targets = c2.multiselect("Target languages", SUPPORTED_LANGUAGES, default=["French"])
        domain = c3.selectbox("Domain", DOMAINS[1:], index=0)
        status = c3.selectbox("Status", ["Active", "Draft", "Paused"])
        if st.form_submit_button("Create project", type="primary", use_container_width=True):
            if not name:
                st.error("Project name is required.")
            else:
                st.session_state.projects.append({
                    "Project ID": new_id("prj"), "Project": name, "Organization": organization or "Default Organization",
                    "Source": source_lang, "Targets": ", ".join(targets), "Domain": domain,
                    "Status": status, "Created": now_iso(),
                })
                st.success("Project created.")
    st.markdown("### Project list")
    if st.session_state.projects:
        st.dataframe(pd.DataFrame(st.session_state.projects), use_container_width=True, hide_index=True)
    else:
        st.info("Create your first project.")


def jobs_page() -> None:
    page_header("Jobs", "Job center", "Track QA, Pro translation, Human Review, and Scorecard jobs.")
    if st.session_state.jobs:
        df = pd.DataFrame(st.session_state.jobs)
        status_filter = st.multiselect("Filter status", sorted(df["Status"].dropna().unique().tolist()), default=[])
        if status_filter:
            df = df[df["Status"].isin(status_filter)]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet. Run QA, Pro, Human Review, or Scorecard to create jobs.")


def qa_page() -> None:
    page_header("ErrorSweep QA", "QA run + suggestions", "Review existing translations against deterministic checks, company rules, and main API QA.")
    uploaded = st.file_uploader("Upload bilingual file", type=["xlsx", "csv", "docx", "txt"], key="qa_upload")
    rules_zip = st.file_uploader("Upload rules ZIP (optional)", type=["zip"], key="qa_rules")
    c1, c2, c3 = st.columns(3)
    target_language = c1.selectbox("Target language", SUPPORTED_LANGUAGES, index=SUPPORTED_LANGUAGES.index("French"), key="qa_lang")
    domain = c2.selectbox("Domain", DOMAINS, key="qa_domain")
    run_ai = c3.checkbox("Run main API QA", value=True)
    if st.button("Run ErrorSweep QA", type="primary", use_container_width=True, disabled=uploaded is None):
        glossary, dnt, rule_context = parse_rules_zip(rules_zip)
        extracted = extract_file(uploaded, mode="qa")
        if domain == "Auto-detect":
            domain = infer_domain_from_texts([s.get("source") or s.get("target", "") for s in extracted.segments])
        segments = extracted.segments
        if not segments:
            st.error("No reviewable segments found.")
            return
        rows = deterministic_qa(segments, glossary + st.session_state.glossary, dnt + st.session_state.dnt_terms, target_language)
        if run_ai:
            rows.extend(qa_with_main_api(segments, target_language, domain, rule_context))
        job = {"Job ID": new_id("job"), "Type": "QA", "File": uploaded.name, "Project": "", "Target": target_language, "Segments": len(segments), "Issues": len(rows), "Status": "Needs Review" if rows else "Completed", "Created": now_iso()}
        st.session_state.jobs.append(job)
        for seg in segments:
            st.session_state.review_segments.append({
                "Review ID": new_id("rev"), "Job ID": job["Job ID"], "Location": seg["location"], "Source": seg.get("source", ""),
                "Target": seg.get("target", ""), "Status": "Needs Review" if any(r.get("Location") == seg["location"] for r in rows) else "Pass",
                "Match": status_for_segment(seg.get("source", ""), seg.get("target", ""), seg.get("origin_status", "")),
                "Comment": "", "Target Language": target_language,
            })
        st.success("QA completed and Human Review session prepared.")
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.download_button("Download QA report", pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"), "errorsweep_qa_report.csv", "text/csv", use_container_width=True)
        else:
            st.success("No deterministic/API issues found.")


def pro_page() -> None:
    page_header("ErrorSweep Pro", "Translate + QA + Human Review", "Use the main API first, then route uncertain segments to Human Review.")
    uploaded = st.file_uploader("Upload source or bilingual file", type=["xlsx", "csv", "docx", "txt", "json", "xml", "xlf", "xliff", "srt"], key="pro_upload")
    rules_zip = st.file_uploader("Upload rules ZIP (optional)", type=["zip"], key="pro_rules")
    c1, c2, c3 = st.columns([1, 1, 1])
    target_language = c1.selectbox("Target language", SUPPORTED_LANGUAGES, index=SUPPORTED_LANGUAGES.index("French"), key="pro_lang")
    domain = c2.selectbox("Domain", DOMAINS, key="pro_domain")
    review_threshold = c3.slider("Allow with review threshold", min_value=0, max_value=25, value=12, help="If unresolved rows are below this percent, download is allowed but Human Review is required.")
    run_ai_review = st.checkbox("Run main API QA after translation", value=True)
    if st.button("Run Translate + Review", type="primary", use_container_width=True, disabled=uploaded is None):
        if get_openai_client() is None:
            st.error("Main API is not configured. Human Review can still be used without API from the Human Review page.")
            return
        glossary, dnt, rule_context = parse_rules_zip(rules_zip)
        extracted = extract_file(uploaded, mode="pro")
        if not extracted.segments:
            st.error("No source segments found.")
            return
        if domain == "Auto-detect":
            domain = infer_domain_from_texts([s.get("source", "") for s in extracted.segments])
            st.info(f"Domain auto-detected as: {domain}")
        with st.spinner("Translating with main API..."):
            translations_by_loc = translate_with_main_api(extracted.segments, target_language, domain, rule_context)
        translated_segments = []
        missing = []
        for seg in extracted.segments:
            tr = translations_by_loc.get(seg["location"], "")
            if is_bad_translation(seg.get("source", ""), tr, target_language):
                missing.append({"Location": seg["location"], "Source": seg.get("source", ""), "Reason": "Blank, copied, placeholder-only, or invalid output"})
                tr = NEEDS_REVIEW_MARKER
                translations_by_loc[seg["location"]] = tr
            translated_segments.append({**seg, "translation": tr, "target": tr, "origin_status": "MT"})
        gate, message = smart_gate(len(missing), len(extracted.segments), review_threshold / 100)
        if gate == "pass":
            st.success(message)
            status = "Completed"
        elif gate == "review":
            st.warning(message)
            status = "Needs Human Review"
        else:
            st.error(message)
            status = "Blocked"
        review_rows = deterministic_qa(translated_segments, glossary + st.session_state.glossary, dnt + st.session_state.dnt_terms, target_language)
        if gate != "block" and run_ai_review:
            with st.spinner("Running main API QA..."):
                review_rows.extend(qa_with_main_api(translated_segments, target_language, domain, rule_context))
        output_bytes, mime, output_name = build_output_file(extracted, translations_by_loc)
        job = {"Job ID": new_id("job"), "Type": "Pro", "File": uploaded.name, "Project": "", "Target": target_language, "Segments": len(extracted.segments), "Issues": len(review_rows), "Status": status, "Created": now_iso()}
        st.session_state.jobs.append(job)
        for seg in translated_segments:
            unresolved = seg["translation"] == NEEDS_REVIEW_MARKER or any(r.get("Location") == seg["location"] for r in review_rows)
            st.session_state.review_segments.append({
                "Review ID": new_id("rev"), "Job ID": job["Job ID"], "Location": seg["location"], "Source": seg["source"], "Target": seg["translation"],
                "Status": "Needs Review" if unresolved else "MT", "Match": status_for_segment(seg.get("source", ""), seg.get("translation", ""), "MT"),
                "Comment": "", "Target Language": target_language,
            })
        st.markdown("### Translation preview")
        st.dataframe(pd.DataFrame([{"Location": s["location"], "Source": truncate(s["source"]), "Translation": truncate(s["translation"])} for s in translated_segments[:100]]), use_container_width=True, hide_index=True)
        if missing:
            with st.expander("Unresolved segments", expanded=True):
                st.dataframe(pd.DataFrame(missing), use_container_width=True, hide_index=True)
        if gate != "block":
            if gate == "review":
                st.warning("Human Review Required before delivery.")
            st.download_button("Download translated output", output_bytes, output_name, mime, use_container_width=True)
            st.download_button("Download issue report", pd.DataFrame(review_rows).to_csv(index=False).encode("utf-8-sig"), "errorsweep_pro_issue_report.csv", "text/csv", use_container_width=True)
        if st.button("Open Human Review", use_container_width=True):
            st.session_state.active_page = "Human Review"
            st.rerun()


def load_review_file_into_session(uploaded, target_language: str) -> None:
    extracted = extract_file(uploaded, mode="review")
    job_id = new_id("job")
    st.session_state.jobs.append({"Job ID": job_id, "Type": "Human Review", "File": uploaded.name, "Project": "", "Target": target_language, "Segments": len(extracted.segments), "Issues": 0, "Status": "In Review", "Created": now_iso()})
    for seg in extracted.segments:
        st.session_state.review_segments.append({
            "Review ID": new_id("rev"), "Job ID": job_id, "Location": seg["location"], "Source": seg.get("source", ""), "Target": seg.get("target", ""),
            "Status": "Existing" if seg.get("target") else "Needs Review", "Match": status_for_segment(seg.get("source", ""), seg.get("target", ""), seg.get("origin_status", "")),
            "Comment": "", "Target Language": target_language,
        })


def human_review_page() -> None:
    page_header("Human Review", "CAT-style segment editor", "Upload a file directly, edit target boxes, view glossary/DNT/TM matches, and approve verified translations.")
    with st.expander("Upload file directly for Human Review", expanded=not bool(st.session_state.review_segments)):
        c1, c2 = st.columns([2, 1])
        review_upload = c1.file_uploader("Upload source/bilingual/reviewer file", type=["xlsx", "csv", "docx", "txt"], key="hr_direct_upload")
        target_language = c2.selectbox("Target language", SUPPORTED_LANGUAGES, index=SUPPORTED_LANGUAGES.index("French"), key="hr_lang")
        if st.button("Load into Human Review", type="primary", use_container_width=True, disabled=review_upload is None):
            load_review_file_into_session(review_upload, target_language)
            st.success("File loaded into Human Review.")
            st.rerun()

    if not st.session_state.review_segments:
        st.info("No review segments yet. Upload a file above or run ErrorSweep QA/Pro first.")
        return

    df = pd.DataFrame(st.session_state.review_segments)
    fc1, fc2, fc3 = st.columns(3)
    job_filter = fc1.selectbox("Job", ["All"] + sorted(df["Job ID"].dropna().unique().tolist()))
    status_filter = fc2.selectbox("Status", ["All"] + sorted(df["Status"].dropna().unique().tolist()))
    search = fc3.text_input("Search source/target")
    filtered = df.copy()
    if job_filter != "All":
        filtered = filtered[filtered["Job ID"] == job_filter]
    if status_filter != "All":
        filtered = filtered[filtered["Status"] == status_filter]
    if search:
        filtered = filtered[filtered["Source"].astype(str).str.contains(search, case=False, na=False) | filtered["Target"].astype(str).str.contains(search, case=False, na=False)]
    if filtered.empty:
        st.info("No matching segments.")
        return

    selected_id = st.session_state.get("selected_review_id") or filtered.iloc[0]["Review ID"]
    if selected_id not in filtered["Review ID"].tolist():
        selected_id = filtered.iloc[0]["Review ID"]

    st.markdown("### Review workspace")
    left, center, right = st.columns([0.95, 1.15, 0.85])
    with left:
        st.markdown("#### Source segments")
        st.markdown('<div class="es-segment-list">', unsafe_allow_html=True)
        for _, row in filtered.head(250).iterrows():
            rid = row["Review ID"]
            selected = rid == selected_id
            badge_class = "es-badge-green" if row.get("Status") == "Approved" else ("es-badge-yellow" if "fuzzy" in str(row.get("Match", "")).lower() else "es-badge-cyan")
            label = f"{row.get('Location','')} · {row.get('Match','')} · {row.get('Status','')}"
            if st.button(label, key=f"open_{rid}", use_container_width=True):
                st.session_state.selected_review_id = rid
                st.rerun()
            st.markdown(f"""
            <div class="es-seg-item" style="border-color:{'rgba(0,231,133,.55)' if selected else 'rgba(125,145,255,.16)'}">
              <span class="es-badge {badge_class}">{escape(str(row.get('Match','')))}</span>
              <div class="es-seg-source">{escape(truncate(row.get('Source',''), 210))}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    idx = next((i for i, s in enumerate(st.session_state.review_segments) if s["Review ID"] == selected_id), None)
    if idx is None:
        return
    seg = st.session_state.review_segments[idx]

    with center:
        st.markdown("#### Target editor")
        st.caption(f"{seg.get('Location','')} · {seg.get('Target Language','')} · {seg.get('Match','')}")
        st.text_area("Source", value=seg.get("Source", ""), height=150, disabled=True)
        edited = st.text_area("Target", value=seg.get("Target", ""), height=190)
        status_options = ["Needs Review", "MT", "Existing", "101%", "100%", "Fuzzy", "Approved", "Rejected", "Needs Rework"]
        current_status = seg.get("Status", "Needs Review")
        status = st.selectbox("Segment status", status_options, index=status_options.index(current_status) if current_status in status_options else 0)
        comment = st.text_area("Reviewer comment", value=seg.get("Comment", ""), height=80)
        b1, b2, b3 = st.columns(3)
        if b1.button("Save", use_container_width=True):
            st.session_state.review_segments[idx].update({"Target": edited, "Status": status, "Comment": comment})
            st.success("Segment saved.")
        if b2.button("Approve", type="primary", use_container_width=True):
            st.session_state.review_segments[idx].update({"Target": edited, "Status": "Approved", "Comment": comment})
            st.success("Segment approved.")
        if b3.button("Approve + TM", use_container_width=True):
            st.session_state.review_segments[idx].update({"Target": edited, "Status": "Approved", "Comment": comment})
            st.session_state.tm_entries.append({"TM ID": new_id("tm"), "Source Hash": text_hash(seg.get("Source", "")), "Source": seg.get("Source", ""), "Target": edited, "Target Language": seg.get("Target Language", ""), "Domain": "", "Approved By": st.session_state.username, "Created": now_iso()})
            st.success("Approved and saved to TM.")

    with right:
        st.markdown("#### Glossary · DNT · TM")
        source = seg.get("Source", "")
        glossary_matches = [g for g in st.session_state.glossary if g.get("Source Term", "").lower() in source.lower()]
        dnt_matches = [d for d in st.session_state.dnt_terms if d.get("Term", "").lower() in source.lower()]
        match, tm_target = best_tm_match(source)
        st.markdown('<div class="es-assist-box"><span class="es-badge es-badge-green">TM match</span>', unsafe_allow_html=True)
        st.write(match)
        if tm_target:
            st.text_area("TM target", value=tm_target, height=90, disabled=True, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="es-assist-box"><span class="es-badge es-badge-cyan">Glossary</span>', unsafe_allow_html=True)
        if glossary_matches:
            st.dataframe(pd.DataFrame(glossary_matches), use_container_width=True, hide_index=True)
        else:
            st.caption("No glossary matches.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="es-assist-box"><span class="es-badge es-badge-red">DNT</span>', unsafe_allow_html=True)
        if dnt_matches:
            st.dataframe(pd.DataFrame(dnt_matches), use_container_width=True, hide_index=True)
        else:
            st.caption("No DNT matches.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Bulk target grid")
    bulk_df = pd.DataFrame(st.session_state.review_segments)
    edited_df = st.data_editor(bulk_df[["Review ID", "Location", "Match", "Status", "Source", "Target", "Comment"]], use_container_width=True, hide_index=True, disabled=["Review ID", "Location", "Match", "Source"])
    if st.button("Save bulk grid changes", use_container_width=True):
        by_id = {row["Review ID"]: row for _, row in edited_df.iterrows()}
        for i, row in enumerate(st.session_state.review_segments):
            rid = row["Review ID"]
            if rid in by_id:
                st.session_state.review_segments[i]["Target"] = str(by_id[rid].get("Target", ""))
                st.session_state.review_segments[i]["Status"] = str(by_id[rid].get("Status", ""))
                st.session_state.review_segments[i]["Comment"] = str(by_id[rid].get("Comment", ""))
        st.success("Bulk changes saved.")
    st.download_button("Download Human Review CSV", build_review_export(st.session_state.review_segments), "human_review_segments.csv", "text/csv", use_container_width=True)


def scorecards_page() -> None:
    page_header("Scorecards", "Translator vs reviewer quality score", "Compare translator output with reviewer/final output and generate vendor quality scorecards. Source file is optional.")
    source_file = st.file_uploader("Source file (optional)", type=["xlsx", "csv", "docx", "txt"], key="score_src")
    translator_file = st.file_uploader("Translator file", type=["xlsx", "csv", "docx", "txt"], key="score_trans")
    reviewer_file = st.file_uploader("Reviewer/final file", type=["xlsx", "csv", "docx", "txt"], key="score_rev")
    if st.button("Generate Scorecard", type="primary", use_container_width=True, disabled=not (translator_file and reviewer_file)):
        src = extract_file(source_file, mode="review") if source_file else None
        trans = extract_file(translator_file, mode="review")
        rev = extract_file(reviewer_file, mode="review")
        rows = []
        total_penalty = 0
        total = min(len(trans.segments), len(rev.segments))
        for i in range(total):
            t_seg = trans.segments[i]
            r_seg = rev.segments[i]
            source = src.segments[i].get("source", "") if src and i < len(src.segments) else (t_seg.get("source") or r_seg.get("source", ""))
            translator = t_seg.get("translation") or t_seg.get("target") or t_seg.get("source", "")
            reviewer = r_seg.get("translation") or r_seg.get("target") or r_seg.get("source", "")
            changed = clean_text(translator) != clean_text(reviewer)
            penalty = 0
            severity = "Pass"
            category = "No change"
            if changed:
                penalty = 2
                severity = "Minor"
                category = "Reviewer changed translation"
                if extract_placeholders(translator) != extract_placeholders(reviewer):
                    penalty = 10
                    severity = "Critical"
                    category = "Placeholder/formatting"
                elif len(clean_text(translator)) < max(1, len(clean_text(reviewer)) * 0.35):
                    penalty = 5
                    severity = "Major"
                    category = "Omission / incompleteness"
            total_penalty += penalty
            rows.append({"Segment": i + 1, "Source": source, "Translator": translator, "Reviewer": reviewer, "Changed": "Yes" if changed else "No", "Category": category, "Severity": severity, "Penalty": penalty})
        score = max(0, round(100 - (total_penalty / max(total, 1)), 2))
        job = {"Job ID": new_id("job"), "Type": "Scorecard", "File": translator_file.name, "Project": "", "Target": "", "Segments": total, "Issues": sum(1 for r in rows if r["Changed"] == "Yes"), "Status": "Completed", "Created": now_iso()}
        st.session_state.jobs.append(job)
        metric_cards([("Quality Score", score, "100 is best"), ("Segments", total, "compared rows"), ("Changed", sum(1 for r in rows if r["Changed"] == "Yes"), "reviewer edits"), ("Penalty", total_penalty, "weighted penalty")])
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download Scorecard Excel", download_excel(df, "Scorecard"), "errorsweep_scorecard.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def memory_rules_page() -> None:
    page_header("Memory & Rules", "Translation memory, glossary, DNT, and rule packs", "Manage approved terminology and reusable corrections.")
    tab1, tab2, tab3, tab4 = st.tabs(["Translation Memory", "Glossary", "DNT", "Rule Pack Upload"])
    with tab1:
        if st.session_state.tm_entries:
            st.dataframe(pd.DataFrame(st.session_state.tm_entries), use_container_width=True, hide_index=True)
        else:
            st.info("No TM entries yet. Approve segments in Human Review to build TM.")
        with st.form("add_tm"):
            source = st.text_area("Source")
            target = st.text_area("Target")
            lang = st.selectbox("Target language", SUPPORTED_LANGUAGES, key="tm_lang")
            if st.form_submit_button("Add TM entry", use_container_width=True):
                if source and target:
                    st.session_state.tm_entries.append({"TM ID": new_id("tm"), "Source Hash": text_hash(source), "Source": source, "Target": target, "Target Language": lang, "Domain": "", "Approved By": st.session_state.username, "Created": now_iso()})
                    st.success("TM entry added.")
    with tab2:
        with st.form("add_glossary"):
            s = st.text_input("Source term")
            t = st.text_input("Target term")
            src = st.text_input("Rule source", value="Manual")
            if st.form_submit_button("Add glossary term", use_container_width=True) and s and t:
                st.session_state.glossary.append({"Source Term": s, "Target Term": t, "Rule Source": src})
                st.success("Glossary term added.")
        if st.session_state.glossary:
            st.dataframe(pd.DataFrame(st.session_state.glossary), use_container_width=True, hide_index=True)
    with tab3:
        with st.form("add_dnt"):
            term = st.text_input("DNT term")
            src = st.text_input("Rule source", value="Manual")
            if st.form_submit_button("Add DNT term", use_container_width=True) and term:
                st.session_state.dnt_terms.append({"Term": term, "Rule Source": src})
                st.success("DNT term added.")
        if st.session_state.dnt_terms:
            st.dataframe(pd.DataFrame(st.session_state.dnt_terms), use_container_width=True, hide_index=True)
    with tab4:
        rules_zip = st.file_uploader("Upload rules ZIP", type=["zip"], key="rules_manager_zip")
        if rules_zip and st.button("Parse and save rules", use_container_width=True):
            glossary, dnt, _ = parse_rules_zip(rules_zip)
            st.session_state.glossary.extend(glossary)
            st.session_state.dnt_terms.extend(dnt)
            st.success(f"Loaded {len(glossary)} glossary term(s) and {len(dnt)} DNT term(s).")


def team_roles_page() -> None:
    page_header("Team & Roles", "Workspace user access", "Invite users, assign workspace roles, and keep platform-owner controls separate.")
    permission_rows = [
        {"Action": "Create projects", "Platform Owner": "All workspaces", "Workspace Owner": "Yes", "Workspace Admin": "Yes", "PM": "Yes", "Translator": "No", "Reviewer": "No", "Client": "No"},
        {"Action": "Run Pro translation", "Platform Owner": "Yes", "Workspace Owner": "Yes", "Workspace Admin": "Yes", "PM": "Yes", "Translator": "No", "Reviewer": "No", "Client": "No"},
        {"Action": "Human Review editing", "Platform Owner": "Yes", "Workspace Owner": "Yes", "Workspace Admin": "Yes", "PM": "Yes", "Translator": "Assigned only", "Reviewer": "Yes", "Client": "No"},
        {"Action": "Approve segments", "Platform Owner": "Yes", "Workspace Owner": "Yes", "Workspace Admin": "Yes", "PM": "Yes", "Translator": "No", "Reviewer": "Yes", "Client": "No"},
        {"Action": "Save to TM", "Platform Owner": "Yes", "Workspace Owner": "Yes", "Workspace Admin": "Yes", "PM": "Yes", "Translator": "No", "Reviewer": "Yes", "Client": "No"},
        {"Action": "Billing", "Platform Owner": "View all", "Workspace Owner": "Yes", "Workspace Admin": "No", "PM": "No", "Translator": "No", "Reviewer": "No", "Client": "No"},
        {"Action": "Platform settings", "Platform Owner": "Yes", "Workspace Owner": "No", "Workspace Admin": "No", "PM": "No", "Translator": "No", "Reviewer": "No", "Client": "No"},
    ]
    st.dataframe(pd.DataFrame(permission_rows), use_container_width=True, hide_index=True)
    if st.session_state.role not in {"Platform Owner", "Workspace Owner", "Workspace Admin"}:
        st.info("Your role can view permissions but cannot invite or modify users.")
        return
    with st.form("invite_user"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name")
        email = c2.text_input("Email")
        role_options = WORKSPACE_ROLES if not is_platform_owner() else ROLES
        role = c3.selectbox("Role", role_options)
        if st.form_submit_button("Add / invite user", use_container_width=True) and name and email:
            st.session_state.team.append({"Name": name, "Email": email, "Role": role, "Status": "Invited"})
            st.success("User added.")
    st.dataframe(pd.DataFrame(st.session_state.team), use_container_width=True, hide_index=True)

def billing_page() -> None:
    page_header("Billing", "Plans and usage", "Plan limits, credit history, invoices, and payment gateway setup.")
    plans = [
        ("Trial", "Demo", "Internal testing while platform is built"),
        ("Pro", "Coming soon", "API translation + QA + Human Review"),
        ("Agency", "Coming soon", "Projects, team roles, scorecards, and TM"),
        ("Enterprise", "Custom", "Private workflows and admin controls"),
    ]
    metric_cards(plans)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Usage")
        metric_cards([("Credits", "Unlimited", "during build"), ("Jobs", len(st.session_state.jobs), "current workspace")])
    with c2:
        st.markdown("### Invoices")
        st.info("Invoices and Razorpay/Stripe integration will be connected after the core project/job/review workflow is stable.")
        st.dataframe(pd.DataFrame(columns=["Invoice", "Date", "Amount", "Status"]), use_container_width=True, hide_index=True)


def account_page() -> None:
    page_header("Account", "Profile and workspace context", "View your account type, role, and workspace membership.")
    metric_cards([
        ("Account Type", "Platform Owner" if is_platform_owner() else "Workspace User", "permission boundary"),
        ("Role", st.session_state.role, "current access level"),
        ("Workspace", st.session_state.get("organization_name", "Workspace"), "active organization"),
        ("Email", st.session_state.username or "demo", "signed-in identity"),
    ])
    st.markdown("### Profile")
    with st.form("account_settings"):
        username = st.text_input("Email / username", value=st.session_state.username)
        org = st.text_input("Organization", value=st.session_state.get("organization_name", "Demo Workspace"), disabled=not is_platform_owner() and st.session_state.role not in {"Workspace Owner", "Workspace Admin"})
        timezone = st.text_input("Time zone", value="Asia/Kolkata")
        st.caption("Roles are assigned from Team & Roles or Platform Owner Console. Regular users cannot self-upgrade.")
        if st.form_submit_button("Save profile", use_container_width=True):
            st.session_state.username = username
            if not (not is_platform_owner() and st.session_state.role not in {"Workspace Owner", "Workspace Admin"}):
                st.session_state.organization_name = org
            st.success("Profile saved.")
    if is_platform_owner():
        st.markdown("### Owner demo role switcher")
        new_role = st.selectbox("Preview workspace as role", ROLES, index=ROLES.index(st.session_state.role) if st.session_state.role in ROLES else 0)
        if st.button("Switch current demo role", use_container_width=True):
            st.session_state.role = new_role
            st.session_state.account_type = "platform_owner" if new_role == "Platform Owner" else "workspace_user"
            st.session_state.active_page = "Platform Owner Console" if new_role == "Platform Owner" else "Dashboard"
            st.rerun()

def admin_page() -> None:
    page_header("Admin", "Workspace admin", "Workspace-level settings only. Platform-owner controls are kept separate.")
    if st.session_state.role not in {"Workspace Owner", "Workspace Admin"}:
        access_denied_page("Admin")
        return
    st.markdown("### Workspace controls")
    c1, c2 = st.columns(2)
    st.session_state.admin_flags["allow_demo_users"] = c1.toggle("Allow demo workspace users", value=bool(st.session_state.admin_flags.get("allow_demo_users", True)))
    st.session_state.admin_flags["billing_enabled"] = c2.toggle("Billing enabled for this workspace", value=bool(st.session_state.admin_flags.get("billing_enabled", False)))
    st.markdown("### Workspace summary")
    metric_cards([("Projects", len(st.session_state.projects), "workspace projects"), ("Jobs", len(st.session_state.jobs), "workspace jobs"), ("TM", len(st.session_state.tm_entries), "approved entries"), ("Review", len(st.session_state.review_segments), "segments")])
    st.markdown("### Maintenance")
    c1, c2 = st.columns(2)
    if c1.button("Clear jobs/review only", use_container_width=True):
        st.session_state.jobs = []
        st.session_state.review_segments = []
        st.success("Jobs and review sessions cleared.")
    if c2.button("Clear workspace demo data", use_container_width=True):
        for key in ["projects", "jobs", "tm_entries", "glossary", "dnt_terms", "review_segments"]:
            st.session_state[key] = []
        st.success("Workspace demo data cleared.")
    st.info("Technical connector names, API secrets, and platform-level controls are hidden from workspace users.")


def platform_owner_console_page() -> None:
    page_header("Platform Owner Console", "Global platform control", "Manage workspaces, plans, global settings, and product-level diagnostics.")
    if not is_platform_owner():
        access_denied_page("Platform Owner Console")
        return
    metric_cards([
        ("Workspaces", len(st.session_state.workspaces), "customer organizations"),
        ("Users", len(st.session_state.team), "demo users in current data"),
        ("Jobs", len(st.session_state.jobs), "current session jobs"),
        ("Mode", "Build", "billing and engines optional"),
    ])
    tab1, tab2, tab3, tab4 = st.tabs(["Workspaces", "Plans", "Feature Flags", "Security"])
    with tab1:
        with st.form("create_workspace"):
            c1, c2, c3 = st.columns(3)
            workspace = c1.text_input("Workspace name")
            owner = c2.text_input("Owner email")
            plan = c3.selectbox("Plan", ["Trial", "Pro", "Agency", "Enterprise"])
            if st.form_submit_button("Create workspace", use_container_width=True) and workspace:
                st.session_state.workspaces.append({"Workspace": workspace, "Owner": owner, "Plan": plan, "Status": "Active", "Users": 1})
                st.success("Workspace created.")
        st.dataframe(pd.DataFrame(st.session_state.workspaces), use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(pd.DataFrame([
            {"Plan": "Trial", "Credits": "Demo", "Projects": 1, "Human Review": "Yes", "Scorecards": "Limited"},
            {"Plan": "Pro", "Credits": "Monthly", "Projects": 5, "Human Review": "Yes", "Scorecards": "Yes"},
            {"Plan": "Agency", "Credits": "High volume", "Projects": "Unlimited", "Human Review": "Yes", "Scorecards": "Yes"},
            {"Plan": "Enterprise", "Credits": "Custom", "Projects": "Custom", "Human Review": "Yes", "Scorecards": "Yes"},
        ]), use_container_width=True, hide_index=True)
    with tab3:
        st.session_state.admin_flags["main_api_required"] = st.toggle("Main API required for Pro translation", value=True)
        st.session_state.admin_flags["show_local_engine_options"] = st.toggle("Show local/free engine options to users", value=False)
        st.session_state.admin_flags["scorecards_enabled"] = st.toggle("Enable scorecards", value=True)
        st.session_state.admin_flags["human_review_enabled"] = st.toggle("Enable Human Review", value=True)
        st.caption("Local/free engine names remain hidden unless explicitly enabled here.")
    with tab4:
        st.info("Production security roadmap: Supabase Auth, organization IDs, row-level security, audit logs, SSO, and owner-only impersonation.")
        st.dataframe(pd.DataFrame([
            {"Control": "Owner/user account separation", "Status": "MVP implemented"},
            {"Control": "Workspace-level admin", "Status": "MVP implemented"},
            {"Control": "Role-based page filtering", "Status": "MVP implemented"},
            {"Control": "Persistent database permissions", "Status": "Next Supabase sprint"},
        ]), use_container_width=True, hide_index=True)


# ==========================================================
# Router
# ==========================================================

def render_app() -> None:
    page = top_nav()
    if not can_access(page):
        access_denied_page(page)
    elif page == "Dashboard":
        dashboard_page()
    elif page == "Projects":
        projects_page()
    elif page == "Jobs":
        jobs_page()
    elif page == "ErrorSweep QA":
        qa_page()
    elif page == "ErrorSweep Pro":
        pro_page()
    elif page == "Human Review":
        human_review_page()
    elif page == "Scorecards":
        scorecards_page()
    elif page == "Memory & Rules":
        memory_rules_page()
    elif page == "Team & Roles":
        team_roles_page()
    elif page == "Billing":
        billing_page()
    elif page == "Account":
        account_page()
    elif page == "Admin":
        admin_page()
    elif page == "Platform Owner Console":
        platform_owner_console_page()
    else:
        dashboard_page()


    st.markdown('<div class="es-footer-note">ErrorSweep website platform shell · Main API first · Local/free engines hidden until production-ready.</div>', unsafe_allow_html=True)


if not st.session_state.authenticated:
    login_page()
else:
    render_app()

