
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
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
except Exception:
    OpenAI = None


# ==========================================================
# ErrorSweep Platform v20
# Main API-first localization platform shell
# ==========================================================

st.set_page_config(page_title="ErrorSweep", page_icon="🌐", layout="wide")


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
    radial-gradient(circle at 10% 15%, rgba(0,231,133,.14), transparent 28%),
    radial-gradient(circle at 85% 8%, rgba(53,189,247,.12), transparent 30%),
    radial-gradient(circle at 50% 100%, rgba(139,92,246,.12), transparent 45%),
    var(--bg);
  color: var(--text);
}
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stDeployButton"], .stAppDeployButton {
  visibility: hidden !important;
  display: none !important;
}
section[data-testid="stSidebar"] {
  background: rgba(8,11,22,.98);
  border-right: 1px solid rgba(125,145,255,.18);
}
.es-hero {
  padding: 32px;
  border: 1px solid rgba(53,189,247,.22);
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(0,231,133,.12), rgba(53,189,247,.08) 40%, rgba(139,92,246,.18)),
    rgba(16,20,36,.82);
  box-shadow: 0 30px 90px rgba(0,0,0,.30);
  margin: 10px 0 24px 0;
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
  font-weight: 800;
  margin: 18px 0 8px 0;
  background: linear-gradient(90deg, #fff, #bfffe1 35%, #9bdfff 70%, #d5c8ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.es-sub {
  color: #c4cbdf;
  font-size: 15px;
  max-width: 980px;
}
.es-grid {
  display:grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  gap: 14px;
  margin: 14px 0 22px;
}
.es-grid-3 {
  display:grid;
  grid-template-columns: repeat(3, minmax(0,1fr));
  gap: 14px;
  margin: 14px 0 22px;
}
.es-card {
  background: rgba(16,20,36,.80);
  border: 1px solid rgba(125,145,255,.20);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 15px 35px rgba(0,0,0,.18);
}
.es-card h3,.es-card h4 { margin: 0 0 8px 0; color: #f8fbff; }
.es-card p { color: var(--muted); margin:0; font-size:13px; }
.es-metric-label {
  font-family:'Space Mono', monospace;
  font-size: 11px;
  color: #a7b4d8;
  letter-spacing: .8px;
  text-transform: uppercase;
}
.es-metric-value {
  font-size: 30px;
  font-weight: 800;
  color:#fff;
  margin: 6px 0;
}
.es-badge {
  display:inline-block;
  padding: 4px 10px;
  border-radius:999px;
  font-size: 11px;
  font-weight:700;
  border:1px solid rgba(125,145,255,.25);
  color:#dfe7ff;
  background: rgba(125,145,255,.10);
}
.es-badge-green { color:#9fffd1; border-color:rgba(0,231,133,.35); background:rgba(0,231,133,.12); }
.es-badge-yellow { color:#ffe8a3; border-color:rgba(251,191,36,.35); background:rgba(251,191,36,.12); }
.es-badge-red { color:#ffc2cd; border-color:rgba(255,77,109,.35); background:rgba(255,77,109,.12); }
.es-two-pane {
  display:grid;
  grid-template-columns: 1.1fr 1.1fr .9fr;
  gap:14px;
}
.es-small {
  font-size:12px;
  color: var(--muted);
}
.stButton > button, .stDownloadButton > button {
  border-radius: 13px !important;
  border: 1px solid rgba(0,231,133,.25) !important;
  background: linear-gradient(90deg, #00c876, #159fe8) !important;
  color: white !important;
  font-weight: 800 !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 35px rgba(0,231,133,.15);
}
div[data-testid="stExpander"] {
  border:1px solid rgba(125,145,255,.20)!important;
  background:rgba(16,20,36,.62)!important;
  border-radius:14px!important;
}
@media (max-width: 1000px) {
  .es-grid, .es-grid-3, .es-two-pane { grid-template-columns: 1fr; }
  .es-title { font-size: 28px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ==========================================================
# Constants and session state
# ==========================================================

APP_VERSION = "v21 Full Navigation"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SUPPORTED_MAIN_API_LANGUAGES = [
    "French", "Spanish", "German", "Italian", "Portuguese",
    "Arabic", "Chinese", "Japanese", "Korean", "Russian",
    "Telugu", "Hindi", "Tamil", "Malayalam", "Kannada",
    "Bengali", "Marathi", "Gujarati", "Urdu", "English",
]

ROLES = [
    "Owner",
    "Admin",
    "Project Manager",
    "Translator",
    "Reviewer",
    "Client Viewer",
    "Billing Admin",
    "Super Admin",
]

QA_CATEGORIES = [
    "Blank target",
    "Source copied",
    "Placeholder",
    "Number mismatch",
    "Formatting",
    "DNT",
    "Glossary",
    "Language/script",
    "AI QA",
]

PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[sd]|\$\w+|<[^>]+>)")
NUMBER_RE = re.compile(r"\d+(?:[.,:]\d+)*")
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "\u200D"
    "]+",
    flags=re.UNICODE,
)


def init_state() -> None:
    defaults = {
        "authenticated": False,
        "username": "",
        "role": "Owner",
        "active_page": "Dashboard",
        "projects": [],
        "jobs": [],
        "tm_entries": [],
        "glossary": [],
        "dnt_terms": [],
        "review_segments": [],
        "team": [],
        "current_project_id": "",
        "last_output": None,
        "last_report": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state["team"]:
        st.session_state["team"] = [
            {"Name": "Platform Owner", "Email": "owner@errorsweep.local", "Role": "Owner", "Status": "Active"},
            {"Name": "Reviewer Demo", "Email": "reviewer@errorsweep.local", "Role": "Reviewer", "Status": "Invited"},
        ]


init_state()


# ==========================================================
# Secrets/API helpers
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
    raw = secret("ERRORSWEEP_ALLOW_DEMO_LOGIN", "true").lower().strip()
    return raw in {"1", "true", "yes", "on"}


def get_openai_client():
    key = secret("OPENAI_API_KEY")
    if not key or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=key, timeout=80, max_retries=1)
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


def truncate(text: Any, n: int = 240) -> str:
    t = clean_text(text)
    return t if len(t) <= n else t[: n - 1] + "…"


def extract_placeholders(text: str) -> List[str]:
    return PLACEHOLDER_RE.findall(text or "")


def extract_numbers(text: str) -> List[str]:
    return NUMBER_RE.findall(text or "")


def preserve_protected(source: str, translation: str) -> str:
    """Light post-processing to restore protected tokens/icons if the API dropped them."""
    output = translation or ""

    for token in extract_placeholders(source):
        if token and token not in output:
            output = (output.rstrip() + " " + token).strip()

    src_emojis = EMOJI_RE.findall(source or "")
    for emoji in src_emojis:
        if emoji and emoji not in output:
            output = f"{emoji} {output}".strip()

    # Preserve leading bullet-like marker.
    leading = re.match(r"^(\s*[•∙·\-\*]\s*)", source or "")
    if leading:
        marker = leading.group(1)
        if marker.strip() and not output.lstrip().startswith(marker.strip()):
            output = marker + output.lstrip()

    # Preserve bracket wrapper for UI labels.
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
    if tokenless == "" and PLACEHOLDER_RE.search(src):
        return True

    if src.lower() == tgt.lower() and target_language.lower() not in {"english", "en"}:
        # Allow bracket-only labels to remain if they are product/screen markers? Better mark review.
        return True

    return False


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


def safe_dataframe(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if columns:
        for c in columns:
            if c not in df.columns:
                df[c] = ""
        return df[columns]
    return df


# ==========================================================
# File extraction and output
# ==========================================================

@dataclass
class ExtractedFile:
    kind: str
    name: str
    segments: List[Dict[str, Any]]
    raw: Any = None
    logs: List[str] = None


def detect_columns(headers: List[str]) -> Tuple[Optional[str], Optional[str]]:
    source_terms = ["source text", "source", "src", "english", "source segment"]
    target_terms = ["target", "translation", "translated text", "original translation", "target text"]

    normalized = {clean_text(h).lower(): h for h in headers}
    source_col = None
    target_col = None

    for key, original in normalized.items():
        if source_col is None and any(term == key or term in key for term in source_terms):
            source_col = original
        if target_col is None and any(term == key or term in key for term in target_terms):
            target_col = original

    return source_col, target_col


def extract_from_xlsx(uploaded_file, mode: str) -> ExtractedFile:
    wb = load_workbook(uploaded_file)
    segments: List[Dict[str, Any]] = []
    logs: List[str] = []

    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        header_row_index = 0
        source_idx = target_idx = None
        headers = []

        for i, row in enumerate(rows[:30]):
            h = [clean_text(v) for v in row]
            if not any(h):
                continue
            s_col, t_col = detect_columns(h)
            if s_col:
                headers = h
                header_row_index = i
                source_idx = h.index(s_col)
                target_idx = h.index(t_col) if t_col and t_col in h else None
                break

        if source_idx is None:
            continue

        if mode == "pro" and target_idx is None:
            target_idx = len(headers)
            ws.cell(row=header_row_index + 1, column=target_idx + 1).value = "AI Translation"
            logs.append(f"{ws.title}: created AI Translation column.")
        else:
            logs.append(f"{ws.title}: detected source/target columns.")

        for r_i, row in enumerate(rows[header_row_index + 1 :], start=header_row_index + 2):
            row_values = list(row)
            source = clean_text(row_values[source_idx] if source_idx < len(row_values) else "")
            target = clean_text(row_values[target_idx] if target_idx is not None and target_idx < len(row_values) else "")
            if not source:
                continue
            if mode == "qa" and not target:
                continue
            location = f"{ws.title}!R{r_i}"
            segments.append({
                "id": len(segments) + 1,
                "location": location,
                "sheet": ws.title,
                "row": r_i,
                "source": source,
                "target": target,
                "translation": target,
                "target_col": target_idx,
                "file_type": "xlsx",
            })

    return ExtractedFile("xlsx", uploaded_file.name, segments, raw=wb, logs=logs)


def extract_from_csv(uploaded_file, mode: str) -> ExtractedFile:
    df = pd.read_csv(uploaded_file)
    source_col, target_col = detect_columns(list(df.columns))

    if source_col is None:
        # Fallback: first column is source.
        source_col = df.columns[0]
    if mode == "pro" and target_col is None:
        target_col = "AI Translation"
        df[target_col] = ""

    segments = []
    for idx, row in df.iterrows():
        source = clean_text(row.get(source_col, ""))
        target = clean_text(row.get(target_col, "")) if target_col else ""
        if not source:
            continue
        if mode == "qa" and not target:
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
        })

    return ExtractedFile("csv", uploaded_file.name, segments, raw=df, logs=[f"CSV: {source_col} → {target_col or 'target not found'}"])


def extract_from_docx(uploaded_file, mode: str) -> ExtractedFile:
    doc = Document(uploaded_file)
    segments = []
    locations = {}

    # Prefer tables with source/target columns.
    for t_i, table in enumerate(doc.tables, start=1):
        if not table.rows:
            continue
        headers = [clean_text(c.text) for c in table.rows[0].cells]
        source_col, target_col = detect_columns(headers)
        if not source_col:
            continue
        source_idx = headers.index(source_col)
        target_idx = headers.index(target_col) if target_col and target_col in headers else None
        if mode == "pro" and target_idx is None:
            target_idx = len(headers) - 1 if len(headers) > 1 else None

        for r_i, row in enumerate(table.rows[1:], start=2):
            if source_idx >= len(row.cells):
                continue
            source = clean_text(row.cells[source_idx].text)
            target = clean_text(row.cells[target_idx].text) if target_idx is not None and target_idx < len(row.cells) else ""
            if not source:
                continue
            if mode == "qa" and not target:
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
            })
            if target_idx is not None and target_idx < len(row.cells):
                locations[loc] = row.cells[target_idx]

    if segments:
        return ExtractedFile("docx", uploaded_file.name, segments, raw=(doc, locations), logs=["DOCX: extracted table segments."])

    # Paragraph fallback.
    for i, p in enumerate(doc.paragraphs, start=1):
        source = clean_text(p.text)
        if len(source) < 2:
            continue
        loc = f"Paragraph {i}"
        segments.append({
            "id": len(segments) + 1,
            "location": loc,
            "sheet": "Document",
            "row": i,
            "source": source,
            "target": "",
            "translation": "",
            "file_type": "docx",
        })
        locations[loc] = p

    return ExtractedFile("docx", uploaded_file.name, segments, raw=(doc, locations), logs=["DOCX: paragraph fallback mode."])


def extract_from_text(uploaded_file, mode: str) -> ExtractedFile:
    raw = uploaded_file.getvalue()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("cp1252", errors="replace")

    lines = text.splitlines()
    segments = []
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
            "source": value if mode == "pro" else "",
            "target": value if mode == "qa" else "",
            "translation": value if mode == "qa" else "",
            "file_type": "text",
        })

    return ExtractedFile("text", uploaded_file.name, segments, raw=text, logs=["Text: line extraction mode."])


def extract_file(uploaded_file, mode: str = "pro") -> ExtractedFile:
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx"):
        return extract_from_xlsx(uploaded_file, mode)
    if name.endswith(".csv"):
        return extract_from_csv(uploaded_file, mode)
    if name.endswith(".docx"):
        return extract_from_docx(uploaded_file, mode)
    return extract_from_text(uploaded_file, mode)


def build_output_file(extracted: ExtractedFile, translations_by_loc: Dict[str, str]) -> Tuple[bytes, str, str]:
    name = extracted.name
    if extracted.kind == "xlsx":
        wb = extracted.raw
        for seg in extracted.segments:
            loc = seg["location"]
            ws = wb[seg["sheet"]]
            target_col = seg.get("target_col")
            if target_col is None:
                continue
            ws.cell(row=int(seg["row"]), column=int(target_col) + 1).value = translations_by_loc.get(loc, "")
        # Add review sheet.
        if "ErrorSweep Job Summary" in wb.sheetnames:
            del wb["ErrorSweep Job Summary"]
        ws = wb.create_sheet("ErrorSweep Job Summary")
        ws.append(["Location", "Source", "Translation"])
        for seg in extracted.segments:
            ws.append([seg["location"], seg["source"], translations_by_loc.get(seg["location"], "")])
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="D9EAF7")
            cell.font = Font(bold=True)
        for col in ws.columns:
            for cell in col:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"errorsweep_translated_{name}"

    if extracted.kind == "csv":
        df = extracted.raw
        target_col = "AI Translation"
        if target_col not in df.columns:
            df[target_col] = ""
        for seg in extracted.segments:
            df.at[int(seg["row"]), target_col] = translations_by_loc.get(seg["location"], "")
        return df.to_csv(index=False).encode("utf-8-sig"), "text/csv", re.sub(r"\.[^.]+$", ".csv", f"errorsweep_translated_{name}")

    if extracted.kind == "docx":
        doc, locations = extracted.raw
        for seg in extracted.segments:
            loc = seg["location"]
            target = translations_by_loc.get(loc, "")
            obj = locations.get(loc)
            if obj is None:
                continue
            if hasattr(obj, "paragraphs"):
                # table cell
                for p in obj.paragraphs:
                    for run in p.runs:
                        run.text = ""
                if obj.paragraphs:
                    obj.paragraphs[0].add_run(target)
                else:
                    obj.add_paragraph(target)
            else:
                # paragraph
                obj.add_run("\n" + target)
        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"errorsweep_translated_{name}"

    # text
    lines = extracted.raw.splitlines()
    by_row = {seg["row"]: translations_by_loc.get(seg["location"], "") for seg in extracted.segments}
    out_lines = []
    for i, line in enumerate(lines, start=1):
        out_lines.append(line)
        if i in by_row and by_row[i]:
            out_lines.append(by_row[i])
    return "\n".join(out_lines).encode("utf-8-sig"), "text/plain", f"errorsweep_translated_{name}"


# ==========================================================
# Rules, QA, API translation
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

        # Very light CSV glossary parsing.
        if lower.endswith(".csv"):
            try:
                df = pd.read_csv(io.StringIO(text))
                cols = {c.lower(): c for c in df.columns}
                src_col = next((cols[c] for c in cols if "source" in c or c == "term"), None)
                tgt_col = next((cols[c] for c in cols if "target" in c or "translation" in c), None)
                dnt_col = next((cols[c] for c in cols if "dnt" in c or "do not" in c), None)
                if src_col and tgt_col:
                    for _, row in df.iterrows():
                        glossary.append({"Source Term": clean_text(row.get(src_col)), "Target Term": clean_text(row.get(tgt_col)), "Rule Source": name})
                if dnt_col:
                    for value in df[dnt_col].dropna().tolist():
                        dnt_terms.append({"Term": clean_text(value), "Rule Source": name})
            except Exception:
                pass

    return glossary, dnt_terms, combined[:6000]


def deterministic_qa(segments: List[Dict[str, Any]], glossary: List[Dict[str, str]], dnt_terms: List[Dict[str, str]], target_language: str = "") -> List[Dict[str, Any]]:
    rows = []
    for seg in segments:
        source = seg.get("source", "")
        target = seg.get("translation") or seg.get("target", "")
        loc = seg.get("location", "")

        if not target:
            rows.append({
                "Location": loc, "Source": source, "Translation": target,
                "Issue Type": "Blank target", "Severity": "Major",
                "Suggestion": "Translate this segment or send to Human Review.",
                "Reason": "Target is blank."
            })
            continue

        if clean_text(source).lower() == clean_text(target).lower() and target_language.lower() not in {"english", "en"}:
            rows.append({
                "Location": loc, "Source": source, "Translation": target,
                "Issue Type": "Source copied", "Severity": "Major",
                "Suggestion": "Review and translate this segment.",
                "Reason": "Source and target are identical."
            })

        missing_ph = [p for p in extract_placeholders(source) if p not in extract_placeholders(target)]
        if missing_ph:
            rows.append({
                "Location": loc, "Source": source, "Translation": target,
                "Issue Type": "Placeholder", "Severity": "Critical",
                "Suggestion": "Preserve: " + ", ".join(missing_ph),
                "Reason": "Placeholder(s) from source are missing."
            })

        missing_num = [n for n in extract_numbers(source) if n not in extract_numbers(target)]
        if missing_num:
            rows.append({
                "Location": loc, "Source": source, "Translation": target,
                "Issue Type": "Number mismatch", "Severity": "Major",
                "Suggestion": "Check number(s): " + ", ".join(missing_num),
                "Reason": "Number(s) from source are missing or changed."
            })

        for item in dnt_terms:
            term = item.get("Term", "")
            if term and term.lower() in source.lower() and term not in target:
                rows.append({
                    "Location": loc, "Source": source, "Translation": target,
                    "Issue Type": "DNT", "Severity": "Major",
                    "Suggestion": f"Keep '{term}' unchanged.",
                    "Reason": f"DNT term missing. Rule: {item.get('Rule Source','')}"
                })

        for item in glossary:
            src_term = item.get("Source Term", "")
            tgt_term = item.get("Target Term", "")
            if src_term and tgt_term and src_term.lower() in source.lower() and tgt_term not in target:
                rows.append({
                    "Location": loc, "Source": source, "Translation": target,
                    "Issue Type": "Glossary", "Severity": "Major",
                    "Suggestion": tgt_term,
                    "Reason": f"Glossary target term missing. Rule: {item.get('Rule Source','')}"
                })

    return rows


def ai_json_call(system: str, prompt: str, max_tokens: int = 6000) -> Any:
    client = get_openai_client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    response = client.responses.create(
        model=model_name(),
        instructions=system,
        input=prompt,
        max_output_tokens=max_tokens,
    )
    text = getattr(response, "output_text", "") or ""
    text = re.sub(r"^```json\s*", "", text.strip(), flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def translate_with_main_api(segments: List[Dict[str, Any]], target_language: str, domain: str, rule_context: str = "") -> Dict[str, str]:
    output: Dict[str, str] = {}
    batch_size = int(secret("ERRORSWEEP_API_BATCH_SIZE", "20") or 20)

    for start in range(0, len(segments), batch_size):
        batch = segments[start:start + batch_size]
        payload = [
            {
                "location": seg["location"],
                "source": seg["source"],
            }
            for seg in batch
        ]
        prompt = f"""
Translate these localization segments into {target_language}.
Domain: {domain}

Rules:
- Preserve placeholders exactly, e.g. {{{{email}}}}, {{{{user_name}}}}.
- Preserve numbers and units.
- Preserve emoji/icons and leading bullet characters.
- Preserve bracket structure for UI labels, but localize the text inside brackets.
- Do not add commentary.
- Return only JSON array with location and translation.

Company rules context:
{rule_context or "(none)"}

Segments:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            data = ai_json_call(
                "You are a professional localization translation engine. Return only valid JSON.",
                prompt,
                max_tokens=7000,
            )
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
    batch_size = int(secret("ERRORSWEEP_API_BATCH_SIZE", "20") or 20)

    for start in range(0, len(segments), batch_size):
        batch = segments[start:start + batch_size]
        payload = [
            {
                "location": seg["location"],
                "source": seg.get("source", ""),
                "translation": seg.get("translation") or seg.get("target", ""),
            }
            for seg in batch
        ]
        prompt = f"""
Review the following localization segments for real errors.
Target language: {target_language}
Domain: {domain}

Only flag real issues:
- Accuracy / omission / addition
- Grammar / spelling
- Source copied
- Placeholder or number errors
- DNT/glossary/style guide violations
- Unexpected mixed script
- Formatting issues

Do not invent errors or rewrite acceptable translations.

Company rules:
{rule_context or "(none)"}

Segments:
{json.dumps(payload, ensure_ascii=False)}

Return only JSON:
[
  {{
    "location": "...",
    "issue_type": "Accuracy|Grammar|Spelling|Placeholder|Number|DNT|Glossary|Formatting|Mixed Script|Style",
    "severity": "Minor|Major|Critical|Review",
    "wrong_part": "...",
    "suggestion": "...",
    "reason": "..."
  }}
]
"""
        try:
            data = ai_json_call(
                "You are ErrorSweep, a conservative localization QA engine. Return only valid JSON.",
                prompt,
                max_tokens=6500,
            )
        except Exception as exc:
            rows.append({
                "Location": "API",
                "Source": "",
                "Translation": "",
                "Issue Type": "API warning",
                "Severity": "Review",
                "Suggestion": "Retry this job.",
                "Reason": str(exc)[:400],
            })
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
# Navigation / auth
# ==========================================================

def login_page() -> None:
    st.markdown("""
    <div class="es-hero">
      <span class="es-kicker">Account required</span>
      <div class="es-title">ErrorSweep</div>
      <div class="es-sub">Secure localization QA, translation review, scorecards, and memory workflows.</div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Sign in", "Create account", "Demo access"])

    with tab1:
        username = st.text_input("Email / username")
        password = st.text_input("Password", type="password")
        if st.button("Sign in", type="primary", use_container_width=True):
            configured_user = secret("ERRORSWEEP_USERNAME", "admin")
            configured_pass = secret("ERRORSWEEP_PASSWORD", "")
            if configured_pass and username == configured_user and password == configured_pass:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = "Owner"
                st.rerun()
            elif allow_demo_login() and not configured_pass:
                st.session_state.authenticated = True
                st.session_state.username = username or "demo@errorsweep.local"
                st.session_state.role = "Owner"
                st.rerun()
            else:
                st.error("Invalid credentials. Use Demo access while building or configure ERRORSWEEP_USERNAME / ERRORSWEEP_PASSWORD.")

    with tab2:
        st.info("Account creation will be connected to Supabase/Auth in the next backend sprint.")
        name = st.text_input("Full name")
        email = st.text_input("Email")
        if st.button("Create demo account", use_container_width=True):
            st.session_state.authenticated = True
            st.session_state.username = email or name or "new-user@errorsweep.local"
            st.session_state.role = "Owner"
            st.rerun()

    with tab3:
        st.write("Use this while building the platform.")
        if st.button("Enter demo workspace", type="primary", use_container_width=True, disabled=not allow_demo_login()):
            st.session_state.authenticated = True
            st.session_state.username = "demo@errorsweep.local"
            st.session_state.role = "Owner"
            st.rerun()
        if not allow_demo_login():
            st.warning("Demo login is disabled. Set ERRORSWEEP_ALLOW_DEMO_LOGIN=true to enable it.")


PAGES = [
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
    "Engine Status",
]


def sidebar_nav() -> str:
    """Render navigation in both sidebar and main page.

    Some deployments/users may have the sidebar collapsed or hidden. To avoid losing
    access to pages, this function always renders a visible top navigation bar in
    the main content area, while also keeping the sidebar navigation when available.
    """
    current = st.session_state.active_page if st.session_state.active_page in PAGES else "Dashboard"

    with st.sidebar:
        st.markdown("## 🌐 ErrorSweep")
        st.caption(f"{APP_VERSION} · Main API-first")
        st.markdown(f'<span class="es-badge es-badge-green">{escape(str(st.session_state.role))}</span>', unsafe_allow_html=True)
        st.caption(st.session_state.username or "demo user")
        st.divider()
        side_selected = st.radio(
            "Workspace",
            PAGES,
            index=PAGES.index(current),
            label_visibility="collapsed",
            key="sidebar_page_radio",
        )
        st.divider()
        if st.button("Logout", use_container_width=True, key="sidebar_logout"):
            st.session_state.authenticated = False
            st.rerun()
        st.caption("Main API first. Local/free engines can be tested later.")

    st.markdown(
        f"""
        <div class="es-card" style="margin: 0 0 14px 0;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
            <div>
              <div class="es-metric-label">Workspace Navigation</div>
              <div style="font-size:20px;font-weight:800;color:#fff;">🌐 ErrorSweep</div>
              <p>{escape(APP_VERSION)} · signed in as {escape(str(st.session_state.username or 'demo user'))}</p>
            </div>
            <span class="es-badge es-badge-green">{escape(str(st.session_state.role))}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_cols = st.columns([3, 1])
    with nav_cols[0]:
        top_selected = st.selectbox(
            "Open page",
            PAGES,
            index=PAGES.index(side_selected if side_selected in PAGES else current),
            key="top_page_select",
        )
    with nav_cols[1]:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True, key="top_logout"):
            st.session_state.authenticated = False
            st.rerun()

    selected = top_selected or side_selected or current
    st.session_state.active_page = selected
    return selected


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(f"""
    <div class="es-hero">
      <span class="es-kicker">{escape(kicker)}</span>
      <div class="es-title">{escape(title)}</div>
      <div class="es-sub">{escape(subtitle)}</div>
    </div>
    """, unsafe_allow_html=True)


def metric_cards(items: List[Tuple[str, Any, str]]) -> None:
    """Render metric cards using native Streamlit containers.

    Earlier builds used a raw HTML grid. Some Streamlit deployments escaped part of
    that HTML and showed <div> tags to users. Native cards avoid that issue.
    """
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


# ==========================================================
# Pages
# ==========================================================

def dashboard_page() -> None:
    page_header(
        "Dashboard",
        "Localization operations hub",
        "Manage projects, translation jobs, QA reports, human review, scorecards, and translation memory from one workspace.",
    )

    metric_cards([
        ("Projects", len(st.session_state.projects), "client/product workspaces"),
        ("Jobs", len(st.session_state.jobs), "QA / Pro / Scorecard"),
        ("TM Entries", len(st.session_state.tm_entries), "approved translations"),
        ("Pending Review", len([s for s in st.session_state.review_segments if s.get("Status") != "Approved"]), "segments or sessions"),
    ])

    st.markdown("### Recommended next steps")
    st.markdown("""
    <div class="es-grid-3">
      <div class="es-card"><h3>🗂️ Create a project</h3><p>Set source/target languages, domain, and reusable rules.</p></div>
      <div class="es-card"><h3>🚀 Run QA or Pro</h3><p>Upload a bilingual file or source file and generate review-ready output.</p></div>
      <div class="es-card"><h3>✍️ Open Human Review</h3><p>Approve corrected segments and save only verified translations to TM.</p></div>
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
        with c1:
            name = st.text_input("Project name", placeholder="Mobile App UI")
            organization = st.text_input("Organization", placeholder="Nawin Corp")
        with c2:
            source_lang = st.selectbox("Source language", SUPPORTED_MAIN_API_LANGUAGES, index=SUPPORTED_MAIN_API_LANGUAGES.index("English"))
            targets = st.multiselect("Target languages", SUPPORTED_MAIN_API_LANGUAGES, default=["French"])
        with c3:
            domain = st.selectbox("Domain", ["Software UI", "Marketing", "Legal", "Medical", "E-learning", "General"])
            status = st.selectbox("Status", ["Active", "Draft", "Paused"])

        if st.form_submit_button("Create project", type="primary", use_container_width=True):
            if not name:
                st.error("Project name is required.")
            else:
                project = {
                    "Project ID": new_id("prj"),
                    "Project": name,
                    "Organization": organization or "Default Organization",
                    "Source": source_lang,
                    "Targets": ", ".join(targets) if targets else "",
                    "Domain": domain,
                    "Status": status,
                    "Created": now_iso(),
                }
                st.session_state.projects.append(project)
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
        st.info("No jobs yet. Run QA, Pro, or a Scorecard to create jobs.")


def qa_page() -> None:
    page_header("ErrorSweep QA", "QA run + suggestions", "Review existing translations against deterministic checks, company rules, and main API QA.")

    uploaded = st.file_uploader("Upload bilingual file", type=["xlsx", "csv", "docx", "txt"], key="qa_upload")
    rules_zip = st.file_uploader("Upload rules ZIP (optional)", type=["zip"], key="qa_rules")
    c1, c2, c3 = st.columns(3)
    with c1:
        target_language = st.selectbox("Target language", SUPPORTED_MAIN_API_LANGUAGES, index=SUPPORTED_MAIN_API_LANGUAGES.index("French"))
    with c2:
        domain = st.selectbox("Domain", ["Software UI", "Marketing", "Legal", "Medical", "E-learning", "General"], key="qa_domain")
    with c3:
        run_ai = st.checkbox("Run main API QA", value=True)

    if st.button("Run ErrorSweep QA", type="primary", use_container_width=True, disabled=uploaded is None):
        glossary, dnt, rule_context = parse_rules_zip(rules_zip)
        extracted = extract_file(uploaded, mode="qa")
        st.session_state.glossary.extend(glossary)
        st.session_state.dnt_terms.extend(dnt)

        if not extracted.segments:
            st.error("No bilingual segments found. Check file columns: Source / Target or Source Text / Original Translation.")
            return

        base_rows = deterministic_qa(extracted.segments, glossary + st.session_state.glossary, dnt + st.session_state.dnt_terms, target_language)
        ai_rows = []
        if run_ai:
            ai_rows = qa_with_main_api(extracted.segments, target_language, domain, rule_context)

        rows = base_rows + ai_rows
        job = {
            "Job ID": new_id("job"),
            "Type": "QA",
            "File": uploaded.name,
            "Project": "",
            "Target": target_language,
            "Segments": len(extracted.segments),
            "Issues": len(rows),
            "Status": "Needs Review" if rows else "Completed",
            "Created": now_iso(),
        }
        st.session_state.jobs.append(job)

        # Seed review.
        for seg in extracted.segments:
            st.session_state.review_segments.append({
                "Review ID": new_id("rev"),
                "Job ID": job["Job ID"],
                "Location": seg["location"],
                "Source": seg["source"],
                "Target": seg.get("translation") or seg.get("target", ""),
                "Status": "Needs Review" if any(r.get("Location") == seg["location"] for r in rows) else "Pass",
                "Comment": "",
                "Target Language": target_language,
            })

        st.success("QA completed.")
        st.markdown("### QA Report")
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download QA report CSV", df.to_csv(index=False).encode("utf-8-sig"), "errorsweep_qa_report.csv", "text/csv", use_container_width=True)
            st.download_button("Download QA report Excel", download_excel(df, "QA Report"), "errorsweep_qa_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.success("No issues found.")


def pro_page() -> None:
    page_header("ErrorSweep Pro", "Translate + QA + Human Review", "Use main API translation first, then route uncertain segments to Human Review.")

    uploaded = st.file_uploader("Upload source or bilingual file", type=["xlsx", "csv", "docx", "txt"], key="pro_upload")
    rules_zip = st.file_uploader("Upload rules ZIP (optional)", type=["zip"], key="pro_rules")

    c1, c2, c3 = st.columns(3)
    with c1:
        target_language = st.selectbox("Target language", SUPPORTED_MAIN_API_LANGUAGES, index=SUPPORTED_MAIN_API_LANGUAGES.index("French"), key="pro_tgt")
    with c2:
        domain = st.selectbox("Domain", ["Software UI", "Marketing", "Legal", "Medical", "E-learning", "General"], key="pro_domain")
    with c3:
        review_threshold = st.slider("Allow with review threshold", 1, 25, 12, help="If unresolved rate is under this %, output is allowed but Human Review is required.")

    if st.button("Run Translate + Review", type="primary", use_container_width=True, disabled=uploaded is None):
        glossary, dnt, rule_context = parse_rules_zip(rules_zip)
        extracted = extract_file(uploaded, mode="pro")
        st.session_state.glossary.extend(glossary)
        st.session_state.dnt_terms.extend(dnt)

        if not extracted.segments:
            st.error("No source segments found.")
            return

        with st.spinner("Translating with main API..."):
            translations_by_loc = translate_with_main_api(extracted.segments, target_language, domain, rule_context)

        translated_segments = []
        missing = []
        for seg in extracted.segments:
            tr = preserve_protected(seg["source"], translations_by_loc.get(seg["location"], ""))
            if is_bad_translation(seg["source"], tr, target_language):
                missing.append({"Location": seg["location"], "Source": seg["source"], "Translation": tr})
                tr = "⟦NEEDS HUMAN REVIEW⟧"
            translations_by_loc[seg["location"]] = tr
            translated_segments.append({**seg, "translation": tr, "target": tr})

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

        # Add main API QA only if the file is not fully blocked.
        if gate != "block":
            with st.spinner("Running main API QA..."):
                review_rows.extend(qa_with_main_api(translated_segments, target_language, domain, rule_context))

        output_bytes, mime, output_name = build_output_file(extracted, translations_by_loc)

        job = {
            "Job ID": new_id("job"),
            "Type": "Pro",
            "File": uploaded.name,
            "Project": "",
            "Target": target_language,
            "Segments": len(extracted.segments),
            "Issues": len(review_rows),
            "Status": status,
            "Created": now_iso(),
        }
        st.session_state.jobs.append(job)

        st.session_state.review_segments = [
            s for s in st.session_state.review_segments
            if s.get("Job ID") != job["Job ID"]
        ]
        for seg in translated_segments:
            unresolved = seg["translation"] == "⟦NEEDS HUMAN REVIEW⟧" or any(r.get("Location") == seg["location"] for r in review_rows)
            st.session_state.review_segments.append({
                "Review ID": new_id("rev"),
                "Job ID": job["Job ID"],
                "Location": seg["location"],
                "Source": seg["source"],
                "Target": seg["translation"],
                "Status": "Needs Review" if unresolved else "Machine Translated",
                "Comment": "",
                "Target Language": target_language,
            })

        st.markdown("### Translation preview")
        st.dataframe(pd.DataFrame([
            {"Location": s["location"], "Source": truncate(s["source"]), "Translation": truncate(s["translation"])}
            for s in translated_segments[:100]
        ]), use_container_width=True, hide_index=True)

        if missing:
            with st.expander("Unresolved segments", expanded=True):
                st.dataframe(pd.DataFrame(missing), use_container_width=True, hide_index=True)

        if gate != "block":
            if gate == "review":
                st.warning("Human Review Required before delivery. Open the Human Review page to resolve marked segments.")
            st.download_button("Download translated output", output_bytes, output_name, mime, use_container_width=True)
            st.download_button("Download issue report", pd.DataFrame(review_rows).to_csv(index=False).encode("utf-8-sig"), "errorsweep_pro_issue_report.csv", "text/csv", use_container_width=True)

        if st.button("Open Human Review", use_container_width=True):
            st.session_state.active_page = "Human Review"
            st.rerun()


def human_review_page() -> None:
    page_header("Human Review", "CAT-style segment editor", "Edit target text, review QA issues, apply glossary/TM, approve segments, and save verified translations.")

    if not st.session_state.review_segments:
        st.info("No review segments yet. Run ErrorSweep QA or Pro first.")
        return

    df = pd.DataFrame(st.session_state.review_segments)
    c1, c2, c3 = st.columns(3)
    with c1:
        job_filter = st.selectbox("Job", ["All"] + sorted(df["Job ID"].dropna().unique().tolist()))
    with c2:
        status_filter = st.selectbox("Status", ["All"] + sorted(df["Status"].dropna().unique().tolist()))
    with c3:
        search = st.text_input("Search source/target")

    filtered = df.copy()
    if job_filter != "All":
        filtered = filtered[filtered["Job ID"] == job_filter]
    if status_filter != "All":
        filtered = filtered[filtered["Status"] == status_filter]
    if search:
        filtered = filtered[
            filtered["Source"].astype(str).str.contains(search, case=False, na=False)
            | filtered["Target"].astype(str).str.contains(search, case=False, na=False)
        ]

    st.markdown("### Segment list")
    st.dataframe(filtered[["Review ID", "Job ID", "Location", "Status", "Source", "Target"]], use_container_width=True, hide_index=True)

    review_ids = filtered["Review ID"].tolist()
    if not review_ids:
        return

    selected_id = st.selectbox("Open segment", review_ids)
    segment_index = next((i for i, s in enumerate(st.session_state.review_segments) if s["Review ID"] == selected_id), None)
    if segment_index is None:
        return

    seg = st.session_state.review_segments[segment_index]

    st.markdown("### Editor")
    left, center, right = st.columns([1.1, 1.1, .85])
    with left:
        st.markdown("#### Source")
        st.text_area("Source text", value=seg["Source"], height=220, disabled=True, label_visibility="collapsed")
        st.caption(f"{seg['Location']} · {seg['Target Language']}")

    with center:
        st.markdown("#### Target")
        edited = st.text_area("Target text", value=seg["Target"], height=220, label_visibility="collapsed")
        status = st.selectbox("Review status", ["Needs Review", "Machine Translated", "Approved", "Rejected", "Needs Rework", "Pass"], index=0 if seg["Status"] not in ["Approved", "Rejected", "Needs Rework", "Pass", "Machine Translated"] else ["Needs Review", "Machine Translated", "Approved", "Rejected", "Needs Rework", "Pass"].index(seg["Status"]))
        comment = st.text_area("Reviewer comment", value=seg.get("Comment", ""), height=90)

        c1, c2 = st.columns(2)
        if c1.button("Save segment", use_container_width=True):
            st.session_state.review_segments[segment_index]["Target"] = edited
            st.session_state.review_segments[segment_index]["Status"] = status
            st.session_state.review_segments[segment_index]["Comment"] = comment
            st.success("Segment saved.")
        if c2.button("Approve & Save to TM", type="primary", use_container_width=True):
            st.session_state.review_segments[segment_index]["Target"] = edited
            st.session_state.review_segments[segment_index]["Status"] = "Approved"
            st.session_state.review_segments[segment_index]["Comment"] = comment
            st.session_state.tm_entries.append({
                "TM ID": new_id("tm"),
                "Source Hash": text_hash(seg["Source"]),
                "Source": seg["Source"],
                "Target": edited,
                "Target Language": seg["Target Language"],
                "Domain": "",
                "Approved By": st.session_state.username,
                "Created": now_iso(),
            })
            st.success("Approved and saved to Translation Memory.")

    with right:
        st.markdown("#### Assist panel")
        st.markdown('<span class="es-badge es-badge-green">Glossary</span>', unsafe_allow_html=True)
        glossary_matches = [g for g in st.session_state.glossary if g.get("Source Term", "").lower() in seg["Source"].lower()]
        if glossary_matches:
            st.dataframe(pd.DataFrame(glossary_matches), use_container_width=True, hide_index=True)
        else:
            st.caption("No glossary matches.")

        st.markdown('<span class="es-badge es-badge-yellow">TM matches</span>', unsafe_allow_html=True)
        tm_matches = [t for t in st.session_state.tm_entries if t.get("Source Hash") == text_hash(seg["Source"]) or t.get("Source", "").lower() == seg["Source"].lower()]
        if tm_matches:
            st.dataframe(pd.DataFrame(tm_matches), use_container_width=True, hide_index=True)
        else:
            st.caption("No exact TM matches.")

        st.markdown('<span class="es-badge es-badge-red">DNT</span>', unsafe_allow_html=True)
        dnt_matches = [d for d in st.session_state.dnt_terms if d.get("Term", "").lower() in seg["Source"].lower()]
        if dnt_matches:
            st.dataframe(pd.DataFrame(dnt_matches), use_container_width=True, hide_index=True)
        else:
            st.caption("No DNT matches.")

    st.markdown("### Export")
    export_df = pd.DataFrame(st.session_state.review_segments)
    st.download_button("Download Human Review CSV", export_df.to_csv(index=False).encode("utf-8-sig"), "human_review_segments.csv", "text/csv", use_container_width=True)


def scorecards_page() -> None:
    page_header("Scorecards", "Translator vs reviewer quality score", "Compare translator output with reviewer/final output and generate vendor quality scorecards.")

    source_file = st.file_uploader("Source file", type=["xlsx", "csv", "docx", "txt"], key="score_src")
    translator_file = st.file_uploader("Translator file", type=["xlsx", "csv", "docx", "txt"], key="score_trans")
    reviewer_file = st.file_uploader("Reviewer/final file", type=["xlsx", "csv", "docx", "txt"], key="score_rev")

    if st.button("Generate Scorecard", type="primary", use_container_width=True, disabled=not (translator_file and reviewer_file)):
        trans = extract_file(translator_file, mode="qa")
        rev = extract_file(reviewer_file, mode="qa")

        rows = []
        total_penalty = 0
        total = min(len(trans.segments), len(rev.segments))
        for i in range(total):
            t_seg = trans.segments[i]
            r_seg = rev.segments[i]
            translator = t_seg.get("translation") or t_seg.get("target") or t_seg.get("source", "")
            reviewer = r_seg.get("translation") or r_seg.get("target") or r_seg.get("source", "")
            changed = clean_text(translator) != clean_text(reviewer)
            penalty = 0
            severity = "Pass"
            category = "No change"
            if changed:
                # Simple MVP scoring.
                penalty = 2
                severity = "Minor"
                category = "Reviewer changed translation"
                if extract_placeholders(translator) != extract_placeholders(reviewer):
                    penalty = 10
                    severity = "Critical"
                    category = "Placeholder/formatting"
                elif len(translator) < max(1, len(reviewer) * 0.35):
                    penalty = 5
                    severity = "Major"
                    category = "Omission / incompleteness"
            total_penalty += penalty
            rows.append({
                "Segment": i + 1,
                "Source": t_seg.get("source") or r_seg.get("source", ""),
                "Translator": translator,
                "Reviewer": reviewer,
                "Changed": "Yes" if changed else "No",
                "Category": category,
                "Severity": severity,
                "Penalty": penalty,
            })

        score = max(0, round(100 - (total_penalty / max(total, 1)), 2))
        job = {
            "Job ID": new_id("job"),
            "Type": "Scorecard",
            "File": translator_file.name,
            "Project": "",
            "Target": "",
            "Segments": total,
            "Issues": sum(1 for r in rows if r["Changed"] == "Yes"),
            "Status": "Completed",
            "Created": now_iso(),
        }
        st.session_state.jobs.append(job)

        metric_cards([
            ("Quality Score", score, "100 is best"),
            ("Segments Compared", total, "translator vs reviewer"),
            ("Changed", sum(1 for r in rows if r["Changed"] == "Yes"), "reviewer edits"),
            ("Penalty", total_penalty, "weighted penalty"),
        ])
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download Scorecard Excel", download_excel(df, "Scorecard"), "errorsweep_scorecard.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def memory_rules_page() -> None:
    page_header("Memory & Rules", "Translation memory, glossary, DNT, and client rules", "Manage approved terminology and reusable corrections.")

    tab1, tab2, tab3, tab4 = st.tabs(["Translation Memory", "Glossary", "DNT", "Rule Pack Upload"])

    with tab1:
        st.markdown("### Translation Memory")
        if st.session_state.tm_entries:
            st.dataframe(pd.DataFrame(st.session_state.tm_entries), use_container_width=True, hide_index=True)
        else:
            st.info("No TM entries yet. Approve segments in Human Review to build TM.")
        with st.form("add_tm"):
            source = st.text_area("Source")
            target = st.text_area("Target")
            lang = st.selectbox("Target language", SUPPORTED_MAIN_API_LANGUAGES, key="tm_lang")
            if st.form_submit_button("Add TM entry", use_container_width=True):
                if source and target:
                    st.session_state.tm_entries.append({
                        "TM ID": new_id("tm"),
                        "Source Hash": text_hash(source),
                        "Source": source,
                        "Target": target,
                        "Target Language": lang,
                        "Domain": "",
                        "Approved By": st.session_state.username,
                        "Created": now_iso(),
                    })
                    st.success("TM entry added.")

    with tab2:
        st.markdown("### Glossary")
        with st.form("add_glossary"):
            s = st.text_input("Source term")
            t = st.text_input("Target term")
            src = st.text_input("Rule source", value="Manual")
            if st.form_submit_button("Add glossary term", use_container_width=True):
                if s and t:
                    st.session_state.glossary.append({"Source Term": s, "Target Term": t, "Rule Source": src})
                    st.success("Glossary term added.")
        if st.session_state.glossary:
            st.dataframe(pd.DataFrame(st.session_state.glossary), use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("### Do Not Translate")
        with st.form("add_dnt"):
            term = st.text_input("DNT term")
            src = st.text_input("Rule source", value="Manual")
            if st.form_submit_button("Add DNT term", use_container_width=True):
                if term:
                    st.session_state.dnt_terms.append({"Term": term, "Rule Source": src})
                    st.success("DNT term added.")
        if st.session_state.dnt_terms:
            st.dataframe(pd.DataFrame(st.session_state.dnt_terms), use_container_width=True, hide_index=True)

    with tab4:
        rules_zip = st.file_uploader("Upload rules ZIP", type=["zip"], key="rules_manager_zip")
        if rules_zip and st.button("Parse and save rules", use_container_width=True):
            glossary, dnt, context = parse_rules_zip(rules_zip)
            st.session_state.glossary.extend(glossary)
            st.session_state.dnt_terms.extend(dnt)
            st.success(f"Loaded {len(glossary)} glossary term(s) and {len(dnt)} DNT term(s).")


def team_roles_page() -> None:
    page_header("Team & Roles", "Role-based access shell", "Define team members, roles, and access boundaries.")

    permission_rows = [
        {"Action": "Create projects", "Owner": "Yes", "Admin": "Yes", "PM": "Yes", "Translator": "No", "Reviewer": "No", "Client": "No"},
        {"Action": "Run Pro translation", "Owner": "Yes", "Admin": "Yes", "PM": "Yes", "Translator": "Limited", "Reviewer": "Yes", "Client": "No"},
        {"Action": "Approve segments", "Owner": "Yes", "Admin": "Yes", "PM": "Yes", "Translator": "No", "Reviewer": "Yes", "Client": "No"},
        {"Action": "Save to TM", "Owner": "Yes", "Admin": "Yes", "PM": "Yes", "Translator": "No", "Reviewer": "Yes", "Client": "No"},
        {"Action": "Billing", "Owner": "Yes", "Admin": "No", "PM": "No", "Translator": "No", "Reviewer": "No", "Client": "No"},
    ]
    st.markdown("### Permission matrix")
    st.dataframe(pd.DataFrame(permission_rows), use_container_width=True, hide_index=True)

    st.markdown("### Team")
    with st.form("invite_user"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name")
        email = c2.text_input("Email")
        role = c3.selectbox("Role", ROLES)
        if st.form_submit_button("Add / invite user", use_container_width=True):
            if name and email:
                st.session_state.team.append({"Name": name, "Email": email, "Role": role, "Status": "Invited"})
                st.success("User added.")
    st.dataframe(pd.DataFrame(st.session_state.team), use_container_width=True, hide_index=True)


def billing_page() -> None:
    page_header("Billing", "Plans and usage", "Billing shell for credits, invoices, and plan limits.")

    metric_cards([
        ("Plan", "Demo", "billing integration pending"),
        ("Credits", "Unlimited", "during platform build"),
        ("Invoices", "0", "not configured"),
        ("Gateway", "Razorpay/Stripe", "future integration"),
    ])
    st.info("Billing can be connected after project/jobs/review workflows are stable.")


def account_page() -> None:
    page_header("Account", "Workspace profile", "Manage user profile and workspace settings.")

    with st.form("account_settings"):
        username = st.text_input("Signed in as", value=st.session_state.username)
        role = st.selectbox("Role", ROLES, index=ROLES.index(st.session_state.role) if st.session_state.role in ROLES else 0)
        org = st.text_input("Organization", value="Default Organization")
        if st.form_submit_button("Save account settings", use_container_width=True):
            st.session_state.username = username
            st.session_state.role = role
            st.success("Account settings saved.")


def admin_page() -> None:
    page_header("Admin", "Platform admin", "System settings, diagnostics, and future admin controls.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### System state")
        st.json({
            "version": APP_VERSION,
            "projects": len(st.session_state.projects),
            "jobs": len(st.session_state.jobs),
            "tm_entries": len(st.session_state.tm_entries),
            "review_segments": len(st.session_state.review_segments),
            "openai_configured": bool(secret("OPENAI_API_KEY")),
        })
    with c2:
        st.markdown("### Maintenance")
        if st.button("Clear demo jobs/review only", use_container_width=True):
            st.session_state.jobs = []
            st.session_state.review_segments = []
            st.success("Jobs and review sessions cleared.")
        if st.button("Clear all demo workspace data", use_container_width=True):
            for key in ["projects", "jobs", "tm_entries", "glossary", "dnt_terms", "review_segments"]:
                st.session_state[key] = []
            st.success("Demo workspace cleared.")


def engine_status_page() -> None:
    page_header("Engine Status", "Translation engine registry", "Main API is primary. Local/free engines are optional and can be tested later.")

    rows = []
    rows.append({
        "Engine": "Main API",
        "Purpose": "Primary translation and QA",
        "Endpoint": "OpenAI Responses API",
        "Status": "Ready" if secret("OPENAI_API_KEY") else "Missing API key",
        "Production": "Yes",
    })

    libre = secret("LIBRETRANSLATE_ENDPOINT")
    rows.append({
        "Engine": "LibreTranslate",
        "Purpose": "Optional low-cost MT",
        "Endpoint": libre or "(not configured)",
        "Status": "Optional / not required",
        "Production": "Later",
    })

    indic = secret("INDICTRANS2_ENDPOINT")
    rows.append({
        "Engine": "IndicTrans2",
        "Purpose": "Optional Indic MT",
        "Endpoint": indic or "(not configured)",
        "Status": "Blocked until /translate is reliable",
        "Production": "Later",
    })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### Direct engine note")
    st.warning("Do not depend on temporary trycloudflare URLs for production. Engines should be added later through stable server endpoints.")


# ==========================================================
# App router
# ==========================================================

def render_app() -> None:
    page = sidebar_nav()
    if page == "Dashboard":
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
    elif page == "Engine Status":
        engine_status_page()
    else:
        dashboard_page()


if not st.session_state.authenticated:
    login_page()
else:
    render_app()

