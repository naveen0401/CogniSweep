import streamlit as st
import pandas as pd
import io
import os
import re
import json
import time
import hmac
import zipfile
import math
from datetime import datetime, timezone
import requests
from typing import Any, Dict, List, Tuple, Optional
from html import escape
from urllib.parse import quote

from openai import OpenAI as AI
from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.comments import Comment
from docx import Document

try:
    from google import genai
except Exception:
    genai = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


# ==========================================================
# ERROR SWEEP / ERROR SWEEP PRO
# White-label AI QA + translation workflow
# ==========================================================

st.set_page_config(page_title="ErrorSweep", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.hero {
    background: linear-gradient(135deg, #0f0f0f 0%, #161827 45%, #10213a 100%);
    border: 1px solid #28324a;
    border-radius: 18px;
    padding: 34px;
    margin-bottom: 22px;
    text-align: center;
}
.hero-title {
    font-family: 'Space Mono', monospace;
    font-size: 44px;
    color: #00ff88;
    font-weight: 700;
    margin: 0;
}
.hero-sub { font-size: 16px; color: #a8acc8; margin-top: 8px; }
.hero-badge {
    display: inline-block;
    background: rgba(0,255,136,0.08);
    border: 1px solid rgba(0,255,136,0.25);
    color: #00ff88;
    border-radius: 20px;
    padding: 5px 15px;
    font-size: 12px;
    font-family: 'Space Mono', monospace;
    margin-top: 12px;
}
.note-card {
    background: #101322;
    border: 1px solid #29314a;
    border-radius: 12px;
    padding: 14px 18px;
    margin: 10px 0;
}
.error-card {
    background: #0f0f1a;
    border-left: 4px solid #ff4466;
    border-radius: 0 8px 8px 0;
    padding: 14px;
    margin-bottom: 10px;
}
.error-card.minor { border-left-color: #ffaa00; }
.error-card.major { border-left-color: #ff4466; }
.error-card.critical { border-left-color: #ff0044; }
.error-card.review { border-left-color: #60a5fa; }
.error-type {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.error-before { color: #ff6680; font-size: 14px; margin: 7px 0 2px; }
.error-after { color: #00ff88; font-size: 14px; }
.error-reason { color: #a8acc8; font-size: 12px; }
.severity-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
}
.sev-minor { background: rgba(255,170,0,0.15); color: #ffaa00; }
.sev-major { background: rgba(255,68,102,0.15); color: #ff4466; }
.sev-critical { background: rgba(255,0,68,0.2); color: #ff0044; }
.sev-review { background: rgba(96,165,250,0.15); color: #60a5fa; }
.empty-state { text-align:center; padding:45px; color:#6b7280; border: 1px dashed #2a2a4a; border-radius:12px; }

/* Hide Streamlit public toolbar/menu/footer, including fork/deploy controls where present */
#MainMenu {visibility: hidden; display: none;}
footer {visibility: hidden; display: none;}
header {visibility: hidden; display: none;}
[data-testid="stToolbar"] {visibility: hidden; display: none;}
[data-testid="stDecoration"] {visibility: hidden; display: none;}
[data-testid="stStatusWidget"] {visibility: hidden; display: none;}
[data-testid="stDeployButton"] {visibility: hidden; display: none;}
.stAppDeployButton {visibility: hidden; display: none;}

/* Premium white-label visual system */
:root {
    --es-green: #00ff88;
    --es-cyan: #38bdf8;
    --es-purple: #8b5cf6;
    --es-bg: #080a12;
    --es-card: rgba(16, 19, 34, 0.72);
}
.stApp {
    background:
        radial-gradient(circle at 12% 18%, rgba(0,255,136,0.14), transparent 25%),
        radial-gradient(circle at 86% 14%, rgba(56,189,248,0.12), transparent 28%),
        radial-gradient(circle at 50% 100%, rgba(139,92,246,0.10), transparent 35%),
        #080a12;
}
.hero {
    position: relative;
    overflow: hidden;
    background:
        linear-gradient(135deg, rgba(0,255,136,0.12), rgba(56,189,248,0.08) 42%, rgba(139,92,246,0.10)),
        rgba(12, 15, 26, 0.9);
    box-shadow: 0 28px 80px rgba(0,0,0,0.35);
}
.hero::after {
    content: "";
    position: absolute;
    width: 420px;
    height: 420px;
    right: -150px;
    top: -190px;
    background: radial-gradient(circle, rgba(0,255,136,0.22), transparent 62%);
    filter: blur(4px);
}
.hero-title {
    background: linear-gradient(90deg, #00ff88, #38bdf8, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.glass-card, div[data-testid="stExpander"] {
    background: rgba(16, 19, 34, 0.74) !important;
    border: 1px solid rgba(56,189,248,0.18) !important;
    border-radius: 16px !important;
    box-shadow: 0 18px 44px rgba(0,0,0,0.22);
}
.stButton > button, .stDownloadButton > button {
    border-radius: 14px !important;
    border: 1px solid rgba(0,255,136,0.25) !important;
    background: linear-gradient(90deg, #00cc6a, #0ea5e9) !important;
    color: white !important;
    font-weight: 800 !important;
    letter-spacing: .2px;
    box-shadow: 0 10px 28px rgba(14,165,233,0.20);
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 16px 36px rgba(0,255,136,0.20);
}
[data-testid="stMetric"] {
    background: rgba(16,19,34,.72);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 16px;
    padding: 16px;
}
.es-visual-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin: 18px 0 24px 0;
}
.es-tile {
    background: rgba(16, 19, 34, 0.74);
    border: 1px solid rgba(0,255,136,0.14);
    border-radius: 16px;
    padding: 18px;
}
.es-tile h4 { margin: 0 0 6px 0; color: #e5e7eb; }
.es-tile p { margin: 0; color: #9ca3af; font-size: 13px; }
@media (max-width: 900px) { .es-visual-grid { grid-template-columns: 1fr; } }

</style>
""",
    unsafe_allow_html=True,
)

st.markdown("""
<div class="es-visual-grid">
  <div class="es-tile"><h4>Secure Review</h4><p>Private server-side AI processing with protected credentials.</p></div>
  <div class="es-tile"><h4>Smart Routing</h4><p>Automatically detects QA, translation, source columns, and target areas.</p></div>
  <div class="es-tile"><h4>Client Rule Packs</h4><p>Optional ZIP rules for glossary, DNT, style guide, and instructions.</p></div>
</div>
""", unsafe_allow_html=True)


# ==========================================================
# CONFIG / CONSTANTS
# ==========================================================

HIGHLIGHT_FILL = PatternFill(start_color="FFF59D", end_color="FFF59D", fill_type="solid")
HEADER_FILL = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
HEADER_FONT = Font(bold=True)
REPORT_SHEETS = {"ErrorSweep Report", "ErrorSweep Pro Review", "Correction Report", "Remaining Errors"}

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

STRICTNESS_GUIDE = {
    "Lenient": "Only flag clear, obvious errors. Ignore minor style preferences.",
    "Standard": "Flag clear errors and notable quality issues.",
    "Strict": "Flag all real errors including minor style, tone, punctuation, spacing, and consistency issues.",
    "Very Strict": "Flag every real issue, including subtle fluency, register, micro-style, punctuation, spacing, and client-style deviations.",
}

SOURCE_KEYWORDS_STRONG = [
    "source text", "source", "src", "english source", "source segment", "source string", "source copy"
]
TARGET_KEYWORDS_STRONG = [
    "original translation", "translation", "target", "target text", "translated text", "localized", "target segment", "translated string"
]

SKIP_SHEET_KEYWORDS = [
    "instruction",
    "lqa instruction",
    "calculation",
    "error_count",
    "error counts",
    "pull-out",
    "pull_out",
    "summary",
    "dashboard",
    "quality evaluation",
    "quality eval",
    "score card",
]

# Common Telugu UI/loanword ZWNJ patterns. This is intentionally conservative.
TELUGU_ZWNJ_BASE_SUFFIXES = {
    "డాక్యుమెంట్": ["ను", "లను", "లు", "తో", "కి", "లో"],
    "పాస్‌వర్డ్": ["ను", "తో", "లో", "కి"],
    "పాస్వర్డ్": ["ను", "తో", "లో", "కి"],
    "డాష్‌బోర్డ్": ["ను", "లో", "కి"],
    "అప్‌లోడ్": ["ను", "చేయండి", "తో"],
    "డౌన్‌లోడ్": ["ను", "చేయండి", "తో"],
    "టెంప్లేట్": ["లు", "ను", "లను", "లో"],
    "సెట్టింగ్": ["లు", "లను", "లో", "కి"],
    "కనెక్షన్": ["ను", "తో", "లో"],
    "ఫైల్": ["ను", "లను", "లు", "లో"],
}

PLACEHOLDER_PATTERN = re.compile(
    r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|\b\w+_id\b|<[^>]+>)"
)
NUMBER_PATTERN = re.compile(r"\d+(?:[.,:]\d+)*")
URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


# ==========================================================
# SECRETS / CLIENTS
# ==========================================================

def get_secret_value(name: str, default: Optional[str] = None) -> Optional[str]:
    env_value = os.environ.get(name)
    if env_value:
        return env_value
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass
    return default


def managed_ai_allowed() -> bool:
    """Managed API keys are disabled by default to protect owner cost.

    Set ALLOW_MANAGED_AI = "true" in Streamlit Secrets only if you want
    server-side keys to be used. Users can still enter their own keys in
    Control Center for the current browser session.
    """
    value = str(get_secret_value("ALLOW_MANAGED_AI", "false") or "false").strip().lower()
    return value in {"true", "1", "yes", "on"}


def get_user_openai_key() -> str:
    return str(st.session_state.get("es_user_openai_api_key", "") or "").strip()


def get_user_gemini_key() -> str:
    return str(st.session_state.get("es_user_gemini_api_key", "") or "").strip()


def get_openai_client() -> Optional[AI]:
    key = get_user_openai_key()
    if not key and managed_ai_allowed():
        key = get_secret_value("OPENAI_API_KEY") or ""
    if not key:
        return None
    return AI(api_key=key, timeout=60, max_retries=1)


def get_gemini_client():
    key = get_user_gemini_key()
    if not key and managed_ai_allowed():
        key = get_secret_value("GEMINI_API_KEY") or ""
    if not key or genai is None:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None


# ==========================================================
# BASIC HELPERS
# ==========================================================

def normalize_text(text: Any) -> str:
    """Normalize without removing ZWNJ. ZWNJ must be preserved for QA."""
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\u200B", "")  # zero width space
    text = text.replace("\u200D", "")  # zero width joiner
    text = text.replace("\u00A0", " ")  # non-breaking space
    return text.strip("\n\r")


def decode_text_bytes(data: bytes) -> Tuple[str, str]:
    """Decode uploaded text files without destroying Windows/CP1252 punctuation.

    Many client text files contain CP1252 bytes such as NBSP (0xA0), smart quotes,
    and en dash. Decoding those with UTF-8 + errors=ignore removes/changes
    characters and can collapse the visual pattern.
    """
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"




def looks_like_binary(data: bytes) -> bool:
    """Return True when a file is probably binary and should not be decoded as text.

    This prevents unknown/binary uploads (or unsupported spreadsheet formats)
    from being decoded as latin-1 and producing tens of thousands of fake text segments.
    """
    if not data:
        return False
    sample = data[:8192]
    if b"\x00" in sample:
        return True
    text_chars = bytes(range(32, 127)) + b"\n\r\t\b\f"
    non_text = sum(1 for b in sample if b not in text_chars and b < 128)
    return (non_text / max(len(sample), 1)) > 0.30


def is_openpyxl_compatible(data: bytes) -> bool:
    """Detect xlsx-like ZIP workbooks even if the extension is unusual."""
    if not data.startswith(b"PK"):
        return False
    try:
        import zipfile as _zipfile
        with _zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            return "xl/workbook.xml" in names or any(n.startswith("xl/worksheets/") for n in names)
    except Exception:
        return False


def uploaded_file_bytes(uploaded_file) -> bytes:
    try:
        return uploaded_file.getvalue()
    except Exception:
        try:
            pos = uploaded_file.tell()
        except Exception:
            pos = None
        data = uploaded_file.read()
        if pos is not None:
            try:
                uploaded_file.seek(pos)
            except Exception:
                pass
        return data


def max_processable_segments_for_credits(profile: Optional[Dict[str, Any]], workflow: str, rules_zip_used: bool = False, independent_review: bool = False) -> int:
    """How many segments the user's remaining ErrorSweep app credits can cover."""
    rem = remaining_credits(profile)
    overhead = 1 if rules_zip_used else 0
    rem_after_overhead = rem - overhead
    if rem_after_overhead <= 0:
        return 0
    if workflow == "qa":
        return rem_after_overhead * 100

    best = 0
    for n in range(1, 200000, 75):
        cost = calculate_credit_cost("pro", n, rules_zip_used=rules_zip_used, independent_review=independent_review)
        if cost <= rem:
            best = n
        else:
            break
    return best


def maybe_limit_segments_to_available_credits(
    segments: List[Dict[str, Any]],
    profile: Optional[Dict[str, Any]],
    workflow: str,
    rules_zip_used: bool = False,
    independent_review: bool = False,
) -> Tuple[List[Dict[str, Any]], int, str]:
    """Require app credits, but process a partial file if current credits cannot cover the full file."""
    full_count = len(segments)
    full_cost = calculate_credit_cost(workflow, full_count, rules_zip_used=rules_zip_used, independent_review=independent_review)
    ok, msg = credit_preflight(profile, full_cost)
    if ok:
        return segments, full_cost, f"Full file covered: {full_count} segment(s), {full_cost} app credit(s)."

    allowed = max_processable_segments_for_credits(profile, workflow, rules_zip_used=rules_zip_used, independent_review=independent_review)
    if allowed <= 0:
        return [], full_cost, msg

    limited = segments[:allowed]
    limited_cost = calculate_credit_cost(workflow, len(limited), rules_zip_used=rules_zip_used, independent_review=independent_review)
    return limited, limited_cost, (
        f"Not enough credits for full file ({full_count} segments require {full_cost} credits). "
        f"Processing first {len(limited)} segment(s) using available credits ({limited_cost} credit(s)). "
        "Upgrade/add credits for full-file processing."
    )

def is_visually_blank_line(line: str) -> bool:
    return line.replace("\u00A0", " ").strip() == ""


def clean_line_for_ai(line: str) -> str:
    """Clean a line for AI while preserving actual source meaning and spacing."""
    line = line.rstrip("\r\n")
    line = line.replace("\u00A0", " ")
    # collapse only excessive internal whitespace created by NBSP-heavy text files
    line = re.sub(r"[ \t]+", " ", line)
    return normalize_text(line).strip()


def should_skip_text_translation_line(clean_line: str, non_empty_position: int) -> bool:
    """Skip column headers in simple Source/Target text templates."""
    low = clean_line.lower().strip()
    if non_empty_position <= 2 and low in {"source", "target"}:
        return True
    return False


def build_preserved_text_translation(text_original: str, segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str]) -> bytes:
    """Build a translated TXT/SRT-like output while keeping the original line pattern.

    For each translated source line, the original line remains in place and the
    translation is written into the following blank line when available. If the
    next line is not blank, the translation is inserted immediately below.
    This prevents the old CSV-table output from changing the user's template.
    """
    lines = text_original.splitlines(keepends=True)
    if not lines and text_original:
        lines = [text_original]

    by_line_index: Dict[int, str] = {}
    for seg in segments:
        idx = seg.get("line_index")
        loc = seg.get("location", "")
        trans = translations_by_loc.get(loc, "")
        if idx is not None and trans:
            by_line_index[int(idx)] = trans.strip()

    output_lines: List[str] = []
    replaced_blank_indices = set()

    for i, line in enumerate(lines):
        if i in replaced_blank_indices:
            continue

        output_lines.append(line)

        if i not in by_line_index:
            continue

        translation = by_line_index[i]
        line_ending_match = re.search(r"(\r\n|\n|\r)$", line)
        line_ending = line_ending_match.group(1) if line_ending_match else "\n"

        next_index = i + 1
        if next_index < len(lines) and is_visually_blank_line(lines[next_index]):
            next_ending_match = re.search(r"(\r\n|\n|\r)$", lines[next_index])
            next_ending = next_ending_match.group(1) if next_ending_match else line_ending
            output_lines.append(translation + next_ending)
            replaced_blank_indices.add(next_index)
        else:
            output_lines.append(translation + line_ending)

    return "".join(output_lines).encode("utf-8-sig")


def visible_invisibles(text: Any) -> str:
    """Return report-safe text while keeping ZWNJ invisible.

    Earlier versions displayed U+200C as ⟨ZWNJ⟩ in report sheets.
    That was useful for debugging, but it looks noisy for clients.
    This keeps the actual ZWNJ character in suggestions/output while hiding
    the debug label from reports and UI.
    """
    text = str(text) if text is not None else ""
    return (
        text
        .replace("\u200B", "")
        .replace("\u200D", "")
        .replace("\u00A0", " ")
    )


def unlimited_scan(max_segments: int) -> bool:
    """max_segments <= 0 means scan the whole file."""
    try:
        return int(max_segments) <= 0
    except Exception:
        return True


def reached_segment_limit(segments: List[Dict[str, Any]], max_segments: int) -> bool:
    return (not unlimited_scan(max_segments)) and len(segments) >= int(max_segments)


def limit_sequence(items, max_segments: int):
    if unlimited_scan(max_segments):
        return list(items)
    return list(items)[:int(max_segments)]


def style_header(sheet):
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def extract_json_array(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end + 1]
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def safe_lower(text: Any) -> str:
    return normalize_text(text).lower()


def first_non_empty(*values: Any) -> str:
    for v in values:
        if v is not None and str(v).strip():
            return str(v)
    return ""


def truncate(text: Any, max_len: int = 500) -> str:
    text = visible_invisibles(text)
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


# ==========================================================
# RULE ZIP PARSING
# ==========================================================

def text_from_docx_bytes(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    parts = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            vals = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if vals:
                parts.append(" | ".join(vals))
    return "\n".join(parts)


def text_from_xlsx_bytes(data: bytes) -> str:
    wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"# Sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
            if vals:
                parts.append(" | ".join(vals))
    return "\n".join(parts)


def text_from_pdf_bytes(data: bytes) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages[:20]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(pages)


def split_chunks(text: str, max_chars: int = 1200) -> List[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > max_chars:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)
    return chunks[:80]


def parse_csv_like_rules(text: str, source_name: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    glossary, dnt = [], []
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        return glossary, dnt

    lower_cols = {str(c).lower().strip(): c for c in df.columns}

    # DNT columns
    dnt_col = None
    for key in lower_cols:
        if "dnt" in key or "do not translate" in key or "non translatable" in key or "locked" in key:
            dnt_col = lower_cols[key]
            break
    if dnt_col:
        for v in df[dnt_col].dropna().astype(str).tolist():
            if v.strip():
                dnt.append({"term": v.strip(), "source": source_name})

    # Glossary source/target columns
    src_col, tgt_col = None, None
    for key in lower_cols:
        if key in ["source", "source term", "english", "term", "src"] or "source" in key:
            src_col = lower_cols[key]
            break
    for key in lower_cols:
        if key in ["target", "target term", "translation", "translated term", "tgt"] or "target" in key or "translation" in key:
            tgt_col = lower_cols[key]
            break

    if src_col and tgt_col and src_col != tgt_col:
        for _, row in df.iterrows():
            src = str(row[src_col]).strip() if pd.notna(row[src_col]) else ""
            tgt = str(row[tgt_col]).strip() if pd.notna(row[tgt_col]) else ""
            if src and tgt:
                glossary.append({"source_term": src, "target_term": tgt, "source": source_name})

    return glossary, dnt


@st.cache_data(show_spinner=False)
def parse_rules_zip_bytes(zip_bytes: bytes) -> Dict[str, Any]:
    rules = {
        "chunks": [],
        "glossary": [],
        "dnt": [],
        "files": [],
        "warnings": [],
    }

    if not zip_bytes:
        return rules

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as e:
        rules["warnings"].append(f"Could not read ZIP: {e}")
        return rules

    total_size = 0
    max_files = 40
    max_total_size = 25 * 1024 * 1024

    for idx, info in enumerate(zf.infolist()):
        if idx >= max_files:
            rules["warnings"].append("ZIP file limit reached; some files were ignored.")
            break
        if info.is_dir():
            continue
        if info.file_size > 8 * 1024 * 1024:
            rules["warnings"].append(f"Skipped large file: {info.filename}")
            continue
        total_size += info.file_size
        if total_size > max_total_size:
            rules["warnings"].append("ZIP total size limit reached; some files were ignored.")
            break

        name = info.filename
        lower = name.lower()
        try:
            data = zf.read(info)
        except Exception:
            continue

        text = ""
        try:
            if lower.endswith((".txt", ".md", ".srt", ".xml", ".xliff", ".json", ".html")):
                text = data.decode("utf-8", errors="ignore")
            elif lower.endswith(".csv"):
                text = data.decode("utf-8", errors="ignore")
                glossary, dnt = parse_csv_like_rules(text, name)
                rules["glossary"].extend(glossary)
                rules["dnt"].extend(dnt)
            elif lower.endswith(".xlsx"):
                text = text_from_xlsx_bytes(data)
                glossary, dnt = parse_csv_like_rules(text.replace(" | ", ","), name)
                rules["glossary"].extend(glossary)
                rules["dnt"].extend(dnt)
            elif lower.endswith(".docx"):
                text = text_from_docx_bytes(data)
            elif lower.endswith(".pdf"):
                text = text_from_pdf_bytes(data)
            else:
                continue
        except Exception as e:
            rules["warnings"].append(f"Could not parse {name}: {e}")
            continue

        text = normalize_text(text)
        if not text:
            continue

        rules["files"].append(name)
        for chunk in split_chunks(text):
            rules["chunks"].append({"source": name, "text": chunk})

    # Heuristic: collect DNT terms from lines like DNT: term or Do Not Translate: term
    for chunk in rules["chunks"]:
        for line in chunk["text"].splitlines():
            if re.search(r"\b(DNT|Do Not Translate|Non-translatable)\b", line, re.I):
                parts = re.split(r"[:\-|,]", line, maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    candidate = parts[1].strip()
                    if len(candidate) <= 80:
                        rules["dnt"].append({"term": candidate, "source": chunk["source"]})

    return rules


def retrieve_relevant_rules(segment: Dict[str, Any], rules: Dict[str, Any], max_chars: int = 1800) -> str:
    if not rules:
        return ""

    source = normalize_text(segment.get("source", ""))
    target = normalize_text(segment.get("translation", "") or segment.get("text", ""))
    combined = (source + " " + target).lower()
    tokens = set(re.findall(r"[\w\u0C00-\u0C7F]+", combined))

    selected = []

    # Relevant glossary
    gloss_lines = []
    for g in rules.get("glossary", [])[:300]:
        src = g.get("source_term", "")
        tgt = g.get("target_term", "")
        if src and (src.lower() in combined or any(t.lower() in combined for t in src.split())):
            gloss_lines.append(f"{src} => {tgt} ({g.get('source','')})")
        if len("\n".join(gloss_lines)) > 600:
            break
    if gloss_lines:
        selected.append("Glossary:\n" + "\n".join(gloss_lines))

    # Relevant DNT
    dnt_lines = []
    for d in rules.get("dnt", [])[:300]:
        term = d.get("term", "")
        if term and term.lower() in combined:
            dnt_lines.append(f"Do not translate: {term} ({d.get('source','')})")
        if len("\n".join(dnt_lines)) > 500:
            break
    if dnt_lines:
        selected.append("DNT rules:\n" + "\n".join(dnt_lines))

    # Style guide chunks by token overlap
    scored = []
    for ch in rules.get("chunks", [])[:100]:
        ch_text = ch["text"]
        ch_tokens = set(re.findall(r"[\w\u0C00-\u0C7F]+", ch_text.lower()))
        score = len(tokens.intersection(ch_tokens))
        if score > 0:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)

    for _, ch in scored[:3]:
        selected.append(f"Rule source: {ch['source']}\n{ch['text'][:700]}")
        if len("\n\n".join(selected)) > max_chars:
            break

    return "\n\n".join(selected)[:max_chars]


# ==========================================================
# SEGMENT EXTRACTION
# ==========================================================

def detect_source_target_columns(headers: List[str], source_hint: str = "", target_hint: str = "") -> Tuple[Optional[int], Optional[int]]:
    """
    Detect real content columns, not metadata rows.
    Excel review forms often have rows like Source language* / Target language* before the actual table.
    Those rows must not be treated as Source/Translation headers.
    """
    headers_clean = [normalize_text(h).lower() for h in headers]

    metadata_terms = [
        "source language", "target language", "client", "project id", "date",
        "number of checked words", "checked words", "review date"
    ]

    strong_source_terms = [
        "source text", "source segment", "source string", "source copy", "source"
    ]
    strong_target_terms = [
        "original translation", "translation", "target text", "target segment",
        "translated text", "translated string", "localized", "target"
    ]

    def bad_metadata_header(h: str) -> bool:
        return any(term in h for term in metadata_terms)

    def find_by_hint(hint: str) -> Optional[int]:
        if not hint:
            return None
        hint = hint.lower().strip()
        try:
            idx = int(hint)
            if 1 <= idx <= len(headers):
                return idx - 1
            if 0 <= idx < len(headers):
                return idx
        except ValueError:
            pass
        for i, h in enumerate(headers_clean):
            if h == hint and not bad_metadata_header(h):
                return i
        for i, h in enumerate(headers_clean):
            if hint in h and not bad_metadata_header(h):
                return i
        return None

    src_idx = find_by_hint(source_hint)
    tgt_idx = find_by_hint(target_hint)

    if src_idx is None:
        for term in strong_source_terms:
            for i, h in enumerate(headers_clean):
                if bad_metadata_header(h):
                    continue
                if term == h or term in h:
                    src_idx = i
                    break
            if src_idx is not None:
                break

    if tgt_idx is None:
        for term in strong_target_terms:
            for i, h in enumerate(headers_clean):
                if bad_metadata_header(h):
                    continue
                if term == h or term in h:
                    tgt_idx = i
                    break
            if tgt_idx is not None:
                break

    return src_idx, tgt_idx


def score_header_row(headers: List[str], src_idx: Optional[int], tgt_idx: Optional[int], need_target: bool) -> int:
    joined = " | ".join([normalize_text(h).lower() for h in headers])
    score = 0

    if "source text" in joined:
        score += 100
    if "original translation" in joined:
        score += 120
    if "suggested translation" in joined:
        score += 40
    if "error category" in joined or "error severity" in joined:
        score += 25
    if "item no" in joined or "item no." in joined:
        score += 20

    bad_rows = [
        "source language", "target language", "client", "project id", "date",
        "number of checked words", "quality evaluation score card"
    ]
    if any(term in joined for term in bad_rows):
        score -= 200

    if src_idx is not None:
        score += 20
    if tgt_idx is not None:
        score += 20
    elif need_target:
        score -= 100

    return score


def find_excel_header_row(rows: List[Any], source_hint: str, target_hint: str, need_target: bool = True) -> Tuple[int, List[str], Optional[int], Optional[int]]:
    """
    Find the real content table header. This prevents metadata rows like Source language* / Target language*
    from being mistaken as the actual QA columns.
    """
    max_scan = min(len(rows), 50)
    best = (None, -9999, [], None, None)

    for row_index in range(max_scan):
        headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[row_index]]
        if not any(headers):
            continue
        src, tgt = detect_source_target_columns(headers, source_hint, target_hint)
        score = score_header_row(headers, src, tgt, need_target)
        if score > best[1]:
            best = (row_index, score, headers, src, tgt)

    row_index, score, headers, src, tgt = best

    if row_index is not None and src is not None and ((tgt is not None) or not need_target) and score >= 60:
        return row_index, headers, src, tgt

    if source_hint or target_hint:
        for row_index in range(max_scan):
            headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[row_index]]
            src, tgt = detect_source_target_columns(headers, source_hint, target_hint)
            if src is not None and ((tgt is not None) or not need_target):
                return row_index, headers, src, tgt

    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[0]] if rows else []
    return 0, headers, None, None

def should_skip_sheet(sheet_name: str, skip_non_content: bool) -> bool:
    if sheet_name in REPORT_SHEETS:
        return True
    if not skip_non_content:
        return False
    lower = sheet_name.lower()
    return any(k in lower for k in SKIP_SHEET_KEYWORDS)


# ==========================================================
# AUTO TASK + LAYOUT DETECTION
# ==========================================================

def infer_task_from_request(request_text: str) -> Optional[str]:
    """Return "qa", "pro" (translation workflow), or None."""
    t = (request_text or "").lower()
    if not t.strip():
        return None
    translate_terms = [
        "translate", "translation", "localize", "localise", "localization",
        "target language", "generate target", "fill target", "prepare translation",
        "tl", "t9n"
    ]
    qa_terms = [
        "qa", "review", "proofread", "proof read", "check", "lqa",
        "linguistic review", "error report", "evaluate", "validation", "verify",
        "quality check"
    ]
    translate_score = sum(1 for k in translate_terms if k in t)
    qa_score = sum(1 for k in qa_terms if k in t)
    if translate_score > qa_score:
        return "pro"
    if qa_score > translate_score:
        return "qa"
    return None


def _bytes_io(uploaded_file):
    return io.BytesIO(uploaded_file.getvalue())


def _nonempty_ratio(values: List[str]) -> float:
    if not values:
        return 0.0
    non_empty = sum(1 for v in values if normalize_text(v))
    return non_empty / max(len(values), 1)


def infer_task_from_file(uploaded_file, source_hint: str = "", target_hint: str = "") -> Tuple[str, str]:
    """
    Heuristic file-level task detector.
    Returns (task, reason), where task is "qa" or "pro".
    """
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".xlsx"):
            wb = load_workbook(_bytes_io(uploaded_file), data_only=False)
            for ws in wb.worksheets:
                if should_skip_sheet(ws.title, True):
                    continue
                rows = list(ws.iter_rows(values_only=False))
                if not rows:
                    continue
                header_idx, headers, src_idx, tgt_idx = find_excel_header_row(rows, source_hint, target_hint, need_target=False)
                if src_idx is not None:
                    if tgt_idx is None:
                        return "pro", f"Detected source column in Excel sheet '{ws.title}' but no target column."
                    target_values = []
                    for row in rows[header_idx + 1: header_idx + 101]:
                        if len(row) <= max(src_idx, tgt_idx):
                            continue
                        target_values.append(normalize_text(row[tgt_idx].value or ""))
                    if _nonempty_ratio(target_values) >= 0.20:
                        return "qa", f"Detected populated source + target columns in Excel sheet '{ws.title}'."
                    return "pro", f"Detected source column with mostly empty target column in Excel sheet '{ws.title}'."
            return "pro", "No reliable target translations found in Excel."

        if name.endswith(".csv"):
            df = pd.read_csv(_bytes_io(uploaded_file))
            src_idx, tgt_idx = detect_source_target_columns(list(df.columns), source_hint, target_hint)
            if src_idx is not None:
                if tgt_idx is None:
                    return "pro", "Detected source column in CSV but no target column."
                tgt_col = df.columns[tgt_idx]
                sample = [normalize_text(x) for x in df[tgt_col].head(100).fillna("").tolist()]
                if _nonempty_ratio(sample) >= 0.20:
                    return "qa", "Detected populated source + target columns in CSV."
                return "pro", "Detected source column with mostly empty target column in CSV."
            return "pro", "No source/target CSV columns detected."

        if name.endswith(".docx"):
            doc = Document(_bytes_io(uploaded_file))
            for table_idx, table in enumerate(doc.tables, start=1):
                header_idx, headers, src_idx, tgt_idx = find_docx_table_header(table, source_hint, target_hint, need_target=False)
                if src_idx is not None:
                    if tgt_idx is None:
                        return "pro", f"Detected source column in DOCX table {table_idx} but no target column."
                    vals = []
                    for row in table.rows[header_idx + 1: header_idx + 101]:
                        if len(row.cells) <= max(src_idx, tgt_idx):
                            continue
                        vals.append(get_docx_cell_text(row.cells[tgt_idx]))
                    if _nonempty_ratio(vals) >= 0.20:
                        return "qa", f"Detected populated source + target columns in DOCX table {table_idx}."
                    return "pro", f"Detected source column with mostly blank target column in DOCX table {table_idx}."
            paras = [normalize_text(p.text) for p in doc.paragraphs if normalize_text(p.text)]
            if len(paras) >= 2 and paras[0].lower() in {"source", "source text"} and paras[1].lower() in {"target", "translation", "original translation"}:
                return "pro", "Detected Source/Target text template in DOCX."
            return "pro", "DOCX appears source-only."

        raw = uploaded_file.getvalue()
        txt, _ = decode_text_bytes(raw)
        clean_lines = [clean_line_for_ai(x) for x in txt.splitlines()]
        nonempty = [x for x in clean_lines if x]
        if len(nonempty) >= 2 and nonempty[0].lower() in {"source", "source text"} and nonempty[1].lower() in {"target", "translation", "original translation"}:
            return "pro", "Detected Source/Target line-template."
        tab_pairs = 0
        for line in nonempty[:100]:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                tab_pairs += 1
        if tab_pairs >= 3:
            return "qa", "Detected tab-separated source/target pairs."
        return "pro", "Text file appears source-only."
    except Exception as e:
        return "pro", f"Auto-detection fallback selected translation because layout detection failed: {e}"


# ==========================================================
# DOCX TABLE HELPERS
# ==========================================================

def get_docx_cell_text(cell) -> str:
    return "\n".join(p.text for p in cell.paragraphs).strip()


def set_docx_cell_text(cell, text: str) -> None:
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.text = ""
    if cell.paragraphs:
        cell.paragraphs[0].add_run(text)
    else:
        cell.add_paragraph(text)


def set_docx_paragraph_text(paragraph, text: str) -> None:
    for run in paragraph.runs:
        run.text = ""
    paragraph.add_run(text)


def find_docx_table_header(table, source_hint: str, target_hint: str, need_target: bool = True):
    max_scan = min(len(table.rows), 30)
    best = (None, -9999, [], None, None)
    for row_idx in range(max_scan):
        headers = [get_docx_cell_text(cell) for cell in table.rows[row_idx].cells]
        if not any(headers):
            continue
        src, tgt = detect_source_target_columns(headers, source_hint, target_hint)
        score = score_header_row(headers, src, tgt, need_target)
        joined = " ".join(str(h).lower() for h in headers)
        if "source text" in joined:
            score += 120
        if "original translation" in joined or "translation" in joined:
            score += 80
        if score > best[1]:
            best = (row_idx, score, headers, src, tgt)
    row_idx, score, headers, src, tgt = best
    if row_idx is not None and src is not None and ((tgt is not None) or not need_target) and score >= 40:
        return row_idx, headers, src, tgt
    return 0, [], None, None


def is_valid_docx_source(text: str) -> bool:
    t = normalize_text(text)
    if len(t) < 2:
        return False
    if t.lower() in {"source", "target", "source text", "original translation", "translation", "target text"}:
        return False
    return True


def extract_excel_segments(uploaded_file, source_hint: str, target_hint: str, mode: str, max_segments: int, skip_non_content: bool, deep_scan: bool):
    wb = load_workbook(uploaded_file)
    segments = []
    logs = []
    cell_map = {}
    translation_col_map = {}

    need_target = mode == "qa"

    for ws in wb.worksheets:
        if should_skip_sheet(ws.title, skip_non_content):
            logs.append(f"Skipped sheet: {ws.title}")
            continue

        rows = list(ws.iter_rows(values_only=False))
        if not rows:
            continue

        header_idx, headers, src_idx, tgt_idx = find_excel_header_row(rows, source_hint, target_hint, need_target=need_target)

        if src_idx is not None and (tgt_idx is not None or mode == "pro"):
            src_name = headers[src_idx] if src_idx < len(headers) else "Source"
            tgt_name = headers[tgt_idx] if tgt_idx is not None and tgt_idx < len(headers) else "AI Translation"
            logs.append(f"{ws.title}: column mode [{src_name}] -> [{tgt_name}]")

            # For Pro, create output translation column if target column is missing.
            output_col_idx = tgt_idx
            if mode == "pro" and output_col_idx is None:
                output_col_idx = ws.max_column
                ws.cell(row=header_idx + 1, column=output_col_idx + 1).value = "AI Translation"
                logs.append(f"{ws.title}: created output column [AI Translation]")

            data_rows = rows[header_idx + 1:]
            for abs_row, row in enumerate(data_rows, start=header_idx + 2):
                if len(row) <= src_idx:
                    continue
                source_text = normalize_text(row[src_idx].value or "")
                if not source_text or len(source_text) < 2:
                    continue

                translation_text = ""
                target_cell = None
                if output_col_idx is not None:
                    if len(row) > output_col_idx:
                        target_cell = row[output_col_idx]
                    else:
                        target_cell = ws.cell(row=abs_row, column=output_col_idx + 1)
                    translation_text = normalize_text(target_cell.value or "")

                if mode == "qa" and not translation_text:
                    continue

                loc = f"{ws.title}!R{abs_row}"
                seg = {
                    "id": len(segments) + 1,
                    "file_type": "xlsx",
                    "sheet": ws.title,
                    "location": loc,
                    "row": abs_row,
                    "source": source_text,
                    "translation": translation_text,
                    "text": translation_text if mode == "qa" else source_text,
                    "mode": "bilingual" if translation_text else "source_only",
                    "source_header": src_name,
                    "target_header": tgt_name,
                }
                segments.append(seg)
                if target_cell is not None:
                    cell_map[loc] = target_cell
                translation_col_map[loc] = (ws.title, abs_row, output_col_idx)
                if reached_segment_limit(segments, max_segments):
                    return wb, segments, cell_map, translation_col_map, logs

        elif deep_scan:
            logs.append(f"{ws.title}: no source/target columns found; deep-scan text cells")
            for row in rows:
                for cell in row:
                    if getattr(cell, "data_type", None) == "f":
                        continue
                    if cell.value and isinstance(cell.value, str) and len(cell.value.strip()) > 3:
                        loc = f"{ws.title}!{cell.coordinate}"
                        seg = {
                            "id": len(segments) + 1,
                            "file_type": "xlsx",
                            "sheet": ws.title,
                            "location": loc,
                            "row": cell.row,
                            "source": "",
                            "translation": normalize_text(cell.value),
                            "text": normalize_text(cell.value),
                            "mode": "monolingual",
                        }
                        segments.append(seg)
                        cell_map[loc] = cell
                        if reached_segment_limit(segments, max_segments):
                            return wb, segments, cell_map, translation_col_map, logs
        else:
            logs.append(f"{ws.title}: no usable columns found; skipped")

    return wb, segments, cell_map, translation_col_map, logs


def extract_csv_segments(uploaded_file, source_hint: str, target_hint: str, mode: str, max_segments: int, deep_scan: bool):
    df = pd.read_csv(uploaded_file)
    headers = list(df.columns)
    src_idx, tgt_idx = detect_source_target_columns(headers, source_hint, target_hint)
    segments = []
    logs = []

    if src_idx is not None and (tgt_idx is not None or mode == "pro"):
        src_col = df.columns[src_idx]
        tgt_col = df.columns[tgt_idx] if tgt_idx is not None else "AI Translation"
        if mode == "pro" and tgt_col not in df.columns:
            df[tgt_col] = ""
        logs.append(f"CSV: column mode [{src_col}] -> [{tgt_col}]")
        for idx, row in df.iterrows():
            source = normalize_text(row[src_col] if pd.notna(row[src_col]) else "")
            translation = normalize_text(row[tgt_col] if tgt_col in df.columns and pd.notna(row[tgt_col]) else "")
            if not source or len(source) < 2:
                continue
            if mode == "qa" and not translation:
                continue
            loc = f"Row {idx + 2}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "csv",
                "sheet": "CSV",
                "location": loc,
                "row": idx,
                "source": source,
                "translation": translation,
                "text": translation if mode == "qa" else source,
                "mode": "bilingual" if translation else "source_only",
                "target_column": tgt_col,
            })
            if reached_segment_limit(segments, max_segments):
                return df, segments, logs
    elif deep_scan:
        logs.append("CSV: deep-scan text cells")
        for col in df.columns:
            for idx, value in df[col].items():
                if pd.notna(value) and isinstance(value, str) and len(value.strip()) > 3:
                    segments.append({
                        "id": len(segments) + 1,
                        "file_type": "csv",
                        "sheet": "CSV",
                        "location": f"Row {idx + 2}, Col {col}",
                        "row": idx,
                        "source": "",
                        "translation": normalize_text(value),
                        "text": normalize_text(value),
                        "mode": "monolingual",
                    })
                    if reached_segment_limit(segments, max_segments):
                        return df, segments, logs
    else:
        logs.append("CSV: no usable columns found")

    return df, segments, logs


def extract_text_segments(uploaded_file, mode: str, max_segments: int):
    data = uploaded_file.getvalue()
    lower_name = uploaded_file.name.lower()

    # .xlz is often a compressed XLIFF package, not a plain text file.
    if lower_name.endswith(".xlz"):
        return extract_xlz_segments_from_zip(data, mode, max_segments)

    text_like_exts = (
        ".txt", ".srt", ".xml", ".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".json", ".po",
        ".properties", ".strings", ".html", ".htm", ".md", ".yml", ".yaml", ".csv"
    )
    if looks_like_binary(data) and not lower_name.endswith(text_like_exts):
        return "", [], [
            "Unsupported or binary file detected. ErrorSweep could not safely extract readable text. "
            "If this is an Excel workbook with a non-standard extension, rename it to .xlsx and retry."
        ]

    text, encoding_used = decode_text_bytes(data)

    # Basic XLIFF/XML/XLZ pair extraction. These formats should not be converted into
    # line-pair text output; they are treated as structured source/target pairs.
    if lower_name.endswith((".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".xml")):
        segments, xliff_logs = extract_xliff_pairs_from_xml_text(
            text,
            mode=mode,
            max_segments=max_segments,
            source_label=uploaded_file.name,
        )
        if segments:
            return text, segments, [f"{msg} (decoded as {encoding_used})" for msg in xliff_logs]

    raw_lines = text.splitlines(keepends=True)
    clean_lines = [clean_line_for_ai(line) for line in raw_lines]

    # Detect tab-separated bilingual pairs first.
    segments = []
    for line_index, clean in enumerate(clean_lines):
        if not clean or len(clean) <= 2:
            continue
        parts = clean.split("\t")
        if len(parts) >= 2 and len(parts[0].strip()) > 1 and len(parts[1].strip()) > 1:
            segments.append({
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {line_index + 1}",
                "line_index": line_index,
                "source": parts[0].strip(),
                "translation": parts[1].strip(),
                "text": parts[1].strip() if mode == "qa" else parts[0].strip(),
                "mode": "bilingual",
            })
            if reached_segment_limit(segments, max_segments):
                break

    non_empty_count = sum(1 for x in clean_lines if x.strip())
    if segments and len(segments) >= max(1, min(5, non_empty_count)):
        return text, segments, [f"Text: detected tab-separated source/translation pairs (decoded as {encoding_used})"]

    # Line-based text template mode. This preserves the user's line pattern.
    # Example:
    #   Source
    #   Target
    #   English source line
    #   [blank target line]
    # becomes:
    #   Source
    #   Target
    #   English source line
    #   Telugu translation
    segments = []
    non_empty_position = 0
    for line_index, clean in enumerate(clean_lines):
        if not clean:
            continue
        non_empty_position += 1
        if len(clean) <= 2:
            continue
        if should_skip_text_translation_line(clean, non_empty_position):
            continue

        if mode == "pro":
            seg = {
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {line_index + 1}",
                "line_index": line_index,
                "source": clean,
                "translation": "",
                "text": clean,
                "mode": "source_only",
            }
        else:
            seg = {
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {line_index + 1}",
                "line_index": line_index,
                "source": "",
                "translation": clean,
                "text": clean,
                "mode": "monolingual",
            }
        segments.append(seg)
        if reached_segment_limit(segments, max_segments):
            break

    return text, segments, [f"Text: pattern-preserving line mode (decoded as {encoding_used})"]


def extract_docx_segments(uploaded_file, mode: str, max_segments: int, source_hint: str = "", target_hint: str = ""):
    """Auto DOCX extractor: tables first, Source/Target template second, paragraph fallback third."""
    doc = Document(uploaded_file)
    segments: List[Dict[str, Any]] = []
    para_map: Dict[str, Dict[str, Any]] = {}
    logs: List[str] = []

    for table_idx, table in enumerate(doc.tables, start=1):
        header_idx, headers, src_idx, tgt_idx = find_docx_table_header(table, source_hint, target_hint, need_target=(mode == "qa"))
        if src_idx is None or (mode == "qa" and tgt_idx is None):
            continue
        src_name = headers[src_idx] if src_idx < len(headers) else "Source Text"
        tgt_name = headers[tgt_idx] if tgt_idx is not None and tgt_idx < len(headers) else "Original Translation"
        logs.append(f"DOCX table {table_idx}: column mode [{src_name}] -> [{tgt_name}]")

        for row_idx in range(header_idx + 1, len(table.rows)):
            row = table.rows[row_idx]
            if len(row.cells) <= src_idx:
                continue
            source_text = normalize_text(get_docx_cell_text(row.cells[src_idx]))
            if not is_valid_docx_source(source_text):
                continue
            translation_text = ""
            target_cell = None
            if tgt_idx is not None and len(row.cells) > tgt_idx:
                target_cell = row.cells[tgt_idx]
                translation_text = normalize_text(get_docx_cell_text(target_cell))
            if mode == "qa" and not translation_text:
                continue
            loc = f"Table {table_idx}, Row {row_idx + 1}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "docx",
                "sheet": f"Table {table_idx}",
                "location": loc,
                "row": row_idx + 1,
                "source": source_text,
                "translation": translation_text,
                "text": translation_text if mode == "qa" else source_text,
                "mode": "bilingual" if translation_text else "source_only",
                "source_header": src_name,
                "target_header": tgt_name,
            })
            if target_cell is not None:
                para_map[loc] = {"kind": "cell", "cell": target_cell}
            if reached_segment_limit(segments, max_segments):
                return doc, segments, para_map, logs

    if segments:
        return doc, segments, para_map, logs

    paras = list(doc.paragraphs)
    clean_paras = [normalize_text(p.text) for p in paras]
    nonempty = [x for x in clean_paras if x]
    if len(nonempty) >= 2 and nonempty[0].lower() in {"source", "source text"} and nonempty[1].lower() in {"target", "translation", "original translation"}:
        logs.append("DOCX: Source/Target paragraph-template mode")
        for i, p in enumerate(paras):
            text = normalize_text(p.text)
            if not is_valid_docx_source(text):
                continue
            if text.lower() in {"source", "source text", "target", "translation", "original translation"}:
                continue
            loc = f"Paragraph {i + 1}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "docx",
                "sheet": "Document",
                "location": loc,
                "source": text if mode == "pro" else "",
                "translation": "" if mode == "pro" else text,
                "text": text,
                "mode": "source_only" if mode == "pro" else "monolingual",
            })
            para_map[loc] = {"kind": "paragraph_append", "paragraph": p}
            if reached_segment_limit(segments, max_segments):
                break
        return doc, segments, para_map, logs

    logs.append("DOCX: paragraph fallback mode")
    for i, p in enumerate(paras, start=1):
        text = normalize_text(p.text)
        if is_valid_docx_source(text):
            seg = {
                "id": len(segments) + 1,
                "file_type": "docx",
                "sheet": "Document",
                "location": f"Paragraph {i}",
                "source": text if mode == "pro" else "",
                "translation": text if mode == "qa" else "",
                "text": text,
                "mode": "source_only" if mode == "pro" else "monolingual",
            }
            segments.append(seg)
            para_map[seg["location"]] = {"kind": "paragraph_append", "paragraph": p}
            if reached_segment_limit(segments, max_segments):
                break
    return doc, segments, para_map, logs


def write_docx_translation_target(target_info: Any, translation: str) -> None:
    if target_info is None:
        return
    if hasattr(target_info, "add_run"):
        target_info.add_run("\n" + translation)
        return
    kind = target_info.get("kind") if isinstance(target_info, dict) else None
    if kind == "cell":
        set_docx_cell_text(target_info["cell"], translation)
    elif kind == "paragraph":
        set_docx_paragraph_text(target_info["paragraph"], translation)
    elif kind == "paragraph_append":
        target_info["paragraph"].add_run("\n" + translation)


# ==========================================================
# DETERMINISTIC QA CHECKS
# ==========================================================

def extract_placeholders(text: str) -> List[str]:
    return PLACEHOLDER_PATTERN.findall(text or "")


def extract_numbers(text: str) -> List[str]:
    return NUMBER_PATTERN.findall(text or "")


def make_report_row(
    segment: Dict[str, Any],
    error_type: str,
    severity: str,
    wrong_part: str,
    suggestion: str,
    explanation: str,
    source_kind: str,
    rule_source: str = "",
    confidence: str = "High",
) -> Dict[str, Any]:
    return {
        "Sheet": segment.get("sheet", ""),
        "Location": segment.get("location", ""),
        "Mode": segment.get("mode", ""),
        "Source Text": truncate(segment.get("source", ""), 400),
        "Translation": truncate(segment.get("translation", segment.get("text", "")), 400),
        "Error Type": error_type,
        "Severity": severity,
        "Wrong Part": truncate(wrong_part, 300),
        "Suggestion": truncate(suggestion, 400),
        "Explanation": explanation,
        "Check Source": source_kind,
        "Rule Source": rule_source,
        "Confidence": confidence,
    }




def _previous_non_space_index(text: str, index: int) -> Optional[int]:
    for j in range(index - 1, -1, -1):
        if not text[j].isspace():
            return j
    return None


def _next_non_space_index(text: str, index: int) -> Optional[int]:
    for j in range(index + 1, len(text)):
        if not text[j].isspace():
            return j
    return None


def _is_measurement_quote(text: str, index: int) -> bool:
    """Treat inch/foot marks as measurements, not quotation marks.

    Examples that must NOT be flagged:
        0.1" Thick Shim
        2.31" Outer Diameter Button Plug
        1/2" Thread Adapter
        13/16"-16 Straight Adapter

    Localization files often use the straight double quote (") as an inch mark.
    A simple odd quote-count rule creates thousands of false positives for these.
    """
    prev_idx = _previous_non_space_index(text, index)
    if prev_idx is None:
        return False

    prev_char = text[prev_idx]
    if prev_char.isdigit():
        return True

    # Cases like 1⁄2" or 1/2" are already covered because previous char is digit,
    # but keep this for unicode fraction symbols such as ½".
    if prev_char in "¼½¾⅛⅜⅝⅞":
        return True

    return False


def _is_contraction_or_apostrophe(text: str, index: int) -> bool:
    """Ignore apostrophes inside words, e.g. Let's, don't, user’s."""
    prev_idx = _previous_non_space_index(text, index)
    next_idx = _next_non_space_index(text, index)
    if prev_idx is None or next_idx is None:
        return False
    return text[prev_idx].isalpha() and text[next_idx].isalpha()


def _real_quote_counts(text: str) -> Dict[str, int]:
    """Count only real quotation marks, excluding measurements and apostrophes."""
    text = text or ""
    double_quotes = {'"', '“', '”', '„', '«', '»'}
    single_quotes = {"'", '‘', '’', '‚'}
    counts = {"double": 0, "single": 0}

    for i, ch in enumerate(text):
        if ch in double_quotes:
            if _is_measurement_quote(text, i):
                continue
            counts["double"] += 1
        elif ch in single_quotes:
            if _is_measurement_quote(text, i) or _is_contraction_or_apostrophe(text, i):
                continue
            counts["single"] += 1
    return counts


def suggest_balanced_quotes(text: str, source_text: str = "") -> str:
    """Return a safer quote-balanced suggestion, or empty string if no clear fix is available.

    This function is intentionally conservative:
    - It ignores inch/foot measurements like 0.1" and 1/2".
    - It ignores apostrophes in words like don't / Let's.
    - If the target follows the source quote pattern, it does not flag.
    """
    t = text.strip()
    s = (source_text or "").strip()
    if not t:
        return ""

    target_counts = _real_quote_counts(t)
    source_counts = _real_quote_counts(s)

    # If target has no real quote imbalance, no issue.
    target_double_odd = target_counts["double"] % 2 != 0
    target_single_odd = target_counts["single"] % 2 != 0
    if not target_double_odd and not target_single_odd:
        return ""

    # If the source has the same real-quote count, the target is following source pattern.
    # This avoids false positives where the source intentionally contains one symbol.
    if source_counts == target_counts:
        return ""

    # Mixed smart/straight pairs.
    if t.startswith("“") and t.endswith('"'):
        return t[:-1] + "”"
    if t.startswith('"') and t.endswith("”"):
        return '“' + t[1:]
    if t.startswith("‘") and t.endswith("'"):
        return t[:-1] + "’"
    if t.startswith("'") and t.endswith("’"):
        return "‘" + t[1:]

    # Add a closing quote only for real quote imbalance.
    if target_double_odd and source_counts["double"] != target_counts["double"]:
        # Prefer smart closing quote if the text starts with a smart opening quote.
        if "“" in t and "”" not in t:
            return t + "”"
        return t + '"'

    if target_single_odd and source_counts["single"] != target_counts["single"]:
        if "‘" in t and "’" not in t:
            return t + "’"
        return t + "'"

    return ""

def has_latin_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text or ""))


def is_low_value_ai_style_issue(row: Dict[str, Any], include_style: bool) -> bool:
    """Drop subjective AI suggestions that look like preference, not true QA errors."""
    if row.get("Check Source") != "AI QA":
        return False

    if str(row.get("Error Type", "")).lower() == "api warning":
        return False

    error_type = str(row.get("Error Type", "")).strip().lower()
    explanation = str(row.get("Explanation", "")).strip().lower()
    wrong = str(row.get("Wrong Part", "")).strip()
    suggestion = str(row.get("Suggestion", "")).strip()
    translation = str(row.get("Translation", "")).strip()
    rule_source = str(row.get("Rule Source", "")).strip().lower()

    if not suggestion:
        return True
    if suggestion == wrong or suggestion == translation:
        return True

    subjective_types = {
        "style", "style & tone", "readability", "fluency", "fluency/readability",
        "terminology", "ai qa"
    }
    if not include_style and error_type in subjective_types and rule_source in {"", "ai"}:
        return True

    subjective_phrases = [
        "more natural", "available", "preferred", "prefer", "better", "alternative",
        "context", "style", "tone", "readability", "fluent", "idiomatic",
        "could be", "would be", "native speakers", "telugu equivalent"
    ]
    if not include_style and rule_source in {"", "ai"} and any(p in explanation for p in subjective_phrases):
        if not (has_latin_letters(wrong) and wrong in translation):
            return True

    objective_types = {"grammar", "spelling", "mixed script", "mixed language"}
    if error_type in objective_types and wrong and wrong not in translation:
        return True

    return False


def post_filter_report_rows(rows: List[Dict[str, Any]], include_style: bool) -> Tuple[List[Dict[str, Any]], int]:
    filtered = []
    dropped = 0
    seen = set()
    for row in rows:
        if is_low_value_ai_style_issue(row, include_style):
            dropped += 1
            continue
        key = (
            row.get("Sheet", ""), row.get("Location", ""), row.get("Error Type", ""),
            row.get("Wrong Part", ""), row.get("Suggestion", "")
        )
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        filtered.append(row)
    return filtered, dropped



# ==========================================================
# SOURCE-DRIVEN FORMAT QA HELPERS
# ==========================================================

TERMINAL_PUNCT_CLASSES = {
    "period": {".", "。", "．", "｡", "।", "॥"},
    "question": {"?", "？", "¿"},
    "exclamation": {"!", "！", "¡"},
    "colon": {":", "："},
    "semicolon": {";", "；"},
    "ellipsis": {"…"},
}

CLOSING_WRAPPERS = set(')]}›»”’"\'')
OPENING_WRAPPERS = set('([{‹«“‘"\'')
BRACKET_PAIRS = [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">")]


def _trim_for_terminal(text: str) -> str:
    """Remove trailing spaces and closing quotes/brackets for terminal punctuation checks.

    Example: source ends with ." or .] should still be treated as ending with a period.
    Measurement inch marks are handled separately by _is_measurement_quote.
    """
    t = normalize_text(text).strip()
    while t and t[-1] in CLOSING_WRAPPERS:
        # Do not strip an inch mark after a number, e.g. 0.1"
        if t[-1] in {'"', '”'} and _is_measurement_quote(t, len(t) - 1):
            break
        t = t[:-1].rstrip()
    return t


def terminal_punctuation_class(text: str) -> str:
    """Return the terminal punctuation class, or empty string.

    This is source-driven: if source has no terminal punctuation, ErrorSweep does not demand one in target.
    """
    t = _trim_for_terminal(text)
    if not t:
        return ""
    if t.endswith("...") or t.endswith("…"):
        return "ellipsis"
    last = t[-1]
    for cls, chars in TERMINAL_PUNCT_CLASSES.items():
        if last in chars:
            return cls
    return ""


def has_script_range(text: str, start: str, end: str) -> bool:
    return any(start <= ch <= end for ch in text or "")


def preferred_terminal_for_target(source_cls: str, target_text: str) -> str:
    """Choose a reasonable localized equivalent for the target.

    Only used when source already has terminal punctuation.
    """
    if source_cls == "period":
        # Devanagari languages often use danda as sentence terminator.
        if has_script_range(target_text, "\u0900", "\u097F"):
            return "।"
        if has_script_range(target_text, "\u4E00", "\u9FFF"):
            return "。"
        return "."
    if source_cls == "question":
        return "?"
    if source_cls == "exclamation":
        return "!"
    if source_cls == "colon":
        return ":"
    if source_cls == "semicolon":
        return ";"
    if source_cls == "ellipsis":
        return "…"
    return ""


def replace_or_append_terminal(target: str, source_cls: str) -> str:
    """Suggest target with source-equivalent terminal punctuation.

    We append when target lacks terminal punctuation. If target has a different terminal class,
    we replace only the last terminal punctuation. We never use this when source has no terminal punctuation.
    """
    t = target.strip()
    preferred = preferred_terminal_for_target(source_cls, t)
    if not preferred:
        return t
    current_cls = terminal_punctuation_class(t)
    if not current_cls:
        return t + preferred
    # Replace last terminal punctuation after stripping closing wrappers is too complex to do perfectly,
    # so keep conservative: only append/replace if last visible char is a terminal mark.
    tt = _trim_for_terminal(t)
    if tt and terminal_punctuation_class(tt):
        idx = t.rfind(tt[-1])
        if idx >= 0:
            return t[:idx] + preferred + t[idx + 1:]
    return t + preferred


def leading_list_marker(text: str) -> Tuple[str, str]:
    """Return (marker_type, marker_text) for bullet/numbered-list starts.

    This is source-driven: target is only required to have a list marker when source has one.
    """
    t = normalize_text(text).lstrip()
    if not t:
        return "", ""
    m = re.match(r"^([•∙◦▪▫‣⁃])\s*", t)
    if m:
        return "bullet", m.group(1)
    m = re.match(r"^([\-*])\s+", t)
    if m:
        return "bullet", m.group(1)
    m = re.match(r"^(\d+[\.)])\s+", t)
    if m:
        return "numbered", m.group(1)
    m = re.match(r"^([A-Za-z][\.)])\s+", t)
    if m:
        return "lettered", m.group(1)
    return "", ""


def bracket_wrapper(text: str) -> Tuple[str, str]:
    """Detect if the whole source segment is wrapped in matching brackets.

    Example: [Welcome Screen] should normally remain bracketed in target.
    """
    t = normalize_text(text).strip()
    if len(t) < 2:
        return "", ""
    for left, right in BRACKET_PAIRS:
        if t.startswith(left) and t.endswith(right):
            return left, right
    return "", ""


def ensure_bracket_wrapper(target: str, left: str, right: str) -> str:
    t = normalize_text(target).strip()
    stripped = t.strip("".join([l + r for l, r in BRACKET_PAIRS]))
    return f"{left}{stripped}{right}"


def extract_urls(text: str) -> List[str]:
    return URL_PATTERN.findall(text or "")


def extract_emails(text: str) -> List[str]:
    return EMAIL_PATTERN.findall(text or "")


def source_driven_format_checks(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Conservative source-vs-target formatting checks.

    Golden rule: only enforce source formatting if the source actually has that formatting.
    If source has no ending period, ErrorSweep will not demand a period in target.
    """
    rows: List[Dict[str, Any]] = []
    source = normalize_text(segment.get("source", ""))
    target = normalize_text(segment.get("translation", "") or segment.get("text", ""))
    if not source or not target:
        return rows

    src_cls = terminal_punctuation_class(source)
    tgt_cls = terminal_punctuation_class(target)
    if src_cls and tgt_cls != src_cls:
        suggestion = replace_or_append_terminal(target, src_cls)
        rows.append(make_report_row(
            segment,
            "Punctuation",
            "Minor",
            "missing or different ending punctuation",
            visible_invisibles(suggestion),
            f"Source ends with {src_cls} punctuation; target should preserve an equivalent. If source has no ending punctuation, this rule does not run.",
            "Rule Engine",
            "Source-driven format rules",
            "High",
        ))

    src_marker_type, src_marker = leading_list_marker(source)
    tgt_marker_type, _ = leading_list_marker(target)
    if src_marker_type and tgt_marker_type != src_marker_type:
        rows.append(make_report_row(
            segment,
            "Formatting",
            "Minor",
            f"missing {src_marker_type} list marker",
            src_marker + " " + target.lstrip(),
            "Source begins with a list/bullet marker, but target does not preserve an equivalent marker.",
            "Rule Engine",
            "Source-driven format rules",
            "High",
        ))

    left, right = bracket_wrapper(source)
    if left and right and not (target.strip().startswith(left) and target.strip().endswith(right)):
        rows.append(make_report_row(
            segment,
            "Formatting",
            "Minor",
            f"missing wrapper {left}{right}",
            ensure_bracket_wrapper(target, left, right),
            "Source segment is wrapped in brackets; target should preserve the same wrapper unless client rules say otherwise.",
            "Rule Engine",
            "Source-driven format rules",
            "Medium",
        ))

    # Ellipsis only if source has ellipsis. Do not invent ellipsis when source does not have it.
    source_has_ellipsis = source.strip().endswith("...") or source.strip().endswith("…")
    target_has_ellipsis = target.strip().endswith("...") or target.strip().endswith("…")
    if source_has_ellipsis and not target_has_ellipsis:
        rows.append(make_report_row(
            segment,
            "Punctuation",
            "Minor",
            "missing ellipsis",
            target.strip() + "…",
            "Source ends with an ellipsis; target should preserve an equivalent ellipsis.",
            "Rule Engine",
            "Source-driven format rules",
            "High",
        ))

    # URLs/emails must be preserved exactly if present in source.
    src_urls = extract_urls(source)
    for url in src_urls:
        if url not in target:
            rows.append(make_report_row(
                segment, "URL", "Major", url, f"Keep URL unchanged: {url}",
                "URL from source is missing or changed in target.", "Rule Engine", "Source-driven format rules", "High"
            ))
    src_emails = extract_emails(source)
    for email in src_emails:
        if email not in target:
            rows.append(make_report_row(
                segment, "Email", "Major", email, f"Keep email unchanged: {email}",
                "Email address from source is missing or changed in target.", "Rule Engine", "Source-driven format rules", "High"
            ))

    return rows

def deterministic_checks(segment: Dict[str, Any], rules: Dict[str, Any], enable_zwnj: bool = True) -> List[Dict[str, Any]]:
    rows = []
    source = normalize_text(segment.get("source", ""))
    target = normalize_text(segment.get("translation", "") or segment.get("text", ""))

    if not target:
        return rows

    # Do not QA Excel formulas as translation text. They create false placeholder issues like $B, $C, $E.
    if target.lstrip().startswith("="):
        return rows

    # Extra spaces
    if re.search(r" {2,}", target):
        suggestion = re.sub(r" {2,}", " ", target)
        rows.append(make_report_row(
            segment, "Spacing", "Minor", visible_invisibles(target), visible_invisibles(suggestion),
            "Multiple consecutive spaces found.", "Rule Engine"
        ))

    if target != target.strip():
        rows.append(make_report_row(
            segment, "Spacing", "Minor", visible_invisibles(target), visible_invisibles(target.strip()),
            "Leading or trailing spaces found.", "Rule Engine"
        ))

    # Source-driven formatting rules.
    # Golden rule: only enforce punctuation/markers/wrappers when the source has them.
    # Example: if source does not end with a period, target is NOT required to end with a period.
    rows.extend(source_driven_format_checks(segment))

    # Placeholders/tags
    src_ph = extract_placeholders(source)
    tgt_ph = extract_placeholders(target)
    missing_ph = [p for p in src_ph if p not in tgt_ph]
    extra_ph = [p for p in tgt_ph if p not in src_ph]
    if missing_ph:
        rows.append(make_report_row(
            segment, "Placeholder", "Major", ", ".join(missing_ph), target,
            "Placeholder/tag from source is missing in translation.", "Rule Engine"
        ))
    if extra_ph:
        rows.append(make_report_row(
            segment, "Placeholder", "Major", ", ".join(extra_ph), target,
            "Translation contains placeholder/tag not found in source.", "Rule Engine"
        ))

    # Numbers
    src_nums = extract_numbers(source)
    tgt_nums = extract_numbers(target)
    missing_nums = [n for n in src_nums if n not in tgt_nums]
    if source and missing_nums:
        rows.append(make_report_row(
            segment, "Number", "Major", ", ".join(missing_nums), target,
            "Number from source is missing or changed in translation.", "Rule Engine"
        ))

    # Bracket balance and quotes
    bracket_pairs = [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">")]
    for left, right in bracket_pairs:
        if target.count(left) != target.count(right):
            rows.append(make_report_row(
                segment, "Formatting", "Minor", f"Unbalanced {left}{right}", target,
                "Unbalanced brackets detected in translation.", "Rule Engine"
            ))
            break

    quote_suggestion = suggest_balanced_quotes(target, source)
    if quote_suggestion:
        rows.append(make_report_row(
            segment, "Formatting", "Minor", "unbalanced quote marks", quote_suggestion,
            "Opening and closing quotation marks are inconsistent or unbalanced. Measurement inch/foot symbols are ignored and source quote pattern is respected.", "Rule Engine"
        ))

    # DNT terms
    for d in rules.get("dnt", [])[:500] if rules else []:
        term = normalize_text(d.get("term", ""))
        if term and (term.lower() in source.lower()) and (term not in target):
            rows.append(make_report_row(
                segment, "DNT", "Major", term, f"Keep '{term}' unchanged in translation.",
                "Do-not-translate term from company rules is missing or changed.", "Company Rules", d.get("source", ""), "High"
            ))

    # Glossary terms
    for g in rules.get("glossary", [])[:500] if rules else []:
        src_term = normalize_text(g.get("source_term", ""))
        tgt_term = normalize_text(g.get("target_term", ""))
        if src_term and tgt_term and src_term.lower() in source.lower() and tgt_term not in target:
            rows.append(make_report_row(
                segment, "Glossary", "Major", src_term, tgt_term,
                "Company glossary target term is missing in translation.", "Company Rules", g.get("source", ""), "High"
            ))

    # ZWNJ detection for Telugu loanword suffixes
    if enable_zwnj:
        for base, suffixes in TELUGU_ZWNJ_BASE_SUFFIXES.items():
            for suffix in suffixes:
                bad_joined = base + suffix
                bad_spaced = base + " " + suffix
                good = base + "\u200C" + suffix
                if bad_joined in target:
                    rows.append(make_report_row(
                        segment, "ZWNJ", "Minor", visible_invisibles(bad_joined), visible_invisibles(good),
                        "Possible missing Zero Width Non-Joiner between loanword/base and suffix.", "Rule Engine", "Built-in Telugu ZWNJ", "Medium"
                    ))
                if bad_spaced in target:
                    rows.append(make_report_row(
                        segment, "ZWNJ", "Minor", visible_invisibles(bad_spaced), visible_invisibles(good),
                        "Possible incorrect visible space where ZWNJ may be required.", "Rule Engine", "Built-in Telugu ZWNJ", "Medium"
                    ))

    return rows


# ==========================================================
# AI SERVICE CALLS
# ==========================================================

def openai_json(client: AI, model: str, instructions: str, prompt: str, max_output_tokens: int = 3000) -> List[Dict[str, Any]]:
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=prompt,
        max_output_tokens=max_output_tokens,
    )
    return extract_json_array(response.output_text)


def gemini_json(client, model: str, prompt: str) -> List[Dict[str, Any]]:
    response = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", "") or ""
    return extract_json_array(text)


def ai_qa_batch(
    client: AI,
    model: str,
    segments: List[Dict[str, Any]],
    rules: Dict[str, Any],
    domain: str,
    strictness: str,
    include_style: bool,
) -> List[Dict[str, Any]]:
    if not segments:
        return []

    numbered_parts = []
    for i, seg in enumerate(segments, start=1):
        relevant = retrieve_relevant_rules(seg, rules, 1200) if rules else ""
        numbered_parts.append(
            f"[Segment {i}]\n"
            f"Location: {seg.get('location','')}\n"
            f"Mode: {seg.get('mode','')}\n"
            f"Source: {seg.get('source','')}\n"
            f"Translation/Text: {seg.get('translation') or seg.get('text','')}\n"
            f"Relevant Company Rules:\n{relevant if relevant else '(none)'}"
        )

    if include_style:
        style_policy = (
            "Style and terminology suggestions are allowed, but only when they are clearly better, "
            "supported by context, and not merely a personal preference."
        )
    else:
        style_policy = (
            "Do NOT flag subjective style, wording, or terminology preferences unless a company rule, glossary, "
            "DNT list, placeholder rule, or clear source meaning proves it is wrong. "
            "Do NOT flag acceptable target-language loanwords/transliterations as errors merely because a native synonym exists. "
            "For Telugu UI localization, terms like వెల్కమ్ స్క్రీన్, స్క్రీన్, ఫైల్, యాప్, సెట్టింగ్, డాక్యుమెంట్, పాస్‌వర్డ్ can be acceptable unless company rules say otherwise."
        )

    instructions = (
        "You are ErrorSweep, a strict but conservative linguistic QA engine for localization. "
        "Your job is to find actual QA defects, not to rewrite acceptable translations. "
        "Return only valid JSON. No markdown. Do not invent issues."
    )

    prompt = f"""
Domain: {domain}
Strictness: {STRICTNESS_GUIDE[strictness]}
Style policy: {style_policy}

Review the following segments for real QA errors.

{chr(10).join(numbered_parts)}

Important rules:
- Output an error only when there is clear evidence in the source, translation, or company rules.
- Do not suggest a different phrase only because it sounds more natural.
- Do not change a valid translation into a different meaning.
- Source-driven formatting policy: preserve source formatting only when the source actually has that formatting.
- If the source does NOT end with a period/question/exclamation/colon/semicolon/ellipsis, do NOT demand that punctuation in the target.
- If the source has measurement inch/foot symbols like 0.1", 1/2", or 13/16", treat them as measurement marks, not quotation marks.
- Preserve placeholders, variables, HTML/XML tags, URLs, emails, numbers, and DNT terms exactly.
- Preserve list/bullet markers only when the source has a list/bullet marker.
- Preserve bracket wrappers like [Label] only when the source is bracket-wrapped.
- Do not flag transliterated UI/product terms in the target script unless company rules require another term.
- Mixed script is an error when Roman/Latin words appear inside target-language text unexpectedly, for example "chupinchandi" in Telugu output.
- If the issue is grammar/spelling/mixed script, "wrong_part" must be an exact visible fragment from the translation.
- "suggestion" must be a concrete correction. Prefer a full corrected translation when possible.
- If you are unsure, omit the error.

Check only these categories:
- Accuracy: source meaning changed, omitted, or added.
- Grammar: real grammar mistake in target language.
- Spelling: real spelling or typo issue.
- Mixed Script: unexpected Latin/Roman script in target-language text.
- Formatting: issue not already covered by deterministic rules.
- Client Rule: clear violation of uploaded company rules.
- Terminology: only if supported by glossary/DNT/client rule or clearly wrong for the domain.

Return ONLY this JSON array:
[
  {{
    "location": "exact location from input",
    "language_detected": "detected language or Unknown",
    "error_type": "Accuracy|Grammar|Spelling|Mixed Script|Terminology|Formatting|Client Rule",
    "severity": "Minor|Major|Critical",
    "wrong_part": "exact wrong fragment from translation, or concise description for Accuracy only",
    "suggestion": "corrected target text or exact replacement",
    "explanation": "brief evidence-based reason",
    "rule_source": "company rule source if used, else AI",
    "confidence": "High|Medium|Low"
  }}
]

Only include real errors. If no errors are found, return [].
"""

    try:
        raw = openai_json(client, model, instructions, prompt, max_output_tokens=3500)
    except Exception as e:
        return [{
            "location": "API",
            "language_detected": "Unknown",
            "error_type": "API Warning",
            "severity": "Review",
            "wrong_part": "AI service call failed",
            "suggestion": "Retry with fewer segments or check API key/settings.",
            "explanation": str(e)[:250],
            "rule_source": "System",
            "confidence": "Low",
        }]

    rows = []
    loc_to_seg = {s.get("location", ""): s for s in segments}
    allowed_types = {"Accuracy", "Grammar", "Spelling", "Mixed Script", "Terminology", "Formatting", "Client Rule", "API Warning"}
    for err in raw:
        loc = err.get("location", "")
        seg = loc_to_seg.get(loc, {})
        error_type = err.get("error_type", "AI QA")
        if error_type not in allowed_types:
            error_type = "AI QA"
        rows.append(make_report_row(
            seg,
            error_type,
            err.get("severity", "Review"),
            err.get("wrong_part", ""),
            err.get("suggestion", ""),
            err.get("explanation", ""),
            "AI QA",
            err.get("rule_source", "AI"),
            err.get("confidence", "Medium"),
        ))
    return rows


def openai_translate_batch(
    client: AI,
    model: str,
    segments: List[Dict[str, Any]],
    target_language: str,
    domain: str,
    rules: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not segments:
        return []
    parts = []
    for i, seg in enumerate(segments, start=1):
        relevant = retrieve_relevant_rules(seg, rules, 1200) if rules else ""
        parts.append(
            f"[Segment {i}]\n"
            f"Location: {seg.get('location','')}\n"
            f"Source: {seg.get('source') or seg.get('text','')}\n"
            f"Relevant Company Rules:\n{relevant if relevant else '(none)'}"
        )

    instructions = (
        "You are a professional localization translator. "
        "Return only valid JSON. Preserve placeholders, numbers, tags, punctuation intent, and product terms."
    )
    prompt = f"""
Translate these segments into {target_language}.
Domain: {domain}

Use company rules if provided. Keep DNT terms unchanged. Follow glossary terms.

{chr(10).join(parts)}

Return ONLY JSON:
[
  {{
    "location": "exact location from input",
    "translation": "translated text"
  }}
]
"""
    try:
        return openai_json(client, model, instructions, prompt, max_output_tokens=4000)
    except Exception as e:
        return [{"location": "API", "translation": "", "error": str(e)}]


def gemini_review_translations(
    client,
    model: str,
    translated_segments: List[Dict[str, Any]],
    target_language: str,
    domain: str,
    rules: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not translated_segments:
        return []
    parts = []
    for i, seg in enumerate(translated_segments, start=1):
        relevant = retrieve_relevant_rules(seg, rules, 1000) if rules else ""
        parts.append(
            f"[Segment {i}]\n"
            f"Location: {seg.get('location','')}\n"
            f"Source: {seg.get('source','')}\n"
            f"Translation: {seg.get('translation','')}\n"
            f"Relevant Rules:\n{relevant if relevant else '(none)'}"
        )

    prompt = f"""
You are an independent translation reviewer.
Review AI translations into {target_language}.
Domain: {domain}

Check accuracy, grammar, terminology, DNT, glossary, placeholders, numbers, punctuation, ZWNJ, style, and formatting.

{chr(10).join(parts)}

Return ONLY valid JSON:
[
  {{
    "location": "exact location from input",
    "error_type": "Accuracy|Grammar|Terminology|Formatting|ZWNJ|Style|Placeholder|Number|DNT|Glossary",
    "severity": "Minor|Major|Critical",
    "wrong_part": "wrong part in translation",
    "suggestion": "reviewer corrected translation or fix",
    "explanation": "brief reason",
    "confidence": "High|Medium|Low"
  }}
]
If no issues, return [].
"""
    try:
        return gemini_json(client, model, prompt)
    except Exception as e:
        return [{
            "location": "API",
            "error_type": "Review Service Warning",
            "severity": "Review",
            "wrong_part": "Independent review failed",
            "suggestion": "Retry with fewer segments or contact the administrator.",
            "explanation": str(e)[:250],
            "confidence": "Low",
        }]


# ==========================================================
# SEGMENT COVERAGE / FULL-FILE STATUS REPORT
# ==========================================================

def highest_severity(rows: List[Dict[str, Any]]) -> str:
    order = {"Critical": 4, "Major": 3, "Minor": 2, "Review": 1, "Pass": 0}
    if not rows:
        return "Pass"
    return max((str(r.get("Severity", "Review")) for r in rows), key=lambda x: order.get(x, 1))


def build_segment_status_rows(segments: List[Dict[str, Any]], issue_rows: List[Dict[str, Any]], checked_by: str = "Rules + AI") -> List[Dict[str, Any]]:
    """Build one status row for every extracted segment so users can see full-file coverage."""
    issues_by_loc: Dict[str, List[Dict[str, Any]]] = {}
    for row in issue_rows:
        loc = str(row.get("Location", ""))
        if loc:
            issues_by_loc.setdefault(loc, []).append(row)

    status_rows: List[Dict[str, Any]] = []
    for seg in segments:
        loc = str(seg.get("location", ""))
        rows = issues_by_loc.get(loc, [])
        issue_count = len(rows)
        status = "Needs Review" if issue_count else "Pass"
        severity = highest_severity(rows)
        error_types = "; ".join(sorted({str(r.get("Error Type", "")) for r in rows if r.get("Error Type")}))
        suggestions = " | ".join(dict.fromkeys(str(r.get("Suggestion", "")) for r in rows if str(r.get("Suggestion", "")).strip()))
        explanations = " | ".join(dict.fromkeys(str(r.get("Explanation", "")) for r in rows if str(r.get("Explanation", "")).strip()))

        status_rows.append({
            "Sheet": seg.get("sheet", ""),
            "Location": loc,
            "Mode": seg.get("mode", ""),
            "Source Text": truncate(seg.get("source", ""), 500),
            "Translation": truncate(seg.get("translation", seg.get("text", "")), 500),
            "Review Status": status,
            "Issue Count": issue_count,
            "Highest Severity": severity,
            "Error Types": error_types,
            "Suggestion Summary": truncate(suggestions, 800) if suggestions else "No change suggested",
            "Explanation Summary": truncate(explanations, 800) if explanations else "Checked; no issue found",
            "Checked By": checked_by,
        })
    return status_rows


def merge_issue_and_status_csv(issue_rows: List[Dict[str, Any]], status_rows: List[Dict[str, Any]]) -> bytes:
    """For non-Excel files, return one CSV that includes all checked segments and issue details."""
    status_df = pd.DataFrame(status_rows)
    issue_df = pd.DataFrame(issue_rows)
    output = io.StringIO()
    output.write("ALL SEGMENT REVIEW\n")
    status_df.to_csv(output, index=False)
    output.write("\nISSUE DETAILS\n")
    issue_df.to_csv(output, index=False)
    return output.getvalue().encode("utf-8-sig")


# ==========================================================
# OUTPUT BUILDERS
# ==========================================================

def safe_report_cell_value(value: Any) -> Any:
    """Write report text safely. If a value starts with =/+/-/@, Excel may treat it as a formula."""
    if value is None:
        return ""
    if isinstance(value, str):
        if value.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    return value


def add_report_sheet_to_workbook(wb, sheet_name: str, report_rows: List[Dict[str, Any]], headers: List[str]):
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)
    ws.append(headers)
    for row in report_rows:
        ws.append([safe_report_cell_value(row.get(h, "")) for h in headers])
    style_header(ws)
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col[:100]:
            val = str(cell.value or "")
            max_len = max(max_len, min(len(val), 60))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[col_letter].width = max(12, min(max_len + 2, 60))

def highlight_excel_cells(cell_map: Dict[str, Any], report_rows: List[Dict[str, Any]]):
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in report_rows:
        loc = row.get("Location", "")
        grouped.setdefault(loc, []).append(row)

    for loc, rows in grouped.items():
        cell = cell_map.get(loc)
        if cell is None:
            continue
        cell.fill = HIGHLIGHT_FILL
        notes = []
        for r in rows[:8]:
            notes.append(
                f"[{r.get('Severity','')}] {r.get('Error Type','')}\n"
                f"Issue: {r.get('Wrong Part','')}\n"
                f"Suggestion: {r.get('Suggestion','')}\n"
                f"Why: {r.get('Explanation','')}"
            )
        cell.comment = Comment("\n\n".join(notes), "ErrorSweep")


def report_csv_bytes(report_rows: List[Dict[str, Any]]) -> bytes:
    return pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8-sig")


def dataframe_to_xlsx_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    """Create an Excel workbook from multiple DataFrames."""
    wb = Workbook()
    # Remove default sheet after creating our own sheets.
    default = wb.active
    wb.remove(default)

    for sheet_name, df in sheets.items():
        safe_name = str(sheet_name)[:31] or "Sheet"
        ws = wb.create_sheet(safe_name)
        if df is None or df.empty:
            ws.append(["Status"])
            ws.append(["No rows available"])
        else:
            ws.append([str(c) for c in df.columns])
            for _, row in df.iterrows():
                ws.append([safe_report_cell_value(row.get(c, "")) for c in df.columns])
        style_header(ws)
        for col in ws.columns:
            col_letter = col[0].column_letter
            max_len = 12
            for cell in col[:200]:
                val = str(cell.value or "")
                max_len = max(max_len, min(len(val) + 2, 70))
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.column_dimensions[col_letter].width = max_len

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def build_excel_report_bytes(
    issue_rows: List[Dict[str, Any]],
    status_rows: List[Dict[str, Any]],
    extraction_logs: Optional[List[str]] = None,
    translation_rows: Optional[List[Dict[str, Any]]] = None,
    title: str = "ErrorSweep Report",
) -> bytes:
    """Always return an Excel report, regardless of input file format."""
    extraction_logs = extraction_logs or []
    sheets: Dict[str, pd.DataFrame] = {}
    sheets["Summary"] = pd.DataFrame([
        {"Metric": "Report", "Value": title},
        {"Metric": "Segments checked", "Value": len(status_rows)},
        {"Metric": "Issues found", "Value": len(issue_rows)},
        {"Metric": "Generated at", "Value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
    ])
    sheets["All Segment Review"] = pd.DataFrame(status_rows)
    sheets["Issue Details"] = pd.DataFrame(issue_rows)
    if translation_rows is not None:
        sheets["Translations"] = pd.DataFrame(translation_rows)
    sheets["Extraction Log"] = pd.DataFrame([{"Log": x} for x in extraction_logs] or [{"Log": "No extraction log."}])
    return dataframe_to_xlsx_bytes(sheets)


def extract_pdf_segments(uploaded_file, mode: str, max_segments: int):
    """Extract readable lines from PDFs. Output/report is Excel; source PDF is not rewritten."""
    logs = []
    if PdfReader is None:
        return [], ["PDF support package is unavailable. Add pypdf to requirements.txt."]
    try:
        reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
        lines = []
        for page_index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            for line_no, line in enumerate(text.splitlines(), start=1):
                clean = clean_line_for_ai(line)
                if clean and len(clean) > 2:
                    lines.append((page_index, line_no, clean))
        segments = []
        for page_index, line_no, clean in limit_sequence(lines, max_segments):
            loc = f"Page {page_index}, Line {line_no}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "pdf",
                "sheet": "PDF",
                "location": loc,
                "source": clean if mode == "pro" else "",
                "translation": clean if mode == "qa" else "",
                "text": clean,
                "mode": "source_only" if mode == "pro" else "monolingual",
            })
        logs.append(f"PDF: extracted {len(segments)} text segment(s).")
        if not segments:
            logs.append("PDF appears image-based or has no extractable text. OCR is not enabled in this MVP.")
        return segments, logs
    except Exception as exc:
        return [], [f"Could not read PDF: {exc}"]




# ==========================================================
# SAME-FORMAT PRO TRANSLATION BUILDERS
# ==========================================================

def extract_json_pro_segments(uploaded_file, max_segments: int):
    """Extract string values from JSON and keep paths so translated output remains JSON."""
    data = uploaded_file.getvalue()
    raw_text, encoding_used = decode_text_bytes(data)
    logs = [f"JSON: decoded as {encoding_used}"]
    try:
        obj = json.loads(raw_text)
    except Exception as exc:
        # Fallback: treat as text-like if JSON cannot be parsed.
        logs.append(f"JSON parse failed; falling back to text mode: {exc}")
        text_original, segments, text_logs = extract_text_segments(uploaded_file, "pro", max_segments)
        return obj if False else None, segments, {}, logs + text_logs

    segments: List[Dict[str, Any]] = []
    path_map: Dict[str, List[Any]] = {}

    def walk(node: Any, path: List[Any]) -> None:
        if reached_segment_limit(segments, max_segments):
            return
        if isinstance(node, dict):
            for k, v in node.items():
                # Avoid translating keys; only translate string values.
                walk(v, path + [k])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [i])
        elif isinstance(node, str):
            clean = clean_line_for_ai(node)
            if clean and len(clean) > 1:
                loc = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in path)
                seg = {
                    "id": len(segments) + 1,
                    "file_type": "json",
                    "sheet": "JSON",
                    "location": loc,
                    "source": clean,
                    "translation": "",
                    "text": clean,
                    "mode": "source_only",
                }
                segments.append(seg)
                path_map[loc] = path

    walk(obj, [])
    logs.append(f"JSON: extracted {len(segments)} string value segment(s).")
    return obj, segments, path_map, logs


def set_json_path(obj: Any, path: List[Any], value: str) -> None:
    cur = obj
    for p in path[:-1]:
        cur = cur[p]
    if path:
        cur[path[-1]] = value


def build_translated_json_bytes(obj: Any, path_map: Dict[str, List[Any]], translations_by_loc: Dict[str, str]) -> bytes:
    for loc, path in path_map.items():
        trans = translations_by_loc.get(loc, "")
        if trans:
            set_json_path(obj, path, trans)
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


def extract_srt_pro_segments(uploaded_file, max_segments: int):
    """Extract subtitle text lines while preserving SRT cue numbers and timecodes."""
    raw_text, encoding_used = decode_text_bytes(uploaded_file.getvalue())
    lines = raw_text.splitlines()
    segments: List[Dict[str, Any]] = []
    line_map: Dict[str, List[int]] = {}
    i = 0
    cue_number = 0
    timestamp_re = re.compile(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}")
    while i < len(lines):
        # Optional cue index
        if not lines[i].strip():
            i += 1
            continue
        if i + 1 < len(lines) and timestamp_re.search(lines[i + 1]):
            cue_number += 1
            time_idx = i + 1
            text_start = i + 2
        elif timestamp_re.search(lines[i]):
            cue_number += 1
            time_idx = i
            text_start = i + 1
        else:
            i += 1
            continue
        text_indices = []
        j = text_start
        while j < len(lines) and lines[j].strip():
            text_indices.append(j)
            j += 1
        cue_text = "\n".join(lines[idx] for idx in text_indices).strip()
        if cue_text and len(cue_text) > 1:
            loc = f"Cue {cue_number}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "srt",
                "sheet": "SRT",
                "location": loc,
                "source": cue_text,
                "translation": "",
                "text": cue_text,
                "mode": "source_only",
            })
            line_map[loc] = text_indices
            if reached_segment_limit(segments, max_segments):
                break
        i = max(j + 1, i + 1)
    return raw_text, segments, line_map, [f"SRT: extracted {len(segments)} cue segment(s) (decoded as {encoding_used})."]


def build_translated_srt_bytes(raw_text: str, line_map: Dict[str, List[int]], translations_by_loc: Dict[str, str]) -> bytes:
    lines = raw_text.splitlines()
    for loc, indices in line_map.items():
        trans = translations_by_loc.get(loc, "")
        if not trans or not indices:
            continue
        trans_lines = trans.splitlines() or [trans]
        # Replace first original subtitle text line with full translation, blank the rest.
        lines[indices[0]] = trans_lines[0]
        insert_extra = trans_lines[1:]
        for idx in indices[1:]:
            lines[idx] = ""
        if insert_extra:
            # Insert extra translation lines immediately after first text line.
            first = indices[0]
            lines = lines[:first + 1] + insert_extra + lines[first + 1:]
    return ("\n".join(lines) + "\n").encode("utf-8-sig")


def xml_local_name(tag: str) -> str:
    return str(tag).split("}")[-1].lower()


def make_xml_target_tag(source_tag: str) -> str:
    if "}" in source_tag:
        ns = source_tag.split("}")[0].strip("{")
        return "{" + ns + "}target"
    return "target"


def extract_xml_xliff_pro_segments(uploaded_file, max_segments: int):
    """Extract XLIFF/XML/XLZ <source>/<target> pairs and preserve XML output."""
    import xml.etree.ElementTree as ET
    raw_text, encoding_used = decode_text_bytes(uploaded_file.getvalue())
    logs = [f"XML/XLIFF: decoded as {encoding_used}"]
    try:
        tree = ET.ElementTree(ET.fromstring(raw_text))
    except Exception as exc:
        logs.append(f"XML parse failed; falling back to text mode: {exc}")
        text_original, segments, text_logs = extract_text_segments(uploaded_file, "pro", max_segments)
        return None, segments, {}, logs + text_logs

    root = tree.getroot()
    segments: List[Dict[str, Any]] = []
    target_map: Dict[str, Any] = {}

    for parent in root.iter():
        children = list(parent)
        if not children:
            continue
        src_el = None
        tgt_el = None
        for child in children:
            lname = xml_local_name(child.tag)
            if lname == "source" and src_el is None:
                src_el = child
            elif lname == "target" and tgt_el is None:
                tgt_el = child
        if src_el is None:
            continue
        src_text = clean_line_for_ai("".join(src_el.itertext()))
        if not src_text:
            continue
        if tgt_el is None:
            tgt_el = ET.Element(make_xml_target_tag(src_el.tag))
            try:
                insert_at = children.index(src_el) + 1
                parent.insert(insert_at, tgt_el)
            except Exception:
                parent.append(tgt_el)
        loc = f"XML Segment {len(segments) + 1}"
        segments.append({
            "id": len(segments) + 1,
            "file_type": "xml",
            "sheet": "XML",
            "location": loc,
            "source": src_text,
            "translation": clean_line_for_ai("".join(tgt_el.itertext())) if tgt_el is not None else "",
            "text": src_text,
            "mode": "source_only",
        })
        target_map[loc] = tgt_el
        if reached_segment_limit(segments, max_segments):
            break
    logs.append(f"XML/XLIFF: extracted {len(segments)} source/target segment(s).")
    return tree, segments, target_map, logs


def build_translated_xml_bytes(tree: Any, target_map: Dict[str, Any], translations_by_loc: Dict[str, str]) -> bytes:
    for loc, target_el in target_map.items():
        trans = translations_by_loc.get(loc, "")
        if trans:
            # Replace text content while preserving attributes and tag.
            target_el.text = trans
    output = io.BytesIO()
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()




def extract_xliff_pairs_from_xml_text(raw_text: str, mode: str, max_segments: int, source_label: str = "File") -> Tuple[List[Dict[str, Any]], List[str]]:
    """Extract source/target pairs from XLIFF/XML/XLZ text.

    This works for plain .xliff/.xlf/.xml files and for .xlz packages after the
    XLIFF file is extracted from the ZIP. It supports namespaces and common
    XLIFF structures where <source> and <target> are siblings.
    """
    import xml.etree.ElementTree as ET
    logs: List[str] = []
    segments: List[Dict[str, Any]] = []

    try:
        root = ET.fromstring(raw_text)
    except Exception as exc:
        return [], [f"{source_label}: XML/XLIFF parse failed: {exc}"]

    for parent in root.iter():
        children = list(parent)
        if not children:
            continue

        src_el = None
        tgt_el = None
        for child in children:
            lname = xml_local_name(child.tag)
            if lname == "source" and src_el is None:
                src_el = child
            elif lname == "target" and tgt_el is None:
                tgt_el = child

        if src_el is None:
            continue

        src_text = clean_line_for_ai("".join(src_el.itertext()))
        tgt_text = clean_line_for_ai("".join(tgt_el.itertext())) if tgt_el is not None else ""

        if not src_text:
            continue
        if mode == "qa" and not tgt_text:
            continue

        loc = f"{source_label} Segment {len(segments) + 1}"
        segments.append({
            "id": len(segments) + 1,
            "file_type": "xliff",
            "sheet": source_label,
            "location": loc,
            "source": src_text,
            "translation": tgt_text,
            "text": tgt_text if mode == "qa" else src_text,
            "mode": "bilingual" if tgt_text else "source_only",
        })

        if reached_segment_limit(segments, max_segments):
            break

    logs.append(f"{source_label}: extracted {len(segments)} source/target segment(s).")
    return segments, logs


def extract_xlz_segments_from_zip(data: bytes, mode: str, max_segments: int) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    """Extract XLIFF/XML/XLZ segments from compressed .xlz / zipped localization packages.

    Many CAT/TMS systems export .xlz as a ZIP package that contains .xlf/.xliff
    files. Treating .xlz as latin-1 text produces fake binary segments; this
    function opens the ZIP and extracts the actual XLIFF/XML/XLZ content safely.
    """
    logs: List[str] = []
    all_segments: List[Dict[str, Any]] = []

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            candidate_names = [
                n for n in zf.namelist()
                if n.lower().endswith((".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".xml"))
                and not n.startswith("__MACOSX/")
            ]

            if not candidate_names:
                logs.append("XLZ package opened, but no .xlf/.xliff/.xml file was found inside.")
                return "", [], logs

            logs.append(f"XLZ package detected. Found {len(candidate_names)} XLIFF/XML/XLZ file(s) inside.")

            for inner_name in candidate_names:
                if reached_segment_limit(all_segments, max_segments):
                    break

                try:
                    inner_data = zf.read(inner_name)
                    inner_text, encoding_used = decode_text_bytes(inner_data)
                except Exception as exc:
                    logs.append(f"{inner_name}: could not read/decode file: {exc}")
                    continue

                remaining_limit = 0 if unlimited_scan(max_segments) else max(0, int(max_segments) - len(all_segments))
                segs, seg_logs = extract_xliff_pairs_from_xml_text(
                    inner_text,
                    mode=mode,
                    max_segments=remaining_limit,
                    source_label=inner_name,
                )
                logs.extend([f"{msg} (decoded as {encoding_used})" for msg in seg_logs])

                for seg in segs:
                    seg["id"] = len(all_segments) + 1
                    all_segments.append(seg)
                    if reached_segment_limit(all_segments, max_segments):
                        break

    except Exception as exc:
        logs.append(f"Could not open XLZ package: {exc}")
        return "", [], logs

    return "", all_segments, logs


def extract_xlz_pro_segments(uploaded_file, max_segments: int):
    """Extract XLIFF/XML/XLZ segments from an .xlz package for Pro translation.

    Returns a package object that can later be rebuilt as .xlz with translated
    <target> nodes filled in.
    """
    import xml.etree.ElementTree as ET
    data = uploaded_file.getvalue()
    logs: List[str] = []
    segments: List[Dict[str, Any]] = []
    target_map: Dict[str, Any] = {}
    package = {
        "entries": {},
        "trees": {},
        "xml_names": set(),
        "original_name": uploaded_file.name,
    }

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                package["entries"][info.filename] = zf.read(info.filename)

            candidate_names = [
                n for n in zf.namelist()
                if n.lower().endswith((".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".xml"))
                and not n.startswith("__MACOSX/")
            ]

            if not candidate_names:
                logs.append("XLZ package opened, but no .xlf/.xliff/.xml file was found inside.")
                return None, [], {}, logs

            logs.append(f"XLZ package detected. Found {len(candidate_names)} XLIFF/XML/XLZ file(s) inside.")

            for inner_name in candidate_names:
                if reached_segment_limit(segments, max_segments):
                    break

                raw_text, encoding_used = decode_text_bytes(package["entries"][inner_name])
                try:
                    tree = ET.ElementTree(ET.fromstring(raw_text))
                except Exception as exc:
                    logs.append(f"{inner_name}: XML parse failed: {exc}")
                    continue

                package["trees"][inner_name] = tree
                package["xml_names"].add(inner_name)
                root = tree.getroot()

                for parent in root.iter():
                    if reached_segment_limit(segments, max_segments):
                        break
                    children = list(parent)
                    if not children:
                        continue
                    src_el = None
                    tgt_el = None
                    for child in children:
                        lname = xml_local_name(child.tag)
                        if lname == "source" and src_el is None:
                            src_el = child
                        elif lname == "target" and tgt_el is None:
                            tgt_el = child
                    if src_el is None:
                        continue
                    src_text = clean_line_for_ai("".join(src_el.itertext()))
                    if not src_text:
                        continue
                    if tgt_el is None:
                        tgt_el = ET.Element(make_xml_target_tag(src_el.tag))
                        try:
                            insert_at = children.index(src_el) + 1
                            parent.insert(insert_at, tgt_el)
                        except Exception:
                            parent.append(tgt_el)
                    loc = f"{inner_name} Segment {len(segments) + 1}"
                    segments.append({
                        "id": len(segments) + 1,
                        "file_type": "xlz",
                        "sheet": inner_name,
                        "location": loc,
                        "source": src_text,
                        "translation": clean_line_for_ai("".join(tgt_el.itertext())) if tgt_el is not None else "",
                        "text": src_text,
                        "mode": "source_only",
                    })
                    target_map[loc] = (inner_name, tgt_el)

                logs.append(f"{inner_name}: extracted segments (decoded as {encoding_used}).")

    except Exception as exc:
        logs.append(f"Could not open XLZ package: {exc}")
        return None, [], {}, logs

    logs.append(f"XLZ: extracted {len(segments)} source segment(s) for translation.")
    return package, segments, target_map, logs


def build_translated_xlz_bytes(package: Dict[str, Any], target_map: Dict[str, Any], translations_by_loc: Dict[str, str]) -> bytes:
    """Rebuild an .xlz ZIP package with translated <target> elements filled in."""
    import zipfile as _zipfile
    for loc, target_info in target_map.items():
        if loc not in translations_by_loc:
            continue
        _inner_name, target_el = target_info
        trans = translations_by_loc.get(loc, "")
        if trans:
            target_el.text = trans

    output = io.BytesIO()
    with _zipfile.ZipFile(output, "w", compression=_zipfile.ZIP_DEFLATED) as zf:
        for name, original_bytes in package.get("entries", {}).items():
            if name in package.get("xml_names", set()) and name in package.get("trees", {}):
                xml_out = io.BytesIO()
                package["trees"][name].write(xml_out, encoding="utf-8", xml_declaration=True)
                zf.writestr(name, xml_out.getvalue())
            else:
                zf.writestr(name, original_bytes)
    output.seek(0)
    return output.getvalue()

def is_text_like_extension(file_name: str) -> bool:
    lower = file_name.lower()
    return lower.endswith((
        ".txt", ".srt", ".md", ".markdown", ".po", ".pot", ".properties", ".strings", ".resx",
        ".html", ".htm", ".yaml", ".yml", ".ini", ".log"
    ))


# ==========================================================
# UI SHARED FUNCTIONS
# ==========================================================

def render_report(report_rows: List[Dict[str, Any]], title: str = "Report"):
    if not report_rows:
        st.success("No errors found for the checked segments.")
        return

    df = pd.DataFrame(report_rows)
    st.markdown(f"### {title}")

    severity_series = df.get("Severity", pd.Series([], dtype=str)).astype(str)
    critical = int((severity_series == "Critical").sum())
    major = int((severity_series == "Major").sum())
    minor = int((severity_series == "Minor").sum())
    review = int((severity_series == "Review").sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Rows", len(df))
    c2.metric("Critical", critical)
    c3.metric("Major", major)
    c4.metric("Minor", minor)
    c5.metric("Review", review)

    if "Error Type" in df.columns:
        st.markdown("#### Errors by Type")
        type_df = df["Error Type"].value_counts().reset_index()
        type_df.columns = ["Error Type", "Count"]
        st.dataframe(type_df, use_container_width=True, hide_index=True)

    st.markdown("#### Detailed Table")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("#### Findings Preview")
    for _, row in df.head(30).iterrows():
        sev = str(row.get("Severity", "Minor")).lower()
        if sev not in ["minor", "major", "critical", "review"]:
            sev = "review"
        badge = f'<span class="severity-badge sev-{sev}">{escape(str(row.get("Severity", "")))}</span>'
        st.markdown(f"""
        <div class="error-card {sev}">
            <div class="error-type">{escape(str(row.get('Error Type','')))} · {escape(str(row.get('Location','')))} · {escape(str(row.get('Check Source','')))} {badge}</div>
            <div class="error-before">Issue: {escape(str(row.get('Wrong Part','')))}</div>
            <div class="error-after">Suggestion: {escape(str(row.get('Suggestion','')))}</div>
            <div class="error-reason">{escape(str(row.get('Explanation','')))}</div>
        </div>
        """, unsafe_allow_html=True)





# ==========================================================
# SUPABASE AUTH + CREDITS + USAGE LOGS
# ==========================================================

SUPABASE_TIMEOUT = 25
DEFAULT_TRIAL_CREDITS = 25
PLAN_CREDITS = {
    "trial": 25,
    "errorsweep": 200,
    "pro": 600,
    "agency": 2500,
    "enterprise": 10000,
}


# Billing plan catalog.
# Payment links are read from Streamlit Secrets, so no payment URL is stored in GitHub.
PLAN_CATALOG = {
    "trial": {
        "name": "Free Trial",
        "price": "₹0",
        "credits": 25,
        "tagline": "Try ErrorSweep with a small monthly allowance.",
        "features": [
            "Offline QA checks",
            "Limited segment preview",
            "Basic Excel report",
            "No Rules ZIP for trial users",
        ],
        "secret_key": "",
    },
    "errorsweep": {
        "name": "ErrorSweep",
        "price": "₹999 / month",
        "credits": 200,
        "tagline": "QA review, reports, and client rules for regular users.",
        "features": [
            "QA Run + suggestions",
            "Rules ZIP support",
            "Excel QA reports",
            "Offline + optional AI checks",
        ],
        "secret_key": "PAYMENT_LINK_ERRORSWEEP",
    },
    "pro": {
        "name": "ErrorSweep Pro",
        "price": "₹2,999 / month",
        "credits": 600,
        "tagline": "Translation + review workflow for production files.",
        "features": [
            "Everything in ErrorSweep",
            "Translate + Review",
            "Same-format translation output where possible",
            "Independent review workflow",
        ],
        "secret_key": "PAYMENT_LINK_PRO",
    },
    "agency": {
        "name": "Agency",
        "price": "₹9,999 / month",
        "credits": 2500,
        "tagline": "Higher-volume workflows for localization teams.",
        "features": [
            "Everything in Pro",
            "Higher monthly credits",
            "Large-file workflows",
            "Priority manual support",
        ],
        "secret_key": "PAYMENT_LINK_AGENCY",
    },
    "enterprise": {
        "name": "Enterprise",
        "price": "Custom",
        "credits": 10000,
        "tagline": "Custom credits, limits, private support, and rule logic.",
        "features": [
            "Custom monthly credits",
            "Dedicated support",
            "Private deployment option",
            "Client-specific rule packs",
        ],
        "secret_key": "PAYMENT_LINK_ENTERPRISE",
    },
}


def normalize_plan(plan: Any) -> str:
    plan = str(plan or "trial").strip().lower()
    return plan if plan in PLAN_CATALOG else "trial"


def get_payment_link(plan: str) -> str:
    plan = normalize_plan(plan)
    secret_key = PLAN_CATALOG[plan].get("secret_key", "")
    candidate_keys = []
    if secret_key:
        candidate_keys.append(secret_key)
    candidate_keys.extend([
        f"PAYMENT_LINK_{plan.upper()}",
        f"RAZORPAY_LINK_{plan.upper()}",
        f"RAZORPAY_{plan.upper()}_LINK",
        f"STRIPE_LINK_{plan.upper()}",
    ])
    for key in candidate_keys:
        value = get_secret_value(key)
        if value:
            return str(value)
    return ""


def render_plan_card(plan_key: str, current_plan: str) -> None:
    plan_key = normalize_plan(plan_key)
    current_plan = normalize_plan(current_plan)
    info = PLAN_CATALOG[plan_key]
    is_current = plan_key == current_plan

    st.markdown(f"### {info['name']}")
    st.metric("Price", info["price"])
    st.caption(info["tagline"])
    st.write(f"**Monthly credits:** {info['credits']}")
    for feature in info["features"]:
        st.write(f"- {feature}")

    if is_current:
        st.success("Current plan")
    elif plan_key != "trial":
        link = get_payment_link(plan_key)
        if link:
            st.link_button(f"Upgrade to {info['name']}", link, use_container_width=True)
        else:
            st.info(f"Add {info['secret_key']} in Streamlit Secrets to enable this upgrade button.")
    else:
        st.caption("Trial is created automatically after signup.")


def supabase_configured() -> bool:
    return bool(get_secret_value("SUPABASE_URL") and get_secret_value("SUPABASE_ANON_KEY"))


def supabase_service_configured() -> bool:
    return bool(get_secret_value("SUPABASE_URL") and get_secret_value("SUPABASE_SERVICE_ROLE_KEY"))


def supabase_url(path: str) -> str:
    base = (get_secret_value("SUPABASE_URL") or "").rstrip("/")
    return f"{base}{path}"


def supabase_headers(kind: str = "anon", access_token: Optional[str] = None) -> Dict[str, str]:
    if kind == "service":
        key = get_secret_value("SUPABASE_SERVICE_ROLE_KEY")
    else:
        key = get_secret_value("SUPABASE_ANON_KEY")

    headers = {
        "apikey": key or "",
        "Authorization": f"Bearer {access_token or key or ''}",
        "Content-Type": "application/json",
    }
    return headers


def supabase_post(path: str, payload: Dict[str, Any], kind: str = "anon", access_token: Optional[str] = None) -> Tuple[bool, Any]:
    try:
        res = requests.post(
            supabase_url(path),
            headers=supabase_headers(kind=kind, access_token=access_token),
            json=payload,
            timeout=SUPABASE_TIMEOUT,
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


def supabase_get(path: str, kind: str = "anon", access_token: Optional[str] = None) -> Tuple[bool, Any]:
    try:
        res = requests.get(
            supabase_url(path),
            headers=supabase_headers(kind=kind, access_token=access_token),
            timeout=SUPABASE_TIMEOUT,
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


def supabase_patch(path: str, payload: Dict[str, Any], kind: str = "service", access_token: Optional[str] = None) -> Tuple[bool, Any]:
    try:
        res = requests.patch(
            supabase_url(path),
            headers={**supabase_headers(kind=kind, access_token=access_token), "Prefer": "return=representation"},
            json=payload,
            timeout=SUPABASE_TIMEOUT,
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


def auth_sign_up(email: str, password: str, full_name: str = "") -> Tuple[bool, str, Dict[str, Any]]:
    payload = {
        "email": email.strip().lower(),
        "password": password,
        "data": {"full_name": full_name.strip() or email.strip().split("@")[0]},
    }
    ok, data = supabase_post("/auth/v1/signup", payload, kind="anon")
    if not ok:
        return False, format_supabase_error(data), {}
    return True, "Account created. If email confirmation is enabled, please confirm your email before signing in.", data or {}


def auth_sign_in(email: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
    payload = {"email": email.strip().lower(), "password": password}
    ok, data = supabase_post("/auth/v1/token?grant_type=password", payload, kind="anon")
    if not ok:
        return False, format_supabase_error(data), {}
    if not data.get("access_token"):
        return False, "Login failed. Please check email confirmation and password.", {}
    return True, "Login successful.", data


def auth_send_password_reset(email: str) -> Tuple[bool, str]:
    ok, data = supabase_post("/auth/v1/recover", {"email": email.strip().lower()}, kind="anon")
    if not ok:
        return False, format_supabase_error(data)
    return True, "Password reset email sent if the account exists."


def format_supabase_error(data: Any) -> str:
    if isinstance(data, dict):
        for key in ["msg", "message", "error_description", "error"]:
            if data.get(key):
                return str(data.get(key))
        return json.dumps(data)[:500]
    return str(data)[:500]


def set_session_from_auth(data: Dict[str, Any]) -> None:
    user = data.get("user") or {}
    st.session_state["errorsweep_authenticated"] = True
    st.session_state["sb_access_token"] = data.get("access_token")
    st.session_state["sb_refresh_token"] = data.get("refresh_token")
    st.session_state["sb_user"] = user
    st.session_state["errorsweep_username"] = user.get("email", "user")


def get_current_user() -> Dict[str, Any]:
    return st.session_state.get("sb_user") or {}


def ensure_profile(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    user_id = user.get("id")
    email = user.get("email")
    if not user_id or not supabase_service_configured():
        return None

    profile = get_profile(user_id)
    if profile:
        return profile

    payload = {
        "id": user_id,
        "email": email,
        "full_name": (user.get("user_metadata") or {}).get("full_name") or email,
        "plan": "trial",
        "monthly_credits": DEFAULT_TRIAL_CREDITS,
        "used_credits": 0,
        "total_files_processed": 0,
    }
    ok, data = supabase_post("/rest/v1/profiles", payload, kind="service")
    if not ok:
        return None
    return get_profile(user_id)


def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id or not supabase_service_configured():
        return None
    ok, data = supabase_get(f"/rest/v1/profiles?id=eq.{user_id}&select=*", kind="service")
    if ok and isinstance(data, list) and data:
        return data[0]
    return None


def remaining_credits(profile: Optional[Dict[str, Any]]) -> int:
    if not profile:
        return 0
    try:
        return max(0, int(profile.get("monthly_credits") or 0) - int(profile.get("used_credits") or 0))
    except Exception:
        return 0


def calculate_credit_cost(workflow: str, segment_count: int, rules_zip_used: bool = False, independent_review: bool = False) -> int:
    """Transparent MVP credit model.
    QA: 1 credit / 100 segments.
    Pro: 3 credits / 75 segments + optional independent review credit.
    Rules ZIP adds 1 credit because it increases context processing.
    """
    segment_count = max(1, int(segment_count or 1))
    if workflow == "qa":
        credits = max(1, math.ceil(segment_count / 100))
    else:
        credits = max(3, math.ceil(segment_count / 75) * 3)
        if independent_review:
            credits += max(1, math.ceil(segment_count / 150))
    if rules_zip_used:
        credits += 1
    return int(credits)


def credit_preflight(profile: Optional[Dict[str, Any]], credits_needed: int) -> Tuple[bool, str]:
    if not supabase_service_configured():
        return False, "Supabase service role is not configured. Add SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets."
    if not profile:
        return False, "User profile not found. Please log out and log in again."
    if remaining_credits(profile) < credits_needed:
        return False, f"Not enough credits. Required: {credits_needed}, remaining: {remaining_credits(profile)}."
    return True, "OK"


def consume_user_credits(user_id: str, credits: int, workflow: str, file_name: str, segment_count: int, metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not user_id:
        return False, "Missing user id.", None
    if credits <= 0:
        return True, "No credits charged.", get_profile(user_id)
    if not supabase_service_configured():
        return False, "Supabase service role is not configured.", None

    payload = {
        "p_user_id": user_id,
        "p_credits": int(credits),
        "p_workflow": workflow,
        "p_file_name": file_name,
        "p_segments": int(segment_count or 0),
        "p_metadata": metadata or {},
    }
    ok, data = supabase_post("/rest/v1/rpc/consume_user_credits", payload, kind="service")
    if ok:
        refreshed = get_profile(user_id)
        return True, "Credits charged successfully.", refreshed

    # Friendly fallback message. Do not silently bypass payment/credits.
    return False, "Credit deduction failed. Make sure the Supabase SQL setup was executed. Details: " + format_supabase_error(data), get_profile(user_id)


def log_report_record(user_id: str, workflow: str, file_name: str, segment_count: int, issue_count: int, output_name: str, credits_charged: int) -> None:
    if not user_id or not supabase_service_configured():
        return
    payload = {
        "user_id": user_id,
        "workflow": workflow,
        "file_name": file_name,
        "segments": int(segment_count or 0),
        "issues": int(issue_count or 0),
        "output_name": output_name,
        "credits_charged": int(credits_charged or 0),
    }
    supabase_post("/rest/v1/file_jobs", payload, kind="service")


def get_recent_jobs(user_id: str, limit: int = 8) -> List[Dict[str, Any]]:
    if not user_id or not supabase_service_configured():
        return []
    ok, data = supabase_get(
        f"/rest/v1/file_jobs?user_id=eq.{user_id}&select=*&order=created_at.desc&limit={int(limit)}",
        kind="service",
    )
    if ok and isinstance(data, list):
        return data
    return []



# ==========================================================
# ADMIN USER MANAGEMENT
# ==========================================================


def get_admin_emails() -> List[str]:
    raw = get_secret_value("ERRORSWEEP_ADMIN_EMAILS", "") or ""
    return [email.strip().lower() for email in raw.split(",") if email.strip()]


def is_admin_user() -> bool:
    user = get_current_user()
    email = (user.get("email") or st.session_state.get("errorsweep_username", "")).strip().lower()
    return bool(email and email in get_admin_emails())


def admin_list_profiles(search: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    if not supabase_service_configured():
        return []
    if search.strip():
        pattern = quote(f"*{search.strip()}*", safe="")
        query = f"/rest/v1/profiles?select=*&email=ilike.{pattern}&order=created_at.desc&limit={int(limit)}"
    else:
        query = f"/rest/v1/profiles?select=*&order=created_at.desc&limit={int(limit)}"
    ok, data = supabase_get(query, kind="service")
    if ok and isinstance(data, list):
        return data
    return []


def admin_get_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
    if not email.strip() or not supabase_service_configured():
        return None
    email_q = quote(email.strip().lower(), safe="")
    ok, data = supabase_get(f"/rest/v1/profiles?email=eq.{email_q}&select=*&limit=1", kind="service")
    if ok and isinstance(data, list) and data:
        return data[0]
    return None


def admin_update_profile(user_id: str, updates: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not user_id:
        return False, "Missing user id.", None
    allowed = {"plan", "monthly_credits", "used_credits", "full_name"}
    safe_updates = {k: v for k, v in updates.items() if k in allowed}
    if not safe_updates:
        return False, "No valid fields to update.", None
    ok, data = supabase_patch(f"/rest/v1/profiles?id=eq.{user_id}", safe_updates, kind="service")
    if not ok:
        return False, format_supabase_error(data), None
    return True, "Profile updated successfully.", get_profile(user_id)


def admin_list_jobs(user_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    if not supabase_service_configured():
        return []
    if user_id:
        query = f"/rest/v1/file_jobs?user_id=eq.{user_id}&select=*&order=created_at.desc&limit={int(limit)}"
    else:
        query = f"/rest/v1/file_jobs?select=*&order=created_at.desc&limit={int(limit)}"
    ok, data = supabase_get(query, kind="service")
    if ok and isinstance(data, list):
        return data
    return []


def admin_usage_summary() -> Dict[str, Any]:
    profiles = admin_list_profiles(limit=500)
    jobs = admin_list_jobs(limit=500)
    return {
        "users": len(profiles),
        "jobs": len(jobs),
        "credits_used": sum(int(p.get("used_credits") or 0) for p in profiles),
        "credits_allocated": sum(int(p.get("monthly_credits") or 0) for p in profiles),
    }

def render_credit_panel(profile: Optional[Dict[str, Any]]) -> None:
    if not profile:
        st.warning("Profile unavailable. Check Supabase setup.")
        return
    plan = str(profile.get("plan") or "trial").title()
    monthly = int(profile.get("monthly_credits") or 0)
    used = int(profile.get("used_credits") or 0)
    remaining = max(0, monthly - used)
    st.markdown("### Account")
    st.caption(profile.get("email", "user"))
    st.metric("Plan", plan)
    st.metric("Credits Remaining", remaining)
    st.progress(min(1.0, used / max(monthly, 1)))
    st.caption(f"{used} / {monthly} credits used this month")


def render_usage_dashboard(user_id: str) -> None:
    profile = get_profile(user_id)
    if not profile:
        return
    plan = str(profile.get("plan") or "trial").title()
    monthly = int(profile.get("monthly_credits") or 0)
    used = int(profile.get("used_credits") or 0)
    remaining = max(0, monthly - used)
    jobs = get_recent_jobs(user_id, limit=8)

    st.markdown("### Usage Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plan", plan)
    c2.metric("Monthly Credits", monthly)
    c3.metric("Used", used)
    c4.metric("Remaining", remaining)

    if jobs:
        with st.expander("Recent jobs", expanded=False):
            st.dataframe(pd.DataFrame(jobs), use_container_width=True, hide_index=True)

# ==========================================================
# LOGIN / SESSION AUTH
# ==========================================================

def is_authenticated() -> bool:
    return bool(st.session_state.get("errorsweep_authenticated") and st.session_state.get("sb_user"))


def logout_user() -> None:
    for key in [
        "errorsweep_authenticated",
        "errorsweep_username",
        "sb_access_token",
        "sb_refresh_token",
        "sb_user",
        "sb_profile",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


def render_login_page() -> None:
    st.markdown(
        """
        <style>
        .login-wrapper {
            max-width: 620px;
            margin: 6vh auto 0 auto;
            background: linear-gradient(135deg, rgba(0,255,136,0.12), rgba(56,189,248,0.08), rgba(139,92,246,0.10));
            border: 1px solid rgba(56,189,248,0.22);
            border-radius: 24px;
            padding: 38px 36px 26px 36px;
            box-shadow: 0 25px 80px rgba(0,0,0,0.35);
            text-align: center;
        }
        .login-title {
            font-family: 'Space Mono', monospace;
            font-size: 40px;
            color: #00ff88;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .login-subtitle {
            color: #a8acc8;
            font-size: 15px;
            margin-bottom: 10px;
        }
        .login-badge {
            display: inline-block;
            background: rgba(0,255,136,0.08);
            border: 1px solid rgba(0,255,136,0.25);
            color: #00ff88;
            border-radius: 999px;
            padding: 6px 16px;
            font-size: 12px;
            margin-top: 8px;
        }
        </style>
        <div class="login-wrapper">
            <div class="login-title">ErrorSweep</div>
            <div class="login-subtitle">Secure language automation dashboard</div>
            <div class="login-badge">Account required</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not supabase_configured():
        st.error("Supabase is not configured yet.")
        st.info("Add these values in Streamlit Cloud → App → Settings → Secrets:")
        st.code(
            'SUPABASE_URL = "https://your-project.supabase.co"\n'
            'SUPABASE_ANON_KEY = "your-anon-key"\n'
            'SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"',
            language="toml",
        )
        st.stop()

    tab_login, tab_signup, tab_reset = st.tabs(["Sign in", "Create account", "Reset password"])

    with tab_login:
        with st.form("supabase_login_form", clear_on_submit=False):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
        if submitted:
            ok, msg, data = auth_sign_in(email, password)
            if ok:
                set_session_from_auth(data)
                profile = ensure_profile(data.get("user") or {})
                st.session_state["sb_profile"] = profile
                st.success("Signed in successfully.")
                st.rerun()
            else:
                st.error(msg)

    with tab_signup:
        with st.form("supabase_signup_form", clear_on_submit=False):
            full_name = st.text_input("Full name")
            new_email = st.text_input("Email", key="signup_email")
            new_password = st.text_input("Password", type="password", key="signup_password", help="Use at least 8 characters.")
            confirm_password = st.text_input("Confirm password", type="password")
            signup_submitted = st.form_submit_button("Create account", use_container_width=True, type="primary")
        if signup_submitted:
            if len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                ok, msg, data = auth_sign_up(new_email, new_password, full_name)
                if ok:
                    user = data.get("user") or {}
                    if user:
                        ensure_profile(user)
                    st.success(msg)
                else:
                    st.error(msg)

    with tab_reset:
        with st.form("password_reset_form", clear_on_submit=True):
            reset_email = st.text_input("Account email")
            reset_submitted = st.form_submit_button("Send reset email", use_container_width=True)
        if reset_submitted:
            ok, msg = auth_send_password_reset(reset_email)
            if ok:
                st.success(msg)
            else:
                st.error(msg)


# ==========================================================
# NO-SIDEBAR APPLICATION LAYOUT
# Everything users need is available from normal pages.
# The app no longer depends on st.sidebar for logout/settings.
# ==========================================================

def init_page_state() -> None:
    defaults = {
        "es_page": "Dashboard",
        "es_domain": "Auto-detect",
        "es_strictness": "Strict",
        "es_check_whole_file": True,
        "es_max_segments": 200,
        "es_batch_size": 20,
        "es_source_col_hint": "",
        "es_target_col_hint": "",
        "es_skip_non_content": True,
        "es_deep_scan": False,
        "es_target_language": "Telugu",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def get_page_settings() -> Dict[str, Any]:
    check_whole_file = bool(st.session_state.get("es_check_whole_file", True))
    return {
        "domain": st.session_state.get("es_domain", "Auto-detect"),
        "strictness": st.session_state.get("es_strictness", "Strict"),
        "check_whole_file": check_whole_file,
        "max_segments": 0 if check_whole_file else int(st.session_state.get("es_max_segments", 200)),
        "batch_size": int(st.session_state.get("es_batch_size", 20)),
        "source_col_hint": st.session_state.get("es_source_col_hint", ""),
        "target_col_hint": st.session_state.get("es_target_col_hint", ""),
        "skip_non_content": bool(st.session_state.get("es_skip_non_content", True)),
        "deep_scan": bool(st.session_state.get("es_deep_scan", False)),
        "target_language": st.session_state.get("es_target_language", "Telugu"),
        "openai_model": DEFAULT_OPENAI_MODEL,
        "gemini_model": DEFAULT_GEMINI_MODEL,
    }


def render_top_account_bar(profile: Optional[Dict[str, Any]]) -> None:
    user = get_current_user()
    email = user.get("email") or st.session_state.get("errorsweep_username", "user")
    c1, c2, c3, c4 = st.columns([2.2, 1.2, 1.2, 1])
    with c1:
        st.caption(f"Signed in as: {email}")
    with c2:
        if profile:
            st.caption(f"Plan: {str(profile.get('plan', 'trial')).title()}")
    with c3:
        if profile:
            st.caption(f"Credits: {remaining_credits(profile)}")
    with c4:
        if st.button("Logout", use_container_width=True, key="top_logout_button"):
            logout_user()


def render_top_nav() -> str:
    pages = ["Dashboard", "ErrorSweep", "ErrorSweep Pro", "Billing", "Account"]
    if is_admin_user():
        pages.append("Admin")
    if st.session_state.get("es_page") not in pages:
        st.session_state["es_page"] = "Dashboard"
    return st.radio(
        "Navigation",
        pages,
        key="es_page",
        horizontal=True,
        label_visibility="collapsed",
    )


def render_settings_summary(settings: Dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Domain", settings["domain"])
    c2.metric("Strictness", settings["strictness"])
    c3.metric("Scan", "Whole file" if settings["check_whole_file"] else str(settings["max_segments"]))
    c4.metric("Batch", settings["batch_size"])
    with st.expander("Current settings", expanded=False):
        st.write(f"Source column hint: {settings['source_col_hint'] or 'Auto-detect'}")
        st.write(f"Target column hint: {settings['target_col_hint'] or 'Auto-detect'}")
        st.write(f"Skip non-content sheets: {'Yes' if settings['skip_non_content'] else 'No'}")
        st.write(f"Deep scan fallback: {'Yes' if settings['deep_scan'] else 'No'}")
        st.write(f"Target language for Pro: {settings['target_language']}")
        st.write(f"Managed AI allowed: {'Yes' if managed_ai_allowed() else 'No'}")
        st.write(f"User language-engine key entered: {'Yes' if bool(get_user_openai_key()) else 'No'}")


def render_inline_workflow_settings(context: str) -> Dict[str, Any]:
    """Render settings directly inside ErrorSweep / ErrorSweep Pro pages.

    This removes the need for a separate Control Center page and avoids dependence
    on the left sidebar. The same session keys are used so settings persist when
    users move between pages.
    """
    is_pro = context == "pro"
    label = "Translation & review settings" if is_pro else "QA settings"

    with st.expander(label, expanded=True):
        st.markdown("#### Core settings")
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox(
                "Content Domain",
                [
                    "Auto-detect",
                    "Software UI / App Strings",
                    "Subtitles / Captions",
                    "Legal / Compliance",
                    "Medical / Healthcare",
                    "Marketing / Ad Copy",
                    "E-learning / Education",
                    "General",
                ],
                key="es_domain",
            )
        with c2:
            st.select_slider(
                "QA Strictness",
                options=["Lenient", "Standard", "Strict", "Very Strict"],
                key="es_strictness",
            )

        st.markdown("#### Scan and extraction")
        s1, s2, s3 = st.columns(3)
        with s1:
            st.checkbox(
                "Check whole file",
                key="es_check_whole_file",
                help="When enabled, ErrorSweep checks every extracted segment. Turn off for smaller paid/test runs.",
            )
        with s2:
            if st.session_state.get("es_check_whole_file", True):
                st.info("Full-file mode ON")
            else:
                st.number_input("Max total segments", min_value=5, max_value=5000, key="es_max_segments")
        with s3:
            st.number_input("Segments per AI call", min_value=5, max_value=50, key="es_batch_size")

        d1, d2 = st.columns(2)
        with d1:
            st.text_input("Source column name/index", key="es_source_col_hint", placeholder="Example: Source Text or 2")
        with d2:
            st.text_input("Target / translation column name/index", key="es_target_col_hint", placeholder="Example: Original Translation or 3")

        f1, f2 = st.columns(2)
        with f1:
            st.checkbox("Skip non-content sheets", key="es_skip_non_content")
        with f2:
            st.checkbox("Deep scan if columns are not found", key="es_deep_scan")

        if is_pro:
            st.markdown("#### Pro translation options")
            st.text_input("Target language", key="es_target_language", placeholder="Example: Spanish, French, Hindi, Telugu")

        st.markdown("#### Optional API keys")
        if is_pro:
            st.caption("Use these only if the client wants translation/review to run on their own provider account. Keys are used for this browser session only and are not saved.")
        else:
            st.caption("Optional: enter a language-engine key only if you want AI QA suggestions. Offline rules work without any API key. Keys are not saved.")
        a1, a2 = st.columns(2)
        with a1:
            st.text_input("Language-engine API key (optional)", type="password", key="es_user_openai_api_key")
        with a2:
            if is_pro:
                st.text_input("Independent-review API key (optional)", type="password", key="es_user_gemini_api_key")
            else:
                st.info("Independent review key is used only in ErrorSweep Pro.")
        st.caption(f"Managed server AI is {'enabled' if managed_ai_allowed() else 'disabled'} by deployment settings.")

    return get_page_settings()


def render_control_center_page() -> None:
    st.markdown("## Control Center")
    st.caption("All controls that were previously in the left panel are now available here.")

    st.markdown("### QA Settings")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox(
            "Content Domain",
            [
                "Auto-detect",
                "Software UI / App Strings",
                "Subtitles / Captions",
                "Legal / Compliance",
                "Medical / Healthcare",
                "Marketing / Ad Copy",
                "E-learning / Education",
                "General",
            ],
            key="es_domain",
        )
    with c2:
        st.select_slider(
            "QA Strictness",
            options=["Lenient", "Standard", "Strict", "Very Strict"],
            key="es_strictness",
        )

    st.markdown("### Scan Size")
    st.checkbox(
        "Check whole file",
        key="es_check_whole_file",
        help="When enabled, ErrorSweep extracts and checks every available segment instead of stopping after a fixed limit.",
    )
    if st.session_state.get("es_check_whole_file", True):
        st.info("Full-file mode is ON. Large files can take longer and may consume more credits/API usage.")
    else:
        st.number_input("Max total segments", min_value=5, max_value=5000, key="es_max_segments")
    st.number_input("Segments per AI call", min_value=5, max_value=50, key="es_batch_size")

    st.markdown("### File Detection")
    d1, d2 = st.columns(2)
    with d1:
        st.text_input("Source column name/index", key="es_source_col_hint", placeholder="Example: Source Text or 2")
    with d2:
        st.text_input("Translation column name/index", key="es_target_col_hint", placeholder="Example: Original Translation or 3")
    st.checkbox("Skip non-content sheets", key="es_skip_non_content")
    st.checkbox("Deep scan if columns are not found", key="es_deep_scan")

    st.markdown("### ErrorSweep Pro")
    st.text_input("Default target language", key="es_target_language", placeholder="Example: Spanish, French, Hindi, Telugu")

    st.markdown("### API Cost Control")
    st.info("API keys are optional. Without keys, ErrorSweep QA still runs in offline rule-based mode. ErrorSweep Pro uses glossary/DNT reference mode unless a language-engine key is provided.")
    st.text_input("Your language-engine API key (optional, current session only)", type="password", key="es_user_openai_api_key", help="Use this only if you want AI QA or full translation to use your own API account.")
    st.text_input("Your independent-review API key (optional, current session only)", type="password", key="es_user_gemini_api_key", help="Optional review engine key for independent review.")
    st.caption(f"Managed server AI is {'enabled' if managed_ai_allowed() else 'disabled'} by deployment settings.")

    st.markdown("### System Status")
    c1, c2 = st.columns(2)
    c1.metric("Language Engine", "Configured" if get_openai_client() else "Missing")
    c2.metric("Review Engine", "Configured" if get_gemini_client() else "Missing")
    st.caption("If an engine is missing, check Streamlit Secrets. This page replaces the hidden left panel.")


def render_account_page(profile: Optional[Dict[str, Any]]) -> None:
    st.markdown("## Account")
    user = get_current_user()
    st.write(f"**Email:** {user.get('email') or st.session_state.get('errorsweep_username', 'user')}")
    if profile:
        render_credit_panel(profile)
    st.divider()
    if st.button("Logout", type="primary", use_container_width=True, key="account_logout_button"):
        logout_user()


def render_billing_page(profile: Optional[Dict[str, Any]]) -> None:
    st.markdown("## Billing & Plans")
    st.caption("Use payment links for MVP billing. After payment, admin can manually upgrade the user from the Admin page.")

    if not profile:
        st.warning("Profile unavailable. Please log out and log in again.")
        return

    current_plan = normalize_plan(profile.get("plan"))
    monthly = int(profile.get("monthly_credits") or 0)
    used = int(profile.get("used_credits") or 0)
    remaining = max(0, monthly - used)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Plan", PLAN_CATALOG[current_plan]["name"])
    c2.metric("Credits Remaining", remaining)
    c3.metric("Used Credits", used)
    c4.metric("Monthly Credits", monthly)

    if monthly > 0:
        st.progress(min(1.0, used / max(monthly, 1)))

    if remaining <= max(5, monthly * 0.10):
        st.warning("Credits are low. Upgrade or contact admin to add credits.")

    st.markdown("### Choose a plan")
    p1, p2, p3 = st.columns(3)
    with p1:
        with st.container(border=True):
            render_plan_card("errorsweep", current_plan)
    with p2:
        with st.container(border=True):
            render_plan_card("pro", current_plan)
    with p3:
        with st.container(border=True):
            render_plan_card("agency", current_plan)

    with st.expander("Enterprise / custom plan", expanded=False):
        render_plan_card("enterprise", current_plan)

    st.markdown("### How billing works in this MVP")
    st.markdown(
        """
        1. User clicks an upgrade button and completes payment.
        2. Admin verifies payment in the payment provider dashboard.
        3. Admin opens **Admin** page in ErrorSweep.
        4. Admin searches the user's email and upgrades plan/credits.

        This manual flow is safer for the first launch. The next upgrade can add automatic payment webhooks.
        """
    )

    st.markdown("### Credit charging guide")
    st.dataframe(
        pd.DataFrame([
            {"Workflow": "ErrorSweep QA", "Credit rule": "1 credit per 100 segments", "Notes": "Rules ZIP adds 1 credit"},
            {"Workflow": "ErrorSweep Pro", "Credit rule": "3 credits per 75 segments", "Notes": "Independent review and Rules ZIP may add credits"},
            {"Workflow": "Offline QA", "Credit rule": "Same app credits apply", "Notes": "API availability does not make runs free"},
        ]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Secrets to add for payment buttons")
    st.code(
        'PAYMENT_LINK_ERRORSWEEP = "https://your-payment-link-for-errorsweep"\n'
        'PAYMENT_LINK_PRO = "https://your-payment-link-for-pro"\n'
        'PAYMENT_LINK_AGENCY = "https://your-payment-link-for-agency"\n'
        'PAYMENT_LINK_ENTERPRISE = "https://your-enterprise-contact-or-payment-link"',
        language="toml",
    )


def render_dashboard_page(user_id: str, profile: Optional[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    st.markdown(
        """
    <div class="hero">
        <div class="hero-title">ErrorSweep</div>
        <div class="hero-sub">QA suggestions, company rules ZIP, translation, and independent review</div>
        <div class="hero-badge">Top navigation · Workflow settings inside each page</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="note-card">
        <b>Navigation updated:</b> Each workflow now contains its own settings. ErrorSweep has QA settings; ErrorSweep Pro has translation/review settings and API options.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if user_id:
        render_usage_dashboard(user_id)

    render_settings_summary(settings)

    st.markdown("### Workflows")
    st.markdown(
        """
        <div class="es-visual-grid">
          <div class="es-tile"><h4>ErrorSweep</h4><p>QA settings, file detection, offline rules, optional API key, and QA Rules ZIP are all inside this page.</p></div>
          <div class="es-tile"><h4>ErrorSweep Pro</h4><p>Target language, translation settings, optional API keys, review settings, and Pro Rules ZIP are all inside this page.</p></div>
          <div class="es-tile"><h4>Billing</h4><p>View credits, plans, and upgrade options without using a sidebar.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rule_upload(prefix: str) -> Tuple[Any, Any, Dict[str, Any]]:
    uploaded_file = st.file_uploader(
        "Upload file",
        type=None,
        key=f"{prefix}_uploaded_file",
        help="Upload any file. ErrorSweep will automatically extract text/segments from Excel, Word, PDF, CSV, XLIFF/XML/XLZ, JSON, subtitles, PO/properties, and other text-like files. Binary files without readable text will return an Excel report explaining the issue.",
    )
    rules_zip = st.file_uploader(
        "Upload Rules ZIP (optional: style guide, DNT list, glossary, instructions, references)",
        type=["zip"],
        key=f"{prefix}_rules_zip",
    )
    rules = {"chunks": [], "glossary": [], "dnt": [], "files": [], "warnings": []}
    if rules_zip:
        rules = parse_rules_zip_bytes(rules_zip.getvalue())
        with st.expander("Rules ZIP summary", expanded=False):
            st.write(f"Files parsed: {len(rules.get('files', []))}")
            st.write(f"Rule chunks: {len(rules.get('chunks', []))}")
            st.write(f"Glossary entries: {len(rules.get('glossary', []))}")
            st.write(f"DNT entries: {len(rules.get('dnt', []))}")
            if rules.get("files"):
                st.write(rules.get("files")[:20])
            for w in rules.get("warnings", []):
                st.warning(w)
    return uploaded_file, rules_zip, rules




# ==========================================================
# OFFLINE / REFERENCE-ONLY TRANSLATION FALLBACK
# ==========================================================

def _apply_glossary_replacements(source_text: str, rules: Dict[str, Any]) -> Tuple[str, int]:
    """Very conservative no-API pre-translation.

    It uses only uploaded glossary terms. This is NOT a full machine translation.
    It is a safe fallback when no language engine/API key is available.
    """
    result = source_text or ""
    replacements = 0
    glossary = rules.get("glossary", []) if rules else []
    # Longest first avoids replacing small substrings before longer terms.
    glossary_sorted = sorted(glossary, key=lambda g: len(str(g.get("source_term", ""))), reverse=True)
    for g in glossary_sorted[:1000]:
        src = normalize_text(g.get("source_term", ""))
        tgt = normalize_text(g.get("target_term", ""))
        if not src or not tgt:
            continue
        pattern = re.compile(re.escape(src), re.IGNORECASE)
        result, count = pattern.subn(tgt, result)
        replacements += count
    return result, replacements


def offline_reference_translate_batch(
    segments: List[Dict[str, Any]],
    target_language: str,
    rules: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """No-API fallback for ErrorSweep Pro.

    Full translation needs a translation engine. When no API is available, this
    function still keeps the workflow alive by applying uploaded glossary/DNT
    references and returning safe placeholder output. It never pretends that a
    full professional translation was produced.
    """
    output = []
    dnt_terms = [normalize_text(d.get("term", "")) for d in (rules.get("dnt", []) if rules else []) if normalize_text(d.get("term", ""))]
    for seg in segments:
        loc = seg.get("location", "")
        source = normalize_text(seg.get("source") or seg.get("text") or "")
        if not source:
            output.append({"location": loc, "translation": ""})
            continue
        # Preserve placeholders-only, DNT-only, or bracket labels as-is.
        if source.startswith("[") and source.endswith("]"):
            translation = source
        elif any(term and source.strip() == term for term in dnt_terms):
            translation = source
        else:
            translation, count = _apply_glossary_replacements(source, rules)
            # If no glossary replacement happened, keep target blank rather than
            # copying English as a fake translation.
            if count == 0:
                translation = ""
        output.append({"location": loc, "translation": translation})
    return output


def build_offline_translation_review_rows(segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str]) -> List[Dict[str, Any]]:
    rows = []
    for seg in segments:
        loc = seg.get("location", "")
        trans = translations_by_loc.get(loc, "")
        if not trans:
            rows.append(make_report_row(
                {**seg, "translation": ""},
                "Translation Engine Required",
                "Review",
                "No offline full translation available",
                "Provide a language-engine API key or upload a glossary/rule pack with approved translations.",
                "Offline mode can apply deterministic QA and glossary/DNT references, but it cannot generate full professional translations for arbitrary global languages.",
                "Offline Reference Mode",
                "Built-in fallback",
                "High",
            ))
    return rows

def render_errorsweep_page(user_id: str, profile: Optional[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    st.markdown("## ErrorSweep — QA Run + Correct Suggestions")
    st.caption("Use this version for reviewing existing translations. QA settings, file detection, optional API key, and QA Rules ZIP are all on this page.")
    settings = render_inline_workflow_settings("qa")
    render_settings_summary(settings)

    openai_client = get_openai_client()
    if openai_client is None:
        st.info("Offline QA mode is available. Deterministic rules, company Rules ZIP, glossary, DNT, placeholders, numbers, spacing, punctuation, and language-specific checks can run without any API key. App credits still apply to generate reports.")

    uploaded_file, rules_zip, rules = render_rule_upload("qa")

    q1, q2, q3 = st.columns(3)
    with q1:
        run_rules = st.checkbox("Run deterministic rules", value=True, key="qa_run_rules")
        run_zwnj = st.checkbox("Check ZWNJ", value=True, key="qa_zwnj")
    with q2:
        run_ai = st.checkbox("Run AI QA suggestions", value=bool(openai_client), key="qa_run_ai")
        include_ai_style = st.checkbox("Allow subjective AI style/terminology suggestions", value=False, key="qa_ai_style")
    with q3:
        output_highlighted = st.checkbox("Highlight Excel output", value=True, key="qa_highlight")

    run = st.button("Run ErrorSweep QA", type="primary", use_container_width=True, disabled=not uploaded_file, key="run_qa_no_sidebar")

    if uploaded_file and run:
        if run_ai and openai_client is None:
            st.warning("AI QA is unavailable, so ErrorSweep will continue in offline rule-based mode. No API key is required, but app credits are still required for the report.")
            run_ai = False
        if not run_rules and not run_ai:
            st.warning("No checks selected. Turning deterministic offline rules ON so the file can still be reviewed without API keys.")
            run_rules = True

        start = time.time()
        status = st.empty()
        progress = st.progress(0)
        report_rows: List[Dict[str, Any]] = []
        logs = []
        lower = uploaded_file.name.lower()
        workbook = None
        cell_map = {}
        output_bytes = None
        mime_type = "text/csv"
        output_name = "errorsweep_report_" + uploaded_file.name

        file_bytes = uploaded_file_bytes(uploaded_file)
        if lower.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")) or is_openpyxl_compatible(file_bytes):
            workbook, segments, cell_map, _, logs = extract_excel_segments(
                io.BytesIO(file_bytes), settings["source_col_hint"], settings["target_col_hint"], "qa", int(settings["max_segments"]), settings["skip_non_content"], settings["deep_scan"]
            )
        elif lower.endswith(".csv"):
            _, segments, logs = extract_csv_segments(uploaded_file, settings["source_col_hint"], settings["target_col_hint"], "qa", int(settings["max_segments"]), settings["deep_scan"])
        elif lower.endswith(".docx"):
            _, segments, _, logs = extract_docx_segments(uploaded_file, "qa", int(settings["max_segments"]), settings["source_col_hint"], settings["target_col_hint"])
        elif lower.endswith(".pdf"):
            segments, logs = extract_pdf_segments(uploaded_file, "qa", int(settings["max_segments"]))
        else:
            _, segments, logs = extract_text_segments(uploaded_file, "qa", int(settings["max_segments"]))

        with st.expander("Extraction log", expanded=True):
            for log in logs:
                st.write(log)
            st.info(f"Found {len(segments)} segment(s) to check. Full-file mode is {'ON' if settings['check_whole_file'] else 'OFF'}.")

        if not segments:
            st.error("No segments found. Use the settings panel on this page to set source/translation columns or enable deep scan.")
            st.stop()

        # App credits are required for every generated report, even when API/AI is unavailable.
        # API credits and ErrorSweep app credits are separate:
        # - API credits pay the external language/review engine provider.
        # - App credits pay for ErrorSweep extraction, rule checks, report generation, storage/logging, and product usage.
        using_managed_ai = bool(run_ai and openai_client)
        segments, credits_needed, credit_message = maybe_limit_segments_to_available_credits(
            segments, profile, "qa", rules_zip_used=bool(rules_zip), independent_review=False
        )
        if not segments:
            st.error(f"{credit_message} App credits are required for all QA reports, including offline rule-based reports.")
            st.stop()
        if "Not enough credits" in credit_message:
            st.warning(credit_message)
        else:
            st.info(credit_message)
        engine_label = "Offline rules + managed AI QA" if using_managed_ai else "Offline rules only"
        st.info(f"Engine: {engine_label}. API availability does not block offline QA; app credits still apply.")

        if run_rules:
            status.text("Running deterministic checks...")
            for idx, seg in enumerate(segments, start=1):
                report_rows.extend(deterministic_checks(seg, rules, enable_zwnj=run_zwnj))
                progress.progress(min(idx / max(len(segments), 1) * 0.35, 0.35))

        if using_managed_ai:
            status.text("Running AI QA suggestions...")
            total_batches = max(1, (len(segments) + int(settings["batch_size"]) - 1) // int(settings["batch_size"]))
            for b in range(total_batches):
                batch = segments[b * int(settings["batch_size"]):(b + 1) * int(settings["batch_size"])]
                status.text(f"AI QA batch {b + 1}/{total_batches}...")
                report_rows.extend(ai_qa_batch(openai_client, settings["openai_model"], batch, rules, settings["domain"], settings["strictness"], include_ai_style))
                progress.progress(0.35 + ((b + 1) / total_batches) * 0.60)

        report_rows, dropped_ai_rows = post_filter_report_rows(report_rows, include_ai_style)
        if dropped_ai_rows:
            st.info(f"Filtered {dropped_ai_rows} low-confidence or subjective AI suggestion(s).")

        progress.progress(1.0)
        status.text(f"QA complete in {round(time.time() - start, 2)} seconds.")

        if lower.endswith(".xlsx") and workbook is not None:
            if output_highlighted:
                highlight_excel_cells(cell_map, report_rows)
            issue_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation", "Check Source", "Rule Source", "Confidence"]
            status_rows = build_segment_status_rows(segments, report_rows, checked_by="Rule Engine + AI QA")
            status_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Review Status", "Issue Count", "Highest Severity", "Error Types", "Suggestion Summary", "Explanation Summary", "Checked By"]
            add_report_sheet_to_workbook(workbook, "All Segment Review", status_rows, status_headers)
            add_report_sheet_to_workbook(workbook, "ErrorSweep Report", report_rows, issue_headers)
            bio = io.BytesIO()
            workbook.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_reviewed_" + uploaded_file.name
        else:
            status_rows = build_segment_status_rows(segments, report_rows, checked_by="Rule Engine + AI QA")
            output_bytes = build_excel_report_bytes(
                issue_rows=report_rows,
                status_rows=status_rows,
                extraction_logs=logs,
                title="ErrorSweep QA Report",
            )
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_review_report_" + re.sub(r"\.[^.]+$", ".xlsx", uploaded_file.name)

        refreshed_profile = profile
        charge_ok, charge_msg, refreshed_profile = consume_user_credits(
            user_id=user_id,
            credits=credits_needed,
            workflow="qa",
            file_name=uploaded_file.name,
            segment_count=len(segments),
            metadata={
                "issues": len(report_rows),
                "rules_zip": bool(rules_zip),
                "engine": "managed_ai" if using_managed_ai else "offline_rules",
                "api_used": bool(using_managed_ai),
            },
        )
        if not charge_ok:
            st.error(f"Could not deduct app credits, so the report cannot be released. {charge_msg}")
            st.stop()
        if refreshed_profile:
            st.session_state["sb_profile"] = refreshed_profile
        st.success(f"App credits charged: {credits_needed}. Remaining credits: {remaining_credits(refreshed_profile or profile)}")
        log_report_record(user_id, "qa", uploaded_file.name, len(segments), len(report_rows), output_name, credits_needed)

        status_rows_for_ui = build_segment_status_rows(segments, report_rows, checked_by="Rule Engine + AI QA")
        st.markdown("### Segment Coverage")
        c1, c2, c3 = st.columns(3)
        c1.metric("Segments checked", len(status_rows_for_ui))
        c2.metric("Segments with issues", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Needs Review"))
        c3.metric("Segments passed", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Pass"))
        with st.expander("All Segment Review Preview", expanded=False):
            st.dataframe(pd.DataFrame(status_rows_for_ui).head(200), use_container_width=True, hide_index=True)
        render_report(report_rows, "ErrorSweep QA Report")
        st.download_button("Download ErrorSweep Output", output_bytes, file_name=output_name, mime=mime_type, use_container_width=True)
        st.download_button(
            "Download Excel QA Report",
            build_excel_report_bytes(report_rows, status_rows_for_ui, extraction_logs=logs, title="ErrorSweep QA Report"),
            file_name="errorsweep_qa_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_errorsweep_pro_page(user_id: str, profile: Optional[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    st.markdown("## ErrorSweep Pro — Translate + Review")
    st.caption("Translate source content, run an independent review, and export a translated file plus review report. Pro settings and API options are all on this page.")
    settings = render_inline_workflow_settings("pro")
    render_settings_summary(settings)

    openai_client = get_openai_client()
    gemini_client = get_gemini_client()
    if openai_client is None:
        st.info("No language engine is configured. ErrorSweep Pro will use Offline Reference Mode: glossary/DNT/rule-pack assisted pre-translation only. Full automatic translation requires a user API key or managed language engine. App credits still apply to outputs.")

    uploaded_file, rules_zip, rules = render_rule_upload("pro")

    target_language = settings.get("target_language", "")
    p1, p2 = st.columns(2)
    with p1:
        apply_gemini_suggestions = st.checkbox("Apply reviewer suggestions to output", value=False, key="pro_apply_review")
    with p2:
        review_with_gemini = st.checkbox("Run independent review", value=bool(gemini_client), key="pro_review", disabled=not bool(gemini_client))

    run_pro = st.button("Run ErrorSweep Pro", type="primary", use_container_width=True, disabled=not uploaded_file, key="run_pro_no_sidebar")

    if uploaded_file and run_pro:
        using_language_engine = bool(openai_client)
        if not using_language_engine:
            st.warning("Offline Reference Mode is active. The app will preserve the file format and apply glossary/DNT references where possible, but it will not generate full professional translations without a language-engine API key. App credits still apply to generate outputs.")
            review_with_gemini = False
        if review_with_gemini and gemini_client is None:
            st.warning("Independent review service is not configured. Independent review will be skipped; deterministic review still runs.")
            review_with_gemini = False
        if not target_language.strip():
            st.error("Please enter the target language in the settings panel on this page.")
            st.stop()

        start = time.time()
        status = st.empty()
        progress = st.progress(0)
        lower = uploaded_file.name.lower()
        logs = []
        workbook = None
        dataframe = None
        text_original = None
        doc = None
        json_obj = None
        json_path_map = {}
        xml_tree = None
        xml_target_map = {}
        xlz_package = None
        xlz_target_map = {}
        srt_line_map = {}
        cell_map = {}
        translation_col_map = {}
        para_map = {}

        file_bytes = uploaded_file_bytes(uploaded_file)
        if lower.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")) or is_openpyxl_compatible(file_bytes):
            workbook, segments, cell_map, translation_col_map, logs = extract_excel_segments(
                io.BytesIO(file_bytes), settings["source_col_hint"], settings["target_col_hint"], "pro", int(settings["max_segments"]), settings["skip_non_content"], settings["deep_scan"]
            )
        elif lower.endswith(".csv"):
            dataframe, segments, logs = extract_csv_segments(uploaded_file, settings["source_col_hint"], settings["target_col_hint"], "pro", int(settings["max_segments"]), settings["deep_scan"])
        elif lower.endswith(".docx"):
            doc, segments, para_map, logs = extract_docx_segments(uploaded_file, "pro", int(settings["max_segments"]), settings["source_col_hint"], settings["target_col_hint"])
        elif lower.endswith(".json"):
            json_obj, segments, json_path_map, logs = extract_json_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith(".xlz"):
            xlz_package, segments, xlz_target_map, logs = extract_xlz_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith((".xml", ".xliff", ".xlf", ".sdlxliff", ".mqxliff")):
            xml_tree, segments, xml_target_map, logs = extract_xml_xliff_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith(".srt"):
            text_original, segments, srt_line_map, logs = extract_srt_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith(".pdf"):
            segments, logs = extract_pdf_segments(uploaded_file, "pro", int(settings["max_segments"]))
        else:
            text_original, segments, logs = extract_text_segments(uploaded_file, "pro", int(settings["max_segments"]))

        with st.expander("Extraction log", expanded=True):
            for log in logs:
                st.write(log)
            st.info(f"Found {len(segments)} segment(s) for translation. Full-file mode is {'ON' if settings['check_whole_file'] else 'OFF'}.")

        if not segments:
            st.error("No source segments found. Use the settings panel on this page to set the source column name/index.")
            st.stop()

        # App credits are required for every Pro output, even in Offline Reference Mode.
        # If API/language-engine credits are unavailable, ErrorSweep Pro can still create a same-format
        # reference-assisted output, but users must still spend app credits to receive that output.
        using_managed_pro_engine = bool(openai_client or (review_with_gemini and gemini_client))
        segments, credits_needed, credit_message = maybe_limit_segments_to_available_credits(
            segments, profile, "pro", rules_zip_used=bool(rules_zip), independent_review=bool(review_with_gemini)
        )
        if not segments:
            st.error(f"{credit_message} App credits are required for ErrorSweep Pro outputs, including Offline Reference Mode.")
            st.stop()
        if "Not enough credits" in credit_message:
            st.warning(credit_message)
        else:
            st.info(credit_message)
        if using_language_engine:
            engine_label = "Language engine"
        else:
            engine_label = "Offline Reference Mode"
        st.info(f"Engine: {engine_label}. API availability does not block reference-mode output; app credits still apply.")

        status.text("Translating file...")
        translations_by_loc: Dict[str, str] = {}
        total_batches = max(1, (len(segments) + int(settings["batch_size"]) - 1) // int(settings["batch_size"]))
        for b in range(total_batches):
            batch = segments[b * int(settings["batch_size"]):(b + 1) * int(settings["batch_size"])]
            status.text(f"Translation batch {b + 1}/{total_batches}...")
            if using_language_engine and openai_client:
                result = openai_translate_batch(openai_client, settings["openai_model"], batch, target_language, settings["domain"], rules)
            else:
                result = offline_reference_translate_batch(batch, target_language, rules)
            for item in result:
                loc = item.get("location", "")
                trans = item.get("translation", "")
                if loc is not None:
                    translations_by_loc[loc] = trans or ""
            progress.progress(((b + 1) / total_batches) * 0.45)

        translated_segments = []
        for seg in segments:
            loc = seg["location"]
            trans = translations_by_loc.get(loc, "")
            translated_segments.append({**seg, "translation": trans, "text": trans})

        review_rows: List[Dict[str, Any]] = []
        status.text("Running deterministic review...")
        for idx, seg in enumerate(translated_segments, start=1):
            review_rows.extend(deterministic_checks(seg, rules, enable_zwnj=True))
            progress.progress(0.45 + (idx / max(len(translated_segments), 1)) * 0.15)
        if not openai_client:
            review_rows.extend(build_offline_translation_review_rows(segments, translations_by_loc))

        if review_with_gemini:
            status.text("Running independent review...")
            total_review_batches = max(1, (len(translated_segments) + int(settings["batch_size"]) - 1) // int(settings["batch_size"]))
            for b in range(total_review_batches):
                batch = translated_segments[b * int(settings["batch_size"]):(b + 1) * int(settings["batch_size"])]
                status.text(f"Review batch {b + 1}/{total_review_batches}...")
                gemini_errors = gemini_review_translations(gemini_client, settings["gemini_model"], batch, target_language, settings["domain"], rules)
                loc_to_seg = {s["location"]: s for s in batch}
                for err in gemini_errors:
                    loc = err.get("location", "")
                    seg = loc_to_seg.get(loc, {"location": loc, "source": "", "translation": "", "sheet": ""})
                    review_rows.append(make_report_row(
                        seg,
                        err.get("error_type", "Independent Review"),
                        err.get("severity", "Review"),
                        err.get("wrong_part", ""),
                        err.get("suggestion", ""),
                        err.get("explanation", ""),
                        "Independent Review",
                        "Reviewer",
                        err.get("confidence", "Medium"),
                    ))
                    if apply_gemini_suggestions and err.get("suggestion") and loc in translations_by_loc:
                        translations_by_loc[loc] = err["suggestion"]
                progress.progress(0.60 + ((b + 1) / total_review_batches) * 0.35)

        status.text("Building output file...")
        output_bytes = b""
        output_name = "errorsweep_pro_" + uploaded_file.name
        mime_type = "text/csv"

        if lower.endswith(".xlsx") and workbook is not None:
            for seg in segments:
                loc = seg["location"]
                if loc in translation_col_map:
                    ws_name, row_num, col_idx = translation_col_map[loc]
                    if col_idx is None:
                        continue
                    workbook[ws_name].cell(row=row_num, column=col_idx + 1).value = translations_by_loc.get(loc, "")
            highlight_excel_cells(cell_map, review_rows)
            issue_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation", "Check Source", "Rule Source", "Confidence"]
            status_rows = build_segment_status_rows(translated_segments, review_rows, checked_by="Rules + Independent Review")
            status_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Review Status", "Issue Count", "Highest Severity", "Error Types", "Suggestion Summary", "Explanation Summary", "Checked By"]
            add_report_sheet_to_workbook(workbook, "All Segment Review", status_rows, status_headers)
            add_report_sheet_to_workbook(workbook, "ErrorSweep Pro Review", review_rows, issue_headers)
            bio = io.BytesIO()
            workbook.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".csv") and dataframe is not None:
            out_col = "AI Translation"
            if "AI Translation" not in dataframe.columns:
                dataframe[out_col] = ""
            for seg in segments:
                dataframe.at[seg["row"], out_col] = translations_by_loc.get(seg["location"], "")
            output_bytes = dataframe.to_csv(index=False).encode("utf-8-sig")
            mime_type = "text/csv"
            output_name = "errorsweep_pro_translated_" + re.sub(r"\.[^.]+$", ".csv", uploaded_file.name)
        elif lower.endswith(".docx") and doc is not None:
            for seg in segments:
                target_info = para_map.get(seg["location"])
                write_docx_translation_target(target_info, translations_by_loc.get(seg["location"], ""))
            bio = io.BytesIO()
            doc.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".json") and json_obj is not None:
            output_bytes = build_translated_json_bytes(json_obj, json_path_map, translations_by_loc)
            mime_type = "application/json"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".xlz") and xlz_package is not None:
            output_bytes = build_translated_xlz_bytes(xlz_package, xlz_target_map, translations_by_loc)
            mime_type = "application/zip"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith((".xml", ".xliff", ".xlf", ".sdlxliff", ".mqxliff")) and xml_tree is not None:
            output_bytes = build_translated_xml_bytes(xml_tree, xml_target_map, translations_by_loc)
            mime_type = "application/xml"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".srt") and text_original is not None:
            output_bytes = build_translated_srt_bytes(text_original, srt_line_map, translations_by_loc)
            mime_type = "text/plain"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif is_text_like_extension(uploaded_file.name) and text_original is not None:
            output_bytes = build_preserved_text_translation(text_original, segments, translations_by_loc)
            mime_type = "text/plain"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        else:
            # For PDFs and truly unknown/binary formats, safely return an Excel translation table.
            # Rebuilding a binary/PDF in the exact same format requires a dedicated renderer and is not safe to fake.
            table = []
            for seg in segments:
                table.append({"Location": seg["location"], "Source": seg.get("source") or seg.get("text", ""), "Translation": translations_by_loc.get(seg["location"], "")})
            output_bytes = build_excel_report_bytes(
                issue_rows=[],
                status_rows=[],
                extraction_logs=logs + ["Exact same-format rebuild is unavailable for this file type; returned an Excel translation table instead."],
                translation_rows=table,
                title="ErrorSweep Pro Translations",
            )
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_pro_translations_" + re.sub(r"\.[^.]+$", ".xlsx", uploaded_file.name)

        progress.progress(1.0)
        status.text(f"Pro workflow complete in {round(time.time() - start, 2)} seconds.")

        refreshed_profile = profile
        charge_ok, charge_msg, refreshed_profile = consume_user_credits(
            user_id=user_id,
            credits=credits_needed,
            workflow="pro",
            file_name=uploaded_file.name,
            segment_count=len(segments),
            metadata={
                "review_issues": len(review_rows),
                "rules_zip": bool(rules_zip),
                "independent_review": bool(review_with_gemini),
                "engine": "managed_ai" if using_managed_pro_engine else "offline_reference",
                "api_used": bool(using_managed_pro_engine),
            },
        )
        if not charge_ok:
            st.error(f"Could not deduct app credits, so the output cannot be released. {charge_msg}")
            st.stop()
        if refreshed_profile:
            st.session_state["sb_profile"] = refreshed_profile
        st.success(f"App credits charged: {credits_needed}. Remaining credits: {remaining_credits(refreshed_profile or profile)}")
        log_report_record(user_id, "pro", uploaded_file.name, len(segments), len(review_rows), output_name, credits_needed)

        st.markdown("### Translation Preview")
        preview = []
        for seg in translated_segments[:50]:
            preview.append({"Location": seg["location"], "Source": truncate(seg.get("source") or seg.get("text", ""), 300), "Translation": truncate(translations_by_loc.get(seg["location"], ""), 300)})
        st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

        status_rows_for_ui = build_segment_status_rows(translated_segments, review_rows, checked_by="Rules + Independent Review")
        st.markdown("### Segment Coverage")
        c1, c2, c3 = st.columns(3)
        c1.metric("Segments translated/reviewed", len(status_rows_for_ui))
        c2.metric("Segments with issues", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Needs Review"))
        c3.metric("Segments passed", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Pass"))
        with st.expander("All Segment Review Preview", expanded=False):
            st.dataframe(pd.DataFrame(status_rows_for_ui).head(200), use_container_width=True, hide_index=True)

        render_report(review_rows, "Independent Review Report")
        st.download_button("Download Translated Output", output_bytes, file_name=output_name, mime=mime_type, use_container_width=True)
        translation_rows_for_report = [
            {
                "Location": seg["location"],
                "Source": truncate(seg.get("source") or seg.get("text", ""), 1000),
                "Translation": truncate(translations_by_loc.get(seg["location"], ""), 1000),
            }
            for seg in translated_segments
        ]
        st.download_button(
            "Download Excel Translation + Review Report",
            build_excel_report_bytes(
                issue_rows=review_rows,
                status_rows=status_rows_for_ui,
                extraction_logs=logs,
                translation_rows=translation_rows_for_report,
                title="ErrorSweep Pro Translation + Review Report",
            ),
            file_name="errorsweep_pro_excel_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_admin_page(profile: Optional[Dict[str, Any]]) -> None:
    st.markdown("## Admin — User Management")
    st.caption("Manage users, plans, credits, and recent jobs. This page is visible only to emails listed in ERRORSWEEP_ADMIN_EMAILS.")

    if not is_admin_user():
        st.error("You do not have admin access.")
        return

    if not supabase_service_configured():
        st.error("Supabase service role is not configured. Add SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets.")
        return

    summary = admin_usage_summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users", summary["users"])
    c2.metric("Recent Jobs", summary["jobs"])
    c3.metric("Credits Used", summary["credits_used"])
    c4.metric("Credits Allocated", summary["credits_allocated"])

    st.divider()
    st.markdown("### Find user")
    search_email = st.text_input("Search by email", placeholder="user@example.com")
    profiles = admin_list_profiles(search_email, limit=50)

    if profiles:
        display_df = pd.DataFrame(profiles)
        preferred_cols = ["email", "plan", "monthly_credits", "used_credits", "total_files_processed", "created_at", "id"]
        cols = [col for col in preferred_cols if col in display_df.columns]
        st.dataframe(display_df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("No users found for the current search.")

    st.divider()
    st.markdown("### Upgrade / adjust credits")
    with st.form("admin_update_user_form"):
        target_email = st.text_input("User email to update", value=search_email or "")
        new_plan = st.selectbox("Plan", ["trial", "errorsweep", "pro", "agency", "enterprise"], index=2)
        monthly_credits = st.number_input("Monthly credits", min_value=0, max_value=1000000, value=600, step=25)
        used_credits = st.number_input("Used credits", min_value=0, max_value=1000000, value=0, step=1)
        reset_used = st.checkbox("Reset used credits to 0", value=True)
        submitted = st.form_submit_button("Update user", type="primary", use_container_width=True)

    if submitted:
        target = admin_get_profile_by_email(target_email)
        if not target:
            st.error("User profile not found. Ask the user to sign up/login once, then try again.")
        else:
            updates = {
                "plan": new_plan,
                "monthly_credits": int(monthly_credits),
                "used_credits": 0 if reset_used else int(used_credits),
            }
            ok, msg, refreshed = admin_update_profile(target["id"], updates)
            if ok:
                st.success(msg)
                if refreshed:
                    st.json({k: refreshed.get(k) for k in ["email", "plan", "monthly_credits", "used_credits"]})
            else:
                st.error(msg)

    st.divider()
    st.markdown("### Add bonus credits")
    with st.form("admin_bonus_credits_form"):
        bonus_email = st.text_input("User email", key="bonus_email")
        bonus = st.number_input("Bonus credits to add to monthly credits", min_value=1, max_value=100000, value=100, step=10)
        bonus_submit = st.form_submit_button("Add bonus credits", use_container_width=True)

    if bonus_submit:
        target = admin_get_profile_by_email(bonus_email)
        if not target:
            st.error("User profile not found.")
        else:
            new_monthly = int(target.get("monthly_credits") or 0) + int(bonus)
            ok, msg, refreshed = admin_update_profile(target["id"], {"monthly_credits": new_monthly})
            if ok:
                st.success(f"Added {bonus} credits. New monthly credits: {new_monthly}")
            else:
                st.error(msg)

    st.divider()
    st.markdown("### Job history")
    job_email = st.text_input("Filter jobs by user email", value=search_email or "", key="job_email_filter")
    job_user_id = None
    if job_email.strip():
        target = admin_get_profile_by_email(job_email)
        if target:
            job_user_id = target.get("id")
    jobs = admin_list_jobs(user_id=job_user_id, limit=100)
    if jobs:
        st.dataframe(pd.DataFrame(jobs), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs found.")

    st.divider()
    st.markdown("### Master access reminder")
    st.code('ERRORSWEEP_ADMIN_EMAILS = "your-email@example.com,adapalanaveen401@gmail.com"', language="toml")


def render_dashboard() -> None:
    init_page_state()
    user = get_current_user()
    user_id = user.get("id")
    profile = ensure_profile(user)
    if profile:
        st.session_state["sb_profile"] = profile

    render_top_account_bar(profile)
    page = render_top_nav()
    settings = get_page_settings()

    if page == "Dashboard":
        render_dashboard_page(user_id, profile, settings)
    elif page == "ErrorSweep":
        render_errorsweep_page(user_id, profile, settings)
    elif page == "ErrorSweep Pro":
        render_errorsweep_pro_page(user_id, profile, settings)
    elif page == "Billing":
        render_billing_page(profile)
    elif page == "Account":
        render_account_page(profile)
    elif page == "Admin":
        render_admin_page(profile)


if not is_authenticated():
    render_login_page()
else:
    render_dashboard()
