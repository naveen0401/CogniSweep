import streamlit as st
import pandas as pd
import io
import os
import re
import json
import time
import zipfile
from typing import Any, Dict, List, Tuple, Optional
from html import escape

from openai import OpenAI
from openpyxl import load_workbook
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
# QA-only + optional company rules ZIP
# Translation with OpenAI + Gemini review
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
</style>
""",
    unsafe_allow_html=True,
)


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
    "instruction", "calculation", "error_count", "error counts", "pull-out", "pull_out", "summary", "dashboard"
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


def get_openai_client() -> Optional[OpenAI]:
    key = get_secret_value("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key, timeout=60, max_retries=1)


def get_gemini_client():
    key = get_secret_value("GEMINI_API_KEY")
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


def visible_invisibles(text: Any) -> str:
    text = str(text) if text is not None else ""
    return (
        text.replace("\u200C", "⟨ZWNJ⟩")
        .replace("\u200B", "⟨ZWSP⟩")
        .replace("\u200D", "⟨ZWJ⟩")
        .replace("\u00A0", "⟨NBSP⟩")
    )


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
    headers_lower = [str(h).lower().strip() for h in headers]

    def find_by_hint(hint: str) -> Optional[int]:
        if not hint:
            return None
        h = hint.lower().strip()
        try:
            idx = int(h)
            if 1 <= idx <= len(headers):
                return idx - 1
            if 0 <= idx < len(headers):
                return idx
        except Exception:
            pass
        for i, col in enumerate(headers_lower):
            if col == h or h in col:
                return i
        return None

    src_idx = find_by_hint(source_hint)
    tgt_idx = find_by_hint(target_hint)

    if src_idx is None:
        for keyword in SOURCE_KEYWORDS_STRONG:
            for i, col in enumerate(headers_lower):
                if keyword == col or keyword in col:
                    # Avoid bad metadata headers like "client"
                    if col in ["client", "project id", "date", "language"]:
                        continue
                    src_idx = i
                    break
            if src_idx is not None:
                break

    if tgt_idx is None:
        for keyword in TARGET_KEYWORDS_STRONG:
            for i, col in enumerate(headers_lower):
                if keyword == col or keyword in col:
                    if col in ["client", "project id", "date", "language"]:
                        continue
                    tgt_idx = i
                    break
            if tgt_idx is not None:
                break

    return src_idx, tgt_idx


def find_excel_header_row(rows: List[Any], source_hint: str, target_hint: str, need_target: bool = True) -> Tuple[int, List[str], Optional[int], Optional[int]]:
    max_scan = min(len(rows), 25)
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
            tgt_name = headers[tgt_idx] if tgt_idx is not None and tgt_idx < len(headers) else "OpenAI Translation"
            logs.append(f"{ws.title}: column mode [{src_name}] -> [{tgt_name}]")

            # For Pro, create output translation column if target column is missing.
            output_col_idx = tgt_idx
            if mode == "pro" and output_col_idx is None:
                output_col_idx = ws.max_column
                ws.cell(row=header_idx + 1, column=output_col_idx + 1).value = "OpenAI Translation"
                logs.append(f"{ws.title}: created output column [OpenAI Translation]")

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
                if len(segments) >= max_segments:
                    return wb, segments, cell_map, translation_col_map, logs

        elif deep_scan:
            logs.append(f"{ws.title}: no source/target columns found; deep-scan text cells")
            for row in rows:
                for cell in row:
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
                        if len(segments) >= max_segments:
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
        tgt_col = df.columns[tgt_idx] if tgt_idx is not None else "OpenAI Translation"
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
            if len(segments) >= max_segments:
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
                    if len(segments) >= max_segments:
                        return df, segments, logs
    else:
        logs.append("CSV: no usable columns found")

    return df, segments, logs


def extract_text_segments(uploaded_file, mode: str, max_segments: int):
    data = uploaded_file.read()
    text = data.decode("utf-8", errors="ignore")
    lower_name = uploaded_file.name.lower()

    # Basic XLIFF/XML pair extraction.
    if lower_name.endswith((".xliff", ".xlf", ".xml")):
        pairs = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
            for elem in root.iter():
                children = list(elem)
                src_el, tgt_el = None, None
                for ch in children:
                    tag = ch.tag.split("}")[-1].lower()
                    if tag == "source":
                        src_el = ch
                    elif tag == "target":
                        tgt_el = ch
                if src_el is not None:
                    src = normalize_text("".join(src_el.itertext()))
                    tgt = normalize_text("".join(tgt_el.itertext())) if tgt_el is not None else ""
                    if src:
                        pairs.append((src, tgt))
        except Exception:
            pairs = []
        if pairs:
            segments = []
            for i, (src, tgt) in enumerate(pairs[:max_segments], start=1):
                if mode == "qa" and not tgt:
                    continue
                segments.append({
                    "id": len(segments) + 1,
                    "file_type": "text",
                    "sheet": "File",
                    "location": f"Segment {i}",
                    "source": src,
                    "translation": tgt,
                    "text": tgt if mode == "qa" else src,
                    "mode": "bilingual" if tgt else "source_only",
                })
            return text, segments, ["XML/XLIFF: extracted source/target pairs"]

    lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 2]
    segments = []
    # Tab-separated bilingual pairs
    for i, line in enumerate(lines[:max_segments], start=1):
        parts = line.split("\t")
        if len(parts) >= 2 and len(parts[0].strip()) > 1 and len(parts[1].strip()) > 1:
            segments.append({
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {i}",
                "source": parts[0].strip(),
                "translation": parts[1].strip(),
                "text": parts[1].strip() if mode == "qa" else parts[0].strip(),
                "mode": "bilingual",
            })

    if len(segments) >= max(1, min(5, len(lines))):
        return text, segments[:max_segments], ["Text: detected tab-separated source/translation pairs"]

    if mode == "pro":
        for i, line in enumerate(lines[:max_segments], start=1):
            segments.append({
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {i}",
                "source": line,
                "translation": "",
                "text": line,
                "mode": "source_only",
            })
    else:
        for i, line in enumerate(lines[:max_segments], start=1):
            segments.append({
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {i}",
                "source": "",
                "translation": line,
                "text": line,
                "mode": "monolingual",
            })

    return text, segments[:max_segments], ["Text: line-based mode"]


def extract_docx_segments(uploaded_file, mode: str, max_segments: int):
    doc = Document(uploaded_file)
    segments = []
    para_map = {}
    for i, p in enumerate(doc.paragraphs, start=1):
        text = normalize_text(p.text)
        if text and len(text) > 2:
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
            para_map[seg["location"]] = p
            if len(segments) >= max_segments:
                break
    return doc, segments, para_map, ["DOCX: paragraph mode"]


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


def deterministic_checks(segment: Dict[str, Any], rules: Dict[str, Any], enable_zwnj: bool = True) -> List[Dict[str, Any]]:
    rows = []
    source = normalize_text(segment.get("source", ""))
    target = normalize_text(segment.get("translation", "") or segment.get("text", ""))

    if not target:
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

    # Punctuation preservation where appropriate
    src_end = source[-1:] if source else ""
    tgt_end = target[-1:] if target else ""
    if source and src_end in ".!?;:" and tgt_end not in ".!?;:":
        rows.append(make_report_row(
            segment, "Punctuation", "Minor", tgt_end or "missing ending punctuation", target + src_end,
            f"Source ends with '{src_end}', but translation does not preserve ending punctuation.", "Rule Engine"
        ))

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

    quote_chars = ['"', "'", "“", "”", "‘", "’"]
    if target.count('"') % 2 != 0 or target.count("'") % 2 != 0:
        rows.append(make_report_row(
            segment, "Formatting", "Minor", "Unbalanced quote", target,
            "Unbalanced quote mark detected.", "Rule Engine"
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
# OPENAI / GEMINI CALLS
# ==========================================================

def openai_json(client: OpenAI, model: str, instructions: str, prompt: str, max_output_tokens: int = 3000) -> List[Dict[str, Any]]:
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
    client: OpenAI,
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

    style_line = "Include terminology/style suggestions only when clearly supported by source or company rules." if include_style else "Do NOT include subjective terminology/style suggestions unless they are clearly supported by provided company rules."

    instructions = (
        "You are ErrorSweep, a professional linguistic QA engine. "
        "Return only valid JSON. Do not include markdown. "
        "Be precise and do not invent issues."
    )

    prompt = f"""
Domain: {domain}
Strictness: {STRICTNESS_GUIDE[strictness]}
Style guidance: {style_line}

Review the following segments for real QA errors.

{chr(10).join(numbered_parts)}

Check these categories:
- Accuracy / meaning mismatch
- Grammar
- Spelling
- Mixed script or mixed language
- Terminology only if clear
- Fluency/readability
- Formatting that deterministic checks may miss
- Client rules from ZIP, if provided

Return ONLY this JSON array:
[
  {{
    "location": "exact location from input",
    "language_detected": "detected language or Unknown",
    "error_type": "Accuracy|Grammar|Spelling|Mixed Script|Terminology|Style & Tone|Readability|Formatting|Client Rule",
    "severity": "Minor|Major|Critical",
    "wrong_part": "specific wrong fragment",
    "suggestion": "corrected suggestion",
    "explanation": "brief reason",
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
            "wrong_part": "OpenAI API call failed",
            "suggestion": "Retry with fewer segments or check API key/settings.",
            "explanation": str(e)[:250],
            "rule_source": "System",
            "confidence": "Low",
        }]

    rows = []
    loc_to_seg = {s.get("location", ""): s for s in segments}
    for err in raw:
        loc = err.get("location", "")
        seg = loc_to_seg.get(loc, {})
        rows.append(make_report_row(
            seg,
            err.get("error_type", "AI QA"),
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
    client: OpenAI,
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
Review OpenAI translations into {target_language}.
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
            "error_type": "Gemini API Warning",
            "severity": "Review",
            "wrong_part": "Gemini review failed",
            "suggestion": "Retry with fewer segments or check GEMINI_API_KEY.",
            "explanation": str(e)[:250],
            "confidence": "Low",
        }]


# ==========================================================
# OUTPUT BUILDERS
# ==========================================================

def add_report_sheet_to_workbook(wb, sheet_name: str, report_rows: List[Dict[str, Any]], headers: List[str]):
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)
    ws.append(headers)
    for row in report_rows:
        ws.append([row.get(h, "") for h in headers])
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
# APP UI
# ==========================================================

st.markdown(
    """
<div class="hero">
    <div class="hero-title">ErrorSweep</div>
    <div class="hero-sub">QA suggestions, company rules ZIP, translation, and independent AI review</div>
    <div class="hero-badge">ErrorSweep = QA only · ErrorSweep Pro = OpenAI translation + Gemini review</div>
</div>
""",
    unsafe_allow_html=True,
)

mode_choice = st.radio(
    "Choose version",
    ["ErrorSweep — QA Run + Suggestions", "ErrorSweep Pro — Translate with OpenAI + Review with Gemini"],
    horizontal=True,
)

with st.sidebar:
    st.markdown("### Product Settings")

    domain = st.selectbox(
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
    )

    strictness = st.select_slider(
        "QA Strictness",
        options=["Lenient", "Standard", "Strict", "Very Strict"],
        value="Strict",
    )

    max_segments = st.number_input("Max total segments", min_value=5, max_value=500, value=60)
    batch_size = st.number_input("Segments per AI call", min_value=5, max_value=50, value=20)

    st.divider()
    st.markdown("### File Detection")
    source_col_hint = st.text_input("Source column name/index", value="", placeholder="Source Text or 2")
    target_col_hint = st.text_input("Translation column name/index", value="", placeholder="Original Translation or 3")
    skip_non_content = st.checkbox("Skip non-content sheets", value=True)
    deep_scan = st.checkbox("Deep scan if columns are not found", value=False)

    st.divider()
    st.markdown("### AI Models")
    openai_model = st.selectbox("OpenAI model", [DEFAULT_OPENAI_MODEL, "gpt-4.1-mini", "gpt-4o"], index=0)
    gemini_model = st.selectbox("Gemini review model", [DEFAULT_GEMINI_MODEL, "gemini-2.5-pro"], index=0)

openai_client = get_openai_client()
gemini_client = get_gemini_client()

if openai_client is None:
    st.warning("OPENAI_API_KEY is not set. Add it in Streamlit Secrets to use AI features.")

col_a, col_b = st.columns([2, 1])
with col_a:
    uploaded_file = st.file_uploader(
        "Upload file",
        type=["xlsx", "csv", "txt", "json", "xml", "xliff", "xlf", "srt", "docx"],
    )
    rules_zip = st.file_uploader(
        "Upload Rules ZIP (optional: style guide, DNT list, glossary, instructions, references)",
        type=["zip"],
    )
with col_b:
    st.markdown("#### What this app uses")
    st.write("Rules engine: spacing, punctuation, placeholders, numbers, ZWNJ, glossary, DNT")
    st.write("OpenAI: QA suggestions and translation")
    st.write("Gemini: independent review for Pro")

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

# ==========================================================
# ERROR SWEEP QA ONLY
# ==========================================================

if mode_choice.startswith("ErrorSweep —"):
    st.markdown("## ErrorSweep — QA Run + Correct Suggestions")
    st.caption("Use this version for reviewing existing translations. Rules ZIP is optional. If no ZIP is uploaded, OpenAI uses general QA rules.")

    q1, q2, q3 = st.columns(3)
    with q1:
        run_rules = st.checkbox("Run deterministic rules", value=True)
        run_zwnj = st.checkbox("Check ZWNJ", value=True)
    with q2:
        run_ai = st.checkbox("Run OpenAI QA suggestions", value=True)
        include_ai_style = st.checkbox("Allow subjective AI style/terminology suggestions", value=False)
    with q3:
        output_highlighted = st.checkbox("Highlight Excel output", value=True)

    run = st.button("Run ErrorSweep QA", type="primary", use_container_width=True, disabled=not uploaded_file)

    if uploaded_file and run:
        if run_ai and openai_client is None:
            st.error("OpenAI key is missing. Disable OpenAI QA or add OPENAI_API_KEY in Streamlit Secrets.")
            st.stop()

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

        # Extract segments
        if lower.endswith(".xlsx"):
            workbook, segments, cell_map, _, logs = extract_excel_segments(
                uploaded_file, source_col_hint, target_col_hint, "qa", int(max_segments), skip_non_content, deep_scan
            )
        elif lower.endswith(".csv"):
            _, segments, logs = extract_csv_segments(uploaded_file, source_col_hint, target_col_hint, "qa", int(max_segments), deep_scan)
        elif lower.endswith(".docx"):
            _, segments, _, logs = extract_docx_segments(uploaded_file, "qa", int(max_segments))
        else:
            _, segments, logs = extract_text_segments(uploaded_file, "qa", int(max_segments))

        with st.expander("Extraction log", expanded=True):
            for log in logs:
                st.write(log)
            st.info(f"Found {len(segments)} segment(s) to check.")

        if not segments:
            st.error("No segments found. Try setting source/translation column names in the sidebar or enable deep scan.")
            st.stop()

        # Rule engine
        if run_rules:
            status.text("Running deterministic checks...")
            for idx, seg in enumerate(segments, start=1):
                report_rows.extend(deterministic_checks(seg, rules, enable_zwnj=run_zwnj))
                progress.progress(min(idx / max(len(segments), 1) * 0.35, 0.35))

        # AI QA
        if run_ai:
            status.text("Running OpenAI QA suggestions...")
            total_batches = max(1, (len(segments) + int(batch_size) - 1) // int(batch_size))
            for b in range(total_batches):
                batch = segments[b * int(batch_size):(b + 1) * int(batch_size)]
                status.text(f"OpenAI QA batch {b + 1}/{total_batches}...")
                report_rows.extend(ai_qa_batch(openai_client, openai_model, batch, rules, domain, strictness, include_ai_style))
                progress.progress(0.35 + ((b + 1) / total_batches) * 0.60)

        progress.progress(1.0)
        status.text(f"QA complete in {round(time.time() - start, 2)} seconds.")

        # Output
        if lower.endswith(".xlsx") and workbook is not None:
            if output_highlighted:
                highlight_excel_cells(cell_map, report_rows)
            headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation", "Check Source", "Rule Source", "Confidence"]
            add_report_sheet_to_workbook(workbook, "ErrorSweep Report", report_rows, headers)
            bio = io.BytesIO()
            workbook.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_reviewed_" + uploaded_file.name
        else:
            output_bytes = report_csv_bytes(report_rows)
            mime_type = "text/csv"
            output_name = "errorsweep_report_" + re.sub(r"\.[^.]+$", ".csv", uploaded_file.name)

        render_report(report_rows, "ErrorSweep QA Report")
        st.download_button("Download ErrorSweep Output", output_bytes, file_name=output_name, mime=mime_type, use_container_width=True)

# ==========================================================
# ERROR SWEEP PRO — TRANSLATE + REVIEW
# ==========================================================

else:
    st.markdown("## ErrorSweep Pro — Translate with OpenAI + Review with Gemini")
    st.caption("Use this version to translate source content with OpenAI, review it independently with Gemini, and export a translated file + review report.")

    p1, p2, p3 = st.columns(3)
    with p1:
        target_language = st.text_input("Target language", value="Telugu")
    with p2:
        apply_gemini_suggestions = st.checkbox("Apply Gemini suggestions to output", value=False)
    with p3:
        review_with_gemini = st.checkbox("Review with Gemini", value=True)

    run_pro = st.button("Run ErrorSweep Pro", type="primary", use_container_width=True, disabled=not uploaded_file)

    if uploaded_file and run_pro:
        if openai_client is None:
            st.error("OPENAI_API_KEY is missing. Add it in Streamlit Secrets.")
            st.stop()
        if review_with_gemini and gemini_client is None:
            st.error("GEMINI_API_KEY is missing or google-genai is not installed. Add GEMINI_API_KEY in Streamlit Secrets or disable Gemini review.")
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
        cell_map = {}
        translation_col_map = {}
        para_map = {}

        if lower.endswith(".xlsx"):
            workbook, segments, cell_map, translation_col_map, logs = extract_excel_segments(
                uploaded_file, source_col_hint, target_col_hint, "pro", int(max_segments), skip_non_content, deep_scan
            )
        elif lower.endswith(".csv"):
            dataframe, segments, logs = extract_csv_segments(uploaded_file, source_col_hint, target_col_hint, "pro", int(max_segments), deep_scan)
        elif lower.endswith(".docx"):
            doc, segments, para_map, logs = extract_docx_segments(uploaded_file, "pro", int(max_segments))
        else:
            text_original, segments, logs = extract_text_segments(uploaded_file, "pro", int(max_segments))

        with st.expander("Extraction log", expanded=True):
            for log in logs:
                st.write(log)
            st.info(f"Found {len(segments)} segment(s) for translation.")

        if not segments:
            st.error("No source segments found. Try setting the source column name/index in the sidebar.")
            st.stop()

        # Translation
        status.text("Translating with OpenAI...")
        translations_by_loc: Dict[str, str] = {}
        total_batches = max(1, (len(segments) + int(batch_size) - 1) // int(batch_size))
        for b in range(total_batches):
            batch = segments[b * int(batch_size):(b + 1) * int(batch_size)]
            status.text(f"OpenAI translation batch {b + 1}/{total_batches}...")
            result = openai_translate_batch(openai_client, openai_model, batch, target_language, domain, rules)
            for item in result:
                loc = item.get("location", "")
                trans = item.get("translation", "")
                if loc and trans:
                    translations_by_loc[loc] = trans
            progress.progress(((b + 1) / total_batches) * 0.45)

        translated_segments = []
        for seg in segments:
            loc = seg["location"]
            trans = translations_by_loc.get(loc, "")
            translated_segments.append({**seg, "translation": trans, "text": trans})

        # Deterministic review of generated translations
        review_rows: List[Dict[str, Any]] = []
        status.text("Running deterministic review...")
        for idx, seg in enumerate(translated_segments, start=1):
            review_rows.extend(deterministic_checks(seg, rules, enable_zwnj=True))
            progress.progress(0.45 + (idx / max(len(translated_segments), 1)) * 0.15)

        # Gemini review
        if review_with_gemini:
            status.text("Reviewing with Gemini...")
            total_review_batches = max(1, (len(translated_segments) + int(batch_size) - 1) // int(batch_size))
            for b in range(total_review_batches):
                batch = translated_segments[b * int(batch_size):(b + 1) * int(batch_size)]
                status.text(f"Gemini review batch {b + 1}/{total_review_batches}...")
                gemini_errors = gemini_review_translations(gemini_client, gemini_model, batch, target_language, domain, rules)
                loc_to_seg = {s["location"]: s for s in batch}
                for err in gemini_errors:
                    loc = err.get("location", "")
                    seg = loc_to_seg.get(loc, {"location": loc, "source": "", "translation": "", "sheet": ""})
                    review_rows.append(make_report_row(
                        seg,
                        err.get("error_type", "Gemini Review"),
                        err.get("severity", "Review"),
                        err.get("wrong_part", ""),
                        err.get("suggestion", ""),
                        err.get("explanation", ""),
                        "Gemini Review",
                        "Gemini",
                        err.get("confidence", "Medium"),
                    ))
                    if apply_gemini_suggestions and err.get("suggestion") and loc in translations_by_loc:
                        translations_by_loc[loc] = err["suggestion"]
                progress.progress(0.60 + ((b + 1) / total_review_batches) * 0.35)

        # Build translated output
        status.text("Building output file...")
        output_bytes = b""
        output_name = "errorsweep_pro_" + uploaded_file.name
        mime_type = "text/csv"

        if lower.endswith(".xlsx") and workbook is not None:
            # Write translations to mapped cells.
            for seg in segments:
                loc = seg["location"]
                if loc in translation_col_map:
                    ws_name, row_num, col_idx = translation_col_map[loc]
                    if col_idx is None:
                        continue
                    workbook[ws_name].cell(row=row_num, column=col_idx + 1).value = translations_by_loc.get(loc, "")

            # Highlight cells with review issues.
            highlight_excel_cells(cell_map, review_rows)
            headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation", "Check Source", "Rule Source", "Confidence"]
            add_report_sheet_to_workbook(workbook, "ErrorSweep Pro Review", review_rows, headers)
            bio = io.BytesIO()
            workbook.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name

        elif lower.endswith(".csv") and dataframe is not None:
            # Add/update translation column.
            out_col = "OpenAI Translation"
            if "OpenAI Translation" not in dataframe.columns:
                dataframe[out_col] = ""
            for seg in segments:
                dataframe.at[seg["row"], out_col] = translations_by_loc.get(seg["location"], "")
            output_bytes = dataframe.to_csv(index=False).encode("utf-8-sig")
            mime_type = "text/csv"
            output_name = "errorsweep_pro_translated_" + re.sub(r"\.[^.]+$", ".csv", uploaded_file.name)

        elif lower.endswith(".docx") and doc is not None:
            # Append translation after each original paragraph for a readable translated DOCX.
            for seg in segments:
                p = para_map.get(seg["location"])
                if p is not None:
                    p.add_run("\n" + translations_by_loc.get(seg["location"], ""))
            bio = io.BytesIO()
            doc.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name

        else:
            # Translation table for text/json/xml/srt/xliff.
            table = []
            for seg in segments:
                table.append({
                    "Location": seg["location"],
                    "Source": seg.get("source") or seg.get("text", ""),
                    "Translation": translations_by_loc.get(seg["location"], ""),
                })
            output_bytes = pd.DataFrame(table).to_csv(index=False).encode("utf-8-sig")
            mime_type = "text/csv"
            output_name = "errorsweep_pro_translations_" + re.sub(r"\.[^.]+$", ".csv", uploaded_file.name)

        progress.progress(1.0)
        status.text(f"Pro workflow complete in {round(time.time() - start, 2)} seconds.")

        # Display translation preview and review report.
        st.markdown("### Translation Preview")
        preview = []
        for seg in translated_segments[:50]:
            preview.append({
                "Location": seg["location"],
                "Source": truncate(seg.get("source") or seg.get("text", ""), 300),
                "Translation": truncate(translations_by_loc.get(seg["location"], ""), 300),
            })
        st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

        render_report(review_rows, "Gemini / Rule Review Report")

        st.download_button("Download Translated Output", output_bytes, file_name=output_name, mime=mime_type, use_container_width=True)
        st.download_button("Download Review Report CSV", report_csv_bytes(review_rows), file_name="errorsweep_pro_review_report.csv", mime="text/csv", use_container_width=True)


if not uploaded_file:
    st.markdown(
        """
<div class="empty-state">
    <div style="font-family:'Space Mono',monospace; color:#a8acc8">Upload a file to begin</div>
    <div style="font-size:13px; margin-top:8px; color:#6b7280">Supports .xlsx · .csv · .docx · .txt · .xliff · .srt · .json · .xml</div>
    <div style="font-size:12px; margin-top:12px; color:#6b7280">Optional Rules ZIP can include style guides, DNT lists, glossary files, instructions, and reference documents.</div>
</div>
""",
        unsafe_allow_html=True,
    )
