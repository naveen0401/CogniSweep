
from __future__ import annotations

import io
import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st
from docx import Document
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from local_translation_engine import (
    has_local_translation_engine,
    preflight_translation_engine,
    local_translate_batch_adapter,
    find_missing_or_bad_translations,
    select_translation_route,
)
from qa_engine_global_v17 import deterministic_checks_v2, normalize_text_for_qa


APP_VERSION = "v17-clean-reset"
SUPPORTED_UPLOADS = ["xlsx", "csv", "docx", "txt", "json", "xml", "xliff", "xlf", "srt", "po", "yaml", "yml"]


# ==========================================================
# Page setup / visual system
# ==========================================================

st.set_page_config(page_title="ErrorSweep", layout="wide", page_icon="🌐")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] { font-family: Inter, sans-serif; }
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stDeployButton"], .stAppDeployButton {
    visibility: hidden !important;
    display: none !important;
}

.stApp {
    background:
      radial-gradient(circle at 6% 12%, rgba(0,255,136,.16), transparent 26%),
      radial-gradient(circle at 88% 9%, rgba(56,189,248,.14), transparent 28%),
      radial-gradient(circle at 48% 98%, rgba(168,85,247,.12), transparent 36%),
      #070911;
    color: #f8fafc;
}

.es-hero {
    background:
      linear-gradient(135deg, rgba(0,255,136,.12), rgba(56,189,248,.08) 42%, rgba(139,92,246,.12)),
      rgba(15, 20, 36, .86);
    border: 1px solid rgba(125, 211, 252, .18);
    border-radius: 24px;
    padding: 34px 34px 28px;
    box-shadow: 0 32px 90px rgba(0,0,0,.35);
    margin: 8px 0 22px;
}
.es-title {
    font-family: Space Mono, monospace;
    font-size: 44px;
    font-weight: 800;
    margin: 0;
    background: linear-gradient(90deg, #00ff88, #38bdf8, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.es-subtitle { color: #c7d2fe; font-size: 15px; margin-top: 8px; }
.es-pill {
    display: inline-block;
    background: rgba(0,255,136,.08);
    border: 1px solid rgba(0,255,136,.25);
    color: #86efac;
    border-radius: 999px;
    padding: 6px 14px;
    margin-top: 14px;
    font-family: Space Mono, monospace;
    font-size: 12px;
}
.es-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin: 16px 0 22px;
}
.es-card {
    background: rgba(16, 19, 34, .78);
    border: 1px solid rgba(56,189,248,.16);
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 18px 44px rgba(0,0,0,.2);
}
.es-card h4 { margin: 0 0 6px 0; color: #f8fafc; }
.es-card p { margin: 0; color: #94a3b8; font-size: 13px; }
.es-note {
    background: rgba(15, 23, 42, .84);
    border: 1px solid rgba(96, 165, 250, .18);
    border-radius: 16px;
    padding: 14px 16px;
    margin: 10px 0;
}
.es-error {
    background: rgba(127, 29, 29, .36);
    border: 1px solid rgba(248, 113, 113, .30);
    color: #fecaca;
    border-radius: 14px;
    padding: 15px 17px;
    margin: 12px 0;
}
.es-success {
    background: rgba(5, 150, 105, .18);
    border: 1px solid rgba(52, 211, 153, .28);
    color: #bbf7d0;
    border-radius: 14px;
    padding: 15px 17px;
    margin: 12px 0;
}
.es-small { color:#94a3b8; font-size: 12px; }
.stButton > button, .stDownloadButton > button {
    border-radius: 14px !important;
    border: 1px solid rgba(0,255,136,.25) !important;
    background: linear-gradient(90deg, #00cc6a, #0ea5e9) !important;
    color: white !important;
    font-weight: 800 !important;
    box-shadow: 0 10px 28px rgba(14,165,233,.18);
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
}
[data-testid="stMetric"] {
    background: rgba(16,19,34,.72);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 16px;
    padding: 16px;
}
div[data-testid="stExpander"] {
    background: rgba(16, 19, 34, .64) !important;
    border: 1px solid rgba(56,189,248,.16) !important;
    border-radius: 16px !important;
}
.es-review-box {
    border: 1px solid rgba(125,211,252,.18);
    border-radius: 16px;
    padding: 14px;
    background: rgba(2, 6, 23, .35);
}
@media (max-width: 900px) { .es-grid { grid-template-columns: 1fr; } .es-title { font-size: 34px; } }
</style>
""",
    unsafe_allow_html=True,
)


# ==========================================================
# General helpers
# ==========================================================

def secret(name: str, default: str = "") -> str:
    env = os.environ.get(name)
    if env:
        return env
    try:
        value = st.secrets.get(name, default)
        return value if value is not None else default
    except Exception:
        return default


def runtime_banner() -> None:
    st.markdown(
        f"""
<div class="es-hero">
  <div class="es-title">ErrorSweep</div>
  <div class="es-subtitle">AI localization QA, translation memory, rule packs, human review, and scorecards.</div>
  <div class="es-pill">Runtime {APP_VERSION} · Local engine routing enabled · Quality gate enabled</div>
</div>
<div class="es-grid">
  <div class="es-card"><h4>Secure Review</h4><p>Server-side processing with protected credentials and project-specific rules.</p></div>
  <div class="es-card"><h4>Smart Routing</h4><p>Routes French/Spanish/German to LibreTranslate and Indic languages to IndicTrans2.</p></div>
  <div class="es-card"><h4>Human Review</h4><p>CAT-style source/target editor with glossary, TM, QA issues, and approval workflow.</p></div>
</div>
""",
        unsafe_allow_html=True,
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00A0", " ")
    text = text.replace("\u200B", "")
    return text.strip()


def safe_file_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "file")


def is_target_language_english(target_language: str) -> bool:
    return normalize_text(target_language).lower() in {"english", "en", "eng_latn", "en-us", "en-gb"}


def get_uploaded_bytes(uploaded_file) -> bytes:
    return uploaded_file.getvalue()


def text_from_bytes(data: bytes) -> Tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def protect_private_file_warning() -> None:
    st.caption("Do not commit .env or .streamlit/secrets.toml. They contain private keys.")


# ==========================================================
# Supabase minimal auth/session
# ==========================================================

def supabase_configured() -> bool:
    return bool(secret("SUPABASE_URL") and secret("SUPABASE_ANON_KEY"))


def supabase_base() -> str:
    return secret("SUPABASE_URL").rstrip("/")


def supabase_headers(service: bool = False, access_token: str = "") -> Dict[str, str]:
    key = secret("SUPABASE_SERVICE_ROLE_KEY") if service else secret("SUPABASE_ANON_KEY")
    bearer = access_token or key
    return {"apikey": key, "Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}


def supabase_post(path: str, payload: Dict[str, Any], service: bool = False, access_token: str = "") -> Tuple[bool, Any]:
    try:
        res = requests.post(
            supabase_base() + path,
            headers=supabase_headers(service=service, access_token=access_token),
            json=payload,
            timeout=25,
        )
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


def supabase_get(path: str, service: bool = False, access_token: str = "") -> Tuple[bool, Any]:
    try:
        res = requests.get(
            supabase_base() + path,
            headers=supabase_headers(service=service, access_token=access_token),
            timeout=25,
        )
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
        return str(data.get("message") or data.get("msg") or data.get("error_description") or data)[:800]
    return str(data)[:800]


def sign_in(email: str, password: str) -> Tuple[bool, str]:
    ok, data = supabase_post("/auth/v1/token?grant_type=password", {"email": email, "password": password})
    if not ok:
        return False, format_error(data)
    st.session_state["access_token"] = data.get("access_token")
    st.session_state["user"] = data.get("user") or {"email": email}
    st.session_state["authenticated"] = True
    return True, "Signed in."


def sign_up(email: str, password: str, full_name: str) -> Tuple[bool, str]:
    ok, data = supabase_post("/auth/v1/signup", {"email": email, "password": password, "data": {"full_name": full_name}})
    if not ok:
        return False, format_error(data)
    return True, "Account created. If email confirmation is enabled, confirm your email and sign in."


def current_user() -> Dict[str, Any]:
    return st.session_state.get("user") or {"email": "demo@errorsweep.local", "id": "demo-user"}


def auth_gate() -> bool:
    if st.session_state.get("authenticated"):
        return True

    if not supabase_configured():
        st.warning("Supabase is not configured. Running in local demo mode.")
        if st.button("Continue in demo mode", type="primary"):
            st.session_state["authenticated"] = True
            st.session_state["user"] = {"email": "demo@errorsweep.local", "id": "demo-user"}
            st.rerun()
        return False

    st.markdown("<div class='es-card'><h4>Account required</h4><p>Sign in to ErrorSweep.</p></div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            ok, msg = sign_in(email.strip().lower(), password)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with tab2:
        with st.form("signup"):
            full = st.text_input("Full name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_pw")
            submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if submitted:
            ok, msg = sign_up(email.strip().lower(), password, full)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
    return False


# ==========================================================
# File extraction and output
# ==========================================================

def detect_columns(headers: List[str]) -> Tuple[Optional[int], Optional[int]]:
    source_terms = ["source text", "source", "english", "src"]
    target_terms = ["original translation", "translation", "target", "target text", "localized"]
    h = [normalize_text(x).lower() for x in headers]
    src = tgt = None
    for i, name in enumerate(h):
        if src is None and any(t == name or t in name for t in source_terms):
            src = i
        if tgt is None and any(t == name or t in name for t in target_terms):
            tgt = i
    return src, tgt


def find_docx_table_header(table) -> Tuple[int, Optional[int], Optional[int]]:
    best = (0, None, None, -999)
    for idx, row in enumerate(table.rows[:20]):
        headers = [cell.text.strip() for cell in row.cells]
        src, tgt = detect_columns(headers)
        joined = " | ".join(x.lower() for x in headers)
        score = 0
        if src is not None:
            score += 50
        if tgt is not None:
            score += 50
        if "source text" in joined:
            score += 60
        if "original translation" in joined:
            score += 80
        if score > best[3]:
            best = (idx, src, tgt, score)
    return best[0], best[1], best[2]


def extract_docx(uploaded_file, mode: str) -> Tuple[Document, List[Dict[str, Any]], Dict[str, Any], List[str]]:
    doc = Document(io.BytesIO(get_uploaded_bytes(uploaded_file)))
    segments: List[Dict[str, Any]] = []
    targets: Dict[str, Any] = {}
    logs: List[str] = []

    for t_idx, table in enumerate(doc.tables, start=1):
        header_idx, src_idx, tgt_idx = find_docx_table_header(table)
        if src_idx is None:
            continue
        logs.append(f"DOCX table {t_idx}: column mode [Source] -> [Target]")
        for r_idx in range(header_idx + 1, len(table.rows)):
            row = table.rows[r_idx]
            if src_idx >= len(row.cells):
                continue
            source = normalize_text(row.cells[src_idx].text)
            if not source or source.lower() in {"source", "source text", "target", "translation"}:
                continue
            target = ""
            target_cell = None
            if tgt_idx is not None and tgt_idx < len(row.cells):
                target_cell = row.cells[tgt_idx]
                target = normalize_text(target_cell.text)
            if mode == "qa" and not target:
                continue
            loc = f"Table {t_idx}, Row {r_idx + 1}"
            segments.append(
                {
                    "id": len(segments) + 1,
                    "file_type": "docx",
                    "location": loc,
                    "sheet": f"Table {t_idx}",
                    "source": source,
                    "translation": target,
                    "text": target if mode == "qa" else source,
                    "mode": "bilingual" if target else "source_only",
                }
            )
            if target_cell is not None:
                targets[loc] = target_cell
    if not segments:
        logs.append("DOCX paragraph fallback mode")
        for p_idx, p in enumerate(doc.paragraphs, start=1):
            source = normalize_text(p.text)
            if source and len(source) > 1:
                loc = f"Paragraph {p_idx}"
                segments.append(
                    {
                        "id": len(segments) + 1,
                        "file_type": "docx",
                        "location": loc,
                        "sheet": "Document",
                        "source": source if mode == "pro" else "",
                        "translation": source if mode == "qa" else "",
                        "text": source,
                        "mode": "source_only" if mode == "pro" else "monolingual",
                    }
                )
                targets[loc] = p
    return doc, segments, targets, logs


def extract_xlsx(uploaded_file, mode: str) -> Tuple[Any, List[Dict[str, Any]], Dict[str, Any], List[str]]:
    wb = load_workbook(io.BytesIO(get_uploaded_bytes(uploaded_file)))
    segments: List[Dict[str, Any]] = []
    targets: Dict[str, Any] = {}
    logs: List[str] = []

    for ws in wb.worksheets:
        rows = list(ws.iter_rows())
        if not rows:
            continue
        header_row_idx = 0
        src_idx = tgt_idx = None
        for idx, row in enumerate(rows[:30]):
            headers = [cell.value if cell.value is not None else "" for cell in row]
            src_idx, tgt_idx = detect_columns([str(x) for x in headers])
            if src_idx is not None:
                header_row_idx = idx
                break
        if src_idx is None:
            continue
        logs.append(f"{ws.title}: column mode")
        if mode == "pro" and tgt_idx is None:
            tgt_idx = ws.max_column
            ws.cell(row=header_row_idx + 1, column=tgt_idx + 1).value = "AI Translation"
        for r_idx, row in enumerate(rows[header_row_idx + 1 :], start=header_row_idx + 2):
            if src_idx >= len(row):
                continue
            source = normalize_text(row[src_idx].value)
            if not source:
                continue
            target_cell = ws.cell(row=r_idx, column=(tgt_idx + 1) if tgt_idx is not None else ws.max_column + 1)
            target = normalize_text(target_cell.value)
            if mode == "qa" and not target:
                continue
            loc = f"{ws.title}!R{r_idx}"
            segments.append(
                {
                    "id": len(segments) + 1,
                    "file_type": "xlsx",
                    "location": loc,
                    "sheet": ws.title,
                    "source": source,
                    "translation": target,
                    "text": target if mode == "qa" else source,
                    "mode": "bilingual" if target else "source_only",
                }
            )
            targets[loc] = target_cell
    return wb, segments, targets, logs


def extract_csv(uploaded_file, mode: str) -> Tuple[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any], List[str]]:
    df = pd.read_csv(io.BytesIO(get_uploaded_bytes(uploaded_file)))
    src_idx, tgt_idx = detect_columns(list(df.columns))
    if src_idx is None:
        src_idx = 0
    if tgt_idx is None:
        df["AI Translation"] = ""
        tgt_idx = len(df.columns) - 1
    src_col = df.columns[src_idx]
    tgt_col = df.columns[tgt_idx]
    segments: List[Dict[str, Any]] = []
    targets: Dict[str, Any] = {}
    for idx, row in df.iterrows():
        source = normalize_text(row.get(src_col, ""))
        target = normalize_text(row.get(tgt_col, ""))
        if not source:
            continue
        if mode == "qa" and not target:
            continue
        loc = f"Row {idx + 2}"
        segments.append(
            {
                "id": len(segments) + 1,
                "file_type": "csv",
                "location": loc,
                "sheet": "CSV",
                "source": source,
                "translation": target,
                "text": target if mode == "qa" else source,
                "row_index": idx,
                "target_col": tgt_col,
                "mode": "bilingual" if target else "source_only",
            }
        )
        targets[loc] = (idx, tgt_col)
    return df, segments, targets, [f"CSV column mode [{src_col}] -> [{tgt_col}]"]


def extract_text(uploaded_file, mode: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any], List[str]]:
    text, enc = text_from_bytes(get_uploaded_bytes(uploaded_file))
    segments: List[Dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines()):
        clean = normalize_text(line)
        if not clean:
            continue
        if clean.lower() in {"source", "target", "translation"}:
            continue
        segments.append(
            {
                "id": len(segments) + 1,
                "file_type": "text",
                "location": f"Line {idx + 1}",
                "sheet": "Text",
                "source": clean if mode == "pro" else "",
                "translation": clean if mode == "qa" else "",
                "text": clean,
                "line_index": idx,
                "mode": "source_only" if mode == "pro" else "monolingual",
            }
        )
    return text, segments, {}, [f"Text mode decoded as {enc}"]


def extract_file(uploaded_file, mode: str) -> Tuple[Any, List[Dict[str, Any]], Dict[str, Any], List[str]]:
    name = uploaded_file.name.lower()
    if name.endswith(".docx"):
        return extract_docx(uploaded_file, mode)
    if name.endswith(".xlsx"):
        return extract_xlsx(uploaded_file, mode)
    if name.endswith(".csv"):
        return extract_csv(uploaded_file, mode)
    return extract_text(uploaded_file, mode)


def set_docx_cell_text(cell, text: str) -> None:
    for p in cell.paragraphs:
        for r in p.runs:
            r.text = ""
    if cell.paragraphs:
        cell.paragraphs[0].add_run(text)
    else:
        cell.add_paragraph(text)


def write_translated_output(uploaded_file, document_obj: Any, targets: Dict[str, Any], segments: List[Dict[str, Any]], translations: Dict[str, str]) -> Tuple[bytes, str, str]:
    name = uploaded_file.name
    low = name.lower()

    if low.endswith(".docx"):
        doc: Document = document_obj
        for seg in segments:
            loc = seg["location"]
            text = translations.get(loc, "")
            target = targets.get(loc)
            if target is None:
                continue
            if hasattr(target, "paragraphs"):
                set_docx_cell_text(target, text)
            else:
                target.add_run("\n" + text)
        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "errorsweep_translated_" + safe_file_name(name)

    if low.endswith(".xlsx"):
        wb = document_obj
        for seg in segments:
            cell = targets.get(seg["location"])
            if cell is not None:
                cell.value = translations.get(seg["location"], "")
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "errorsweep_translated_" + safe_file_name(name)

    if low.endswith(".csv"):
        df: pd.DataFrame = document_obj
        for seg in segments:
            target = targets.get(seg["location"])
            if target:
                row_idx, col = target
                df.at[row_idx, col] = translations.get(seg["location"], "")
        return df.to_csv(index=False).encode("utf-8-sig"), "text/csv", "errorsweep_translated_" + safe_file_name(name)

    table = pd.DataFrame(
        [
            {"Location": s["location"], "Source": s.get("source") or s.get("text", ""), "Translation": translations.get(s["location"], "")}
            for s in segments
        ]
    )
    return table.to_csv(index=False).encode("utf-8-sig"), "text/csv", "errorsweep_translations.csv"


# ==========================================================
# Rule pack parsing / memory in session
# ==========================================================

def parse_rules_zip(uploaded_zip) -> Dict[str, Any]:
    rules = {"glossary": [], "dnt": [], "chunks": [], "files": []}
    if not uploaded_zip:
        return rules
    try:
        zf = zipfile.ZipFile(io.BytesIO(get_uploaded_bytes(uploaded_zip)))
    except Exception:
        return rules
    for info in zf.infolist()[:80]:
        if info.is_dir():
            continue
        data = zf.read(info)
        name = info.filename
        text = ""
        if name.lower().endswith((".txt", ".md", ".csv", ".json", ".xml", ".xliff", ".xlf")):
            text, _ = text_from_bytes(data)
        elif name.lower().endswith(".docx"):
            try:
                doc = Document(io.BytesIO(data))
                text = "\n".join([p.text for p in doc.paragraphs])
            except Exception:
                text = ""
        elif name.lower().endswith(".xlsx"):
            try:
                wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
                rows = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        vals = [str(v) for v in row if v is not None]
                        if vals:
                            rows.append(" | ".join(vals))
                text = "\n".join(rows)
            except Exception:
                text = ""
        if not text:
            continue
        rules["files"].append(name)
        rules["chunks"].append({"source": name, "text": text[:4000]})

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if "->" in stripped or "=>" in stripped:
                sep = "->" if "->" in stripped else "=>"
                a, b = [x.strip() for x in stripped.split(sep, 1)]
                if a and b:
                    rules["glossary"].append({"source_term": a, "target_term": b, "source": name})
            if stripped.lower().startswith(("dnt:", "do not translate:", "brand:")):
                term = stripped.split(":", 1)[-1].strip()
                if term:
                    rules["dnt"].append({"term": term, "source": name})
    return rules


def tm_store() -> Dict[str, str]:
    if "tm_store" not in st.session_state:
        st.session_state["tm_store"] = {}
    return st.session_state["tm_store"]


def tm_key(source: str, target_language: str, project: str = "default") -> str:
    return f"{project}::{target_language.lower().strip()}::{source.strip().lower()}"


def save_tm(source: str, target: str, target_language: str, project: str = "default") -> None:
    if source and target:
        tm_store()[tm_key(source, target_language, project)] = target


def lookup_tm(source: str, target_language: str, project: str = "default") -> str:
    return tm_store().get(tm_key(source, target_language, project), "")


# ==========================================================
# Report/Excel helpers
# ==========================================================

def make_review_report(segments: List[Dict[str, Any]], translations: Dict[str, str], issues: List[Dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    total = len(segments)
    bad = len(issues)
    ws.append(["Metric", "Value"])
    ws.append(["Segments", total])
    ws.append(["Issues", bad])
    ws.append(["Pass", max(0, total - bad)])
    ws.append(["Generated", datetime.now(timezone.utc).isoformat()])

    ws2 = wb.create_sheet("All Segment Review")
    ws2.append(["Location", "Source", "Translation", "Status"])
    issue_locs = {x.get("Location") for x in issues}
    for seg in segments:
        loc = seg["location"]
        ws2.append([loc, seg.get("source") or seg.get("text", ""), translations.get(loc, seg.get("translation", "")), "Needs Review" if loc in issue_locs else "Pass"])

    ws3 = wb.create_sheet("Issue Details")
    headers = ["Location", "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation", "Confidence"]
    ws3.append(headers)
    for row in issues:
        ws3.append([row.get(h, "") for h in headers])

    for wsx in wb.worksheets:
        for cell in wsx[1]:
            cell.fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
            cell.font = Font(bold=True)
        for col in wsx.columns:
            letter = col[0].column_letter
            wsx.column_dimensions[letter].width = min(60, max(12, max(len(str(c.value or "")) for c in col[:100]) + 2))
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def issue_rows_for_segments(segments: List[Dict[str, Any]], rules: Dict[str, Any], target_language: str = "Auto") -> List[Dict[str, Any]]:
    rows = []
    for seg in segments:
        rows.extend(deterministic_checks_v2(seg, rules, target_language=target_language))
    return rows


# ==========================================================
# Pages
# ==========================================================

def page_dashboard() -> None:
    runtime_banner()
    user = current_user()
    cols = st.columns(4)
    cols[0].metric("Workspace", "MVP")
    cols[1].metric("User", user.get("email", "demo"))
    cols[2].metric("TM entries", len(tm_store()))
    cols[3].metric("Runtime", APP_VERSION)

    st.markdown("### Quick Start")
    st.markdown(
        """
<div class="es-note">
<b>Recommended workflow:</b> Run Pro translation with engines connected → open Human Review → approve good segments → save approved segments to TM → generate scorecards later.
</div>
""",
        unsafe_allow_html=True,
    )


def page_engine_status() -> None:
    st.markdown("## Engine Status")
    source = st.selectbox("Source language", ["English", "eng_Latn"], index=0)
    target = st.selectbox("Target language", ["French", "Spanish", "German", "Arabic", "Telugu", "Hindi", "Tamil", "Malayalam", "Kannada"], index=0)

    route = select_translation_route(
        target_language=target,
        source_language=source,
        libretranslate_endpoint=secret("LIBRETRANSLATE_ENDPOINT") or secret("LOCAL_TRANSLATION_ENDPOINT"),
        indictrans2_endpoint=secret("INDICTRANS2_ENDPOINT"),
    )
    if route:
        st.success(f"Route: {route.provider} → {route.endpoint}")
        pf = preflight_translation_engine(
            target_language=target,
            source_language=source,
            libretranslate_endpoint=secret("LIBRETRANSLATE_ENDPOINT") or secret("LOCAL_TRANSLATION_ENDPOINT"),
            indictrans2_endpoint=secret("INDICTRANS2_ENDPOINT"),
        )
        if pf.ok:
            st.success(pf.message)
        else:
            st.error(pf.message)
        with st.expander("Details"):
            st.json(pf.details if pf.details is not None else {})
    else:
        st.error("No route configured for this target language.")


def run_qa_page() -> None:
    st.markdown("## ErrorSweep QA")
    st.caption("Check existing translations and generate an Excel QA report.")

    up = st.file_uploader("Upload translated file", type=SUPPORTED_UPLOADS, key="qa_file")
    rules_zip = st.file_uploader("Upload Rules ZIP", type=["zip"], key="qa_rules")
    target_language = st.text_input("Target language / locale", value="Auto-detect", key="qa_lang")
    run = st.button("Run QA", type="primary", disabled=up is None, use_container_width=True)

    if not run or up is None:
        return

    rules = parse_rules_zip(rules_zip)
    obj, segments, targets, logs = extract_file(up, "qa")
    with st.expander("Extraction log", expanded=True):
        for log in logs:
            st.write(log)
        st.info(f"Found {len(segments)} segment(s).")

    issues = issue_rows_for_segments(segments, rules, target_language)
    report = make_review_report(segments, {s["location"]: s.get("translation", "") for s in segments}, issues)

    st.metric("Segments", len(segments))
    st.metric("Issues", len(issues))
    st.download_button("Download QA Score Report", report, "errorsweep_qa_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    create_review_session("QA", up.name, segments, {s["location"]: s.get("translation", "") for s in segments}, issues, target_language)
    if st.button("Open Human Review", use_container_width=True):
        st.session_state["page"] = "Human Review"
        st.rerun()


def create_review_session(kind: str, file_name: str, segments: List[Dict[str, Any]], translations: Dict[str, str], issues: List[Dict[str, Any]], target_language: str) -> str:
    sid = str(uuid.uuid4())
    session = {
        "id": sid,
        "kind": kind,
        "file_name": file_name,
        "target_language": target_language,
        "segments": segments,
        "translations": translations,
        "issues": issues,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": {},
        "comments": {},
    }
    st.session_state.setdefault("review_sessions", {})[sid] = session
    st.session_state["active_review_session_id"] = sid
    return sid


def run_pro_page() -> None:
    st.markdown("## ErrorSweep Pro")
    st.caption("Translate source content, run offline QA, block incomplete outputs, and open Human Review.")

    up = st.file_uploader("Upload source file", type=SUPPORTED_UPLOADS, key="pro_file")
    rules_zip = st.file_uploader("Upload Rules ZIP", type=["zip"], key="pro_rules")
    col1, col2, col3 = st.columns(3)
    with col1:
        target_language = st.text_input("Target language", value="French")
    with col2:
        use_tm = st.checkbox("Use Translation Memory", value=False, help="Turn OFF for first test to avoid old-language memory.")
    with col3:
        run_review = st.checkbox("Run offline QA after translation", value=True)

    route = select_translation_route(
        target_language=target_language,
        source_language=secret("LOCAL_TRANSLATION_SOURCE_LANGUAGE", "English"),
        libretranslate_endpoint=secret("LIBRETRANSLATE_ENDPOINT") or secret("LOCAL_TRANSLATION_ENDPOINT"),
        indictrans2_endpoint=secret("INDICTRANS2_ENDPOINT"),
    )
    if route:
        st.info(f"Engine route: {route.provider} · {route.endpoint}")
    else:
        st.warning("No local translation route is configured for this target language.")

    run = st.button("Run Translate + Review", type="primary", disabled=up is None, use_container_width=True)

    if not run or up is None:
        return

    rules = parse_rules_zip(rules_zip)
    obj, segments, targets, logs = extract_file(up, "pro")
    with st.expander("Extraction log", expanded=True):
        for log in logs:
            st.write(log)
        st.info(f"Found {len(segments)} source segment(s).")

    if not route:
        st.error(f"No translation endpoint configured for {target_language}.")
        st.stop()

    pf = preflight_translation_engine(
        target_language=target_language,
        source_language=secret("LOCAL_TRANSLATION_SOURCE_LANGUAGE", "English"),
        libretranslate_endpoint=secret("LIBRETRANSLATE_ENDPOINT") or secret("LOCAL_TRANSLATION_ENDPOINT"),
        indictrans2_endpoint=secret("INDICTRANS2_ENDPOINT"),
    )
    if not pf.ok:
        st.error(pf.message)
        st.stop()
    st.success(pf.message)

    translations: Dict[str, str] = {}
    to_translate: List[Dict[str, Any]] = []
    if use_tm:
        for seg in segments:
            hit = lookup_tm(seg.get("source") or seg.get("text", ""), target_language)
            if hit:
                translations[seg["location"]] = hit
            else:
                to_translate.append(seg)
    else:
        to_translate = list(segments)

    progress = st.progress(0)
    if to_translate:
        for i in range(0, len(to_translate), 20):
            batch = to_translate[i : i + 20]
            result = local_translate_batch_adapter(
                segments=batch,
                target_language=target_language,
                source_language=secret("LOCAL_TRANSLATION_SOURCE_LANGUAGE", "English"),
                domain="General",
                libretranslate_endpoint=secret("LIBRETRANSLATE_ENDPOINT") or secret("LOCAL_TRANSLATION_ENDPOINT"),
                indictrans2_endpoint=secret("INDICTRANS2_ENDPOINT"),
                api_key=secret("LOCAL_TRANSLATION_API_KEY", ""),
                batch_size=20,
            )
            for item in result:
                translations[item.get("location", "")] = item.get("translation", "")
            progress.progress(min(1.0, (i + len(batch)) / max(len(to_translate), 1)))

    missing = find_missing_or_bad_translations(segments, translations, target_language)
    if missing:
        st.error(f"Translation coverage failed: {len(missing)} segment(s) are blank, placeholder-only, or clearly untranslated. Download is blocked.")
        with st.expander("Missing translation locations", expanded=True):
            st.dataframe(pd.DataFrame(missing[:200]), use_container_width=True, hide_index=True)
        st.stop()

    translated_segments = []
    for seg in segments:
        translated_segments.append({**seg, "translation": translations.get(seg["location"], ""), "text": translations.get(seg["location"], "")})

    issues = issue_rows_for_segments(translated_segments, rules, target_language) if run_review else []
    output_bytes, mime, output_name = write_translated_output(up, obj, targets, segments, translations)
    report = make_review_report(translated_segments, translations, issues)

    st.success(f"Translated {len(segments)} segment(s).")
    st.dataframe(
        pd.DataFrame(
            [{"Location": s["location"], "Source": s.get("source") or s.get("text", ""), "Translation": translations.get(s["location"], "")} for s in segments[:100]]
        ),
        use_container_width=True,
        hide_index=True,
    )
    c1, c2 = st.columns(2)
    c1.download_button("Download Translated Output", output_bytes, output_name, mime=mime, use_container_width=True)
    c2.download_button("Download Review Report", report, "errorsweep_pro_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    create_review_session("Pro", up.name, translated_segments, translations, issues, target_language)
    if st.button("Open Human Review", use_container_width=True):
        st.session_state["page"] = "Human Review"
        st.rerun()


def page_human_review() -> None:
    st.markdown("## Human Review")
    sessions = st.session_state.get("review_sessions", {})
    if not sessions:
        st.info("No review session yet. Run QA or Pro, then click Open Human Review.")
        return

    session_ids = list(sessions.keys())
    active = st.session_state.get("active_review_session_id") or session_ids[-1]
    sid = st.selectbox("Review session", session_ids, index=session_ids.index(active) if active in session_ids else 0, format_func=lambda x: f"{sessions[x]['kind']} · {sessions[x]['file_name']} · {sessions[x]['created_at'][:19]}")
    session = sessions[sid]
    segments = session["segments"]
    issues = session.get("issues", [])
    issues_by_loc: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        issues_by_loc.setdefault(issue.get("Location", ""), []).append(issue)

    st.markdown(f"<div class='es-note'>Session: <b>{escape(session['file_name'])}</b> · Target: <b>{escape(session['target_language'])}</b></div>", unsafe_allow_html=True)

    left, mid, right = st.columns([1.1, 1.4, 1])
    locations = [s["location"] for s in segments]
    selected_loc = left.selectbox("Segment", locations, format_func=lambda x: f"{x} · {'Issues' if issues_by_loc.get(x) else 'Pass'}")
    seg = next(s for s in segments if s["location"] == selected_loc)

    source = seg.get("source") or seg.get("text", "")
    current_target = session["translations"].get(selected_loc, seg.get("translation", ""))

    with left:
        st.markdown("#### Source")
        st.text_area("Source text", value=source, height=220, disabled=True, label_visibility="collapsed")
        st.caption(selected_loc)

    with mid:
        st.markdown("#### Target")
        edited = st.text_area("Editable target", value=current_target, height=220, key=f"edit_{sid}_{selected_loc}")
        status = st.radio("Status", ["Draft", "Needs Review", "Approved", "Rejected"], horizontal=True, key=f"status_{sid}_{selected_loc}")
        comment = st.text_area("Reviewer comment", value=session["comments"].get(selected_loc, ""), height=80, key=f"comment_{sid}_{selected_loc}")

        b1, b2 = st.columns(2)
        if b1.button("Save segment", use_container_width=True):
            session["translations"][selected_loc] = edited
            session["status"][selected_loc] = status
            session["comments"][selected_loc] = comment
            st.success("Saved.")
        if b2.button("Approve & Save to TM", use_container_width=True):
            session["translations"][selected_loc] = edited
            session["status"][selected_loc] = "Approved"
            session["comments"][selected_loc] = comment
            save_tm(source, edited, session["target_language"])
            st.success("Approved and saved to TM.")

    with right:
        st.markdown("#### QA issues")
        loc_issues = issues_by_loc.get(selected_loc, [])
        if not loc_issues:
            st.success("No issues for this segment.")
        else:
            for issue in loc_issues:
                st.markdown(
                    f"""
<div class="es-error">
<b>{escape(str(issue.get('Error Type','Issue')))}</b> · {escape(str(issue.get('Severity','Review')))}<br>
Issue: {escape(str(issue.get('Wrong Part','')))}<br>
Suggestion: {escape(str(issue.get('Suggestion','')))}<br>
<span class="es-small">{escape(str(issue.get('Explanation','')))}</span>
</div>
""",
                    unsafe_allow_html=True,
                )
        st.markdown("#### TM match")
        hit = lookup_tm(source, session["target_language"])
        if hit:
            st.info(hit)
        else:
            st.caption("No exact TM match.")
        st.markdown("#### Glossary")
        st.caption("Glossary panel will connect to project rule packs in the next build.")

    export = make_review_report(segments, session["translations"], issues)
    st.download_button("Download Human Review Export", export, "human_review_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def page_scorecards() -> None:
    st.markdown("## Translator vs Reviewer Scorecard")
    st.caption("Upload translator file and reviewer/final file to compare quality.")

    trans_file = st.file_uploader("Translator file", type=SUPPORTED_UPLOADS, key="score_trans")
    rev_file = st.file_uploader("Reviewer/final file", type=SUPPORTED_UPLOADS, key="score_rev")
    target_language = st.text_input("Target language", value="Auto", key="score_lang")
    run = st.button("Generate Scorecard", type="primary", disabled=not (trans_file and rev_file), use_container_width=True)
    if not run:
        return

    _, trans_segments, _, _ = extract_file(trans_file, "qa")
    _, rev_segments, _, _ = extract_file(rev_file, "qa")
    by_source_rev = {normalize_text(s.get("source", "")).lower(): s.get("translation", "") for s in rev_segments if s.get("source")}

    rows = []
    for s in trans_segments:
        src = s.get("source", "")
        t1 = s.get("translation", "")
        t2 = by_source_rev.get(normalize_text(src).lower(), "")
        changed = bool(t2 and normalize_text(t1) != normalize_text(t2))
        severity = "Major" if changed else "Pass"
        rows.append(
            {
                "Source": src,
                "Translator Translation": t1,
                "Reviewer Translation": t2,
                "Changed": changed,
                "Error Category": "Reviewer Change" if changed else "Pass",
                "Severity": severity,
                "Penalty": 5 if changed else 0,
            }
        )
    df = pd.DataFrame(rows)
    score = max(0, 100 - int(df["Penalty"].sum() if not df.empty else 0))
    st.metric("Quality Score", score)
    st.metric("Changed segments", int(df["Changed"].sum() if not df.empty else 0))
    st.dataframe(df, use_container_width=True, hide_index=True)

    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame([{"Quality Score": score, "Changed Segments": int(df["Changed"].sum()) if not df.empty else 0}]).to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="Segment Comparison", index=False)
    st.download_button("Download Scorecard", bio.getvalue(), "translator_scorecard.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def page_memory_rules() -> None:
    st.markdown("## Memory & Rules")
    st.metric("Session TM entries", len(tm_store()))
    if tm_store():
        df = pd.DataFrame([{"Key": k, "Translation": v} for k, v in tm_store().items()])
        st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("Clear session TM"):
        st.session_state["tm_store"] = {}
        st.rerun()


def page_account() -> None:
    st.markdown("## Account")
    user = current_user()
    st.write(user)
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()


def page_admin() -> None:
    st.markdown("## Admin")
    st.caption("Production admin controls will move to role-based access in the next backend build.")
    page_engine_status()
    protect_private_file_warning()


# ==========================================================
# Main entry
# ==========================================================

def main() -> None:
    runtime_banner()
    if not auth_gate():
        return

    pages = ["Dashboard", "ErrorSweep QA", "ErrorSweep Pro", "Human Review", "Scorecards", "Memory & Rules", "Account", "Admin"]
    current = st.session_state.get("page", "Dashboard")
    if current not in pages:
        current = "Dashboard"

    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio("Go to", pages, index=pages.index(current), label_visibility="collapsed")
        st.session_state["page"] = page
        st.divider()
        st.caption(f"Runtime {APP_VERSION}")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if page == "Dashboard":
        page_dashboard()
    elif page == "ErrorSweep QA":
        run_qa_page()
    elif page == "ErrorSweep Pro":
        run_pro_page()
    elif page == "Human Review":
        page_human_review()
    elif page == "Scorecards":
        page_scorecards()
    elif page == "Memory & Rules":
        page_memory_rules()
    elif page == "Account":
        page_account()
    elif page == "Admin":
        page_admin()


if __name__ == "__main__":
    main()

