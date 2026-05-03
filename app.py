import streamlit as st
import pandas as pd
import io
import time
import json
import os
import re
from openai import OpenAI
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.comments import Comment
from docx import Document


# ==============================
# Page config
# ==============================
st.set_page_config(page_title="ErrorSweep Pro", layout="wide")


# ==============================
# Styling
# ==============================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.hero {
    background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 50%, #16213e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 16px;
    padding: 34px;
    margin-bottom: 20px;
    text-align: center;
}

.hero-title {
    font-family: 'Space Mono', monospace;
    font-size: 42px;
    color: #00ff88;
    font-weight: 700;
    margin: 0;
}

.hero-sub {
    font-size: 15px;
    color: #a9a9c8;
    margin-top: 8px;
    font-weight: 300;
}

.hero-badge {
    display: inline-block;
    background: rgba(0,255,136,0.1);
    border: 1px solid rgba(0,255,136,0.3);
    color: #00ff88;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 12px;
    font-family: 'Space Mono', monospace;
    margin-top: 12px;
}

.error-card {
    background: #0f0f1a;
    border-left: 3px solid #ff4466;
    border-radius: 0 8px 8px 0;
    padding: 16px;
    margin-bottom: 12px;
}

.error-card.minor {
    border-left-color: #ffaa00;
}

.error-card.major {
    border-left-color: #ff4466;
}

.error-card.critical {
    border-left-color: #ff0044;
}

.error-type {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #8888aa;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.error-source {
    color: #777799;
    font-size: 12px;
    margin: 4px 0;
}

.error-before {
    color: #ff6680;
    font-size: 14px;
    margin: 6px 0 2px;
}

.error-after {
    color: #00ff88;
    font-size: 14px;
}

.severity-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-family: 'Space Mono', monospace;
    font-weight: 700;
}

.sev-minor {
    background: rgba(255,170,0,0.15);
    color: #ffaa00;
}

.sev-major {
    background: rgba(255,68,102,0.15);
    color: #ff4466;
}

.sev-critical {
    background: rgba(255,0,68,0.2);
    color: #ff0044;
}

.empty-state {
    text-align:center;
    padding:48px;
    color:#777;
    border: 1px dashed #2a2a4a;
    border-radius:12px;
}

.small-muted {
    color: #777;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)


# ==============================
# Hero
# ==============================
st.markdown("""
<div class="hero">
    <div class="hero-title">ErrorSweep Pro</div>
    <div class="hero-sub">Fast AI linguistic QA for source-vs-translation review</div>
    <div class="hero-badge">Fast mode · Rule checks · ZWNJ detection · Batched AI calls</div>
</div>
""", unsafe_allow_html=True)


# ==============================
# Constants
# ==============================
HIGHLIGHT_FILL = PatternFill(start_color="FFF59D", end_color="FFF59D", fill_type="solid")
HEADER_FILL = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
HEADER_FONT = Font(bold=True)

REPORT_SHEETS = {"ErrorSweep Report", "Correction Report", "Remaining Errors"}
COMMON_SKIP_SHEETS = {"Calculation", "Error_counts", "Pull-out_data", "LQA Instructions", "Quality Evaluation"}

STRICTNESS_GUIDE = {
    "Lenient": "Only flag clear, obvious errors. Ignore minor style preferences.",
    "Standard": "Flag clear errors and notable quality issues.",
    "Strict": "Flag all errors including minor style, tone, consistency, and formatting issues.",
    "Very Strict": "Flag everything including subtle fluency, register, and micro-style issues."
}


# ==============================
# Secrets and client
# ==============================
def get_secret_value(name, default=None):
    env_value = os.environ.get(name)
    if env_value:
        return env_value

    try:
        secret_value = st.secrets.get(name)
        if secret_value:
            return secret_value
    except Exception:
        pass

    return default


api_key = get_secret_value("OPENAI_API_KEY")

if not api_key:
    st.error("OPENAI_API_KEY is not set.")
    st.info("In Streamlit Cloud: App Settings > Secrets")
    st.code('OPENAI_API_KEY = "your_new_openai_api_key_here"', language="toml")
    st.stop()

# Hard timeout + no automatic retry prevents the app from appearing stuck forever.
client = OpenAI(api_key=api_key, timeout=45.0, max_retries=0)


# ==============================
# Sidebar controls
# ==============================
with st.sidebar:
    st.markdown("### ErrorSweep Pro")
    st.caption("Fast OpenAI QA Engine")
    st.divider()

    st.markdown("**Recommended fast settings**")
    st.caption("Start with 20 segments and Fast model. Increase only after testing.")

    model = st.selectbox(
        "OpenAI model",
        [
            "gpt-4o-mini",
            "gpt-5.4-nano",
            "gpt-5.4-mini",
            "gpt-5.5"
        ],
        index=0,
        help="Use gpt-4o-mini first for compatibility and speed. Use GPT-5.4/5.5 only if your account supports them."
    )

    domain = st.selectbox(
        "Content domain",
        [
            "Auto-detect",
            "Software UI / App Strings",
            "Subtitles / Captions",
            "Legal / Compliance",
            "Medical / Healthcare",
            "Marketing / Ad Copy",
            "E-learning / Education",
            "General"
        ],
        index=1
    )

    strictness = st.select_slider(
        "QA strictness",
        options=["Lenient", "Standard", "Strict", "Very Strict"],
        value="Standard"
    )

    max_segments = st.number_input(
        "Max total segments to check",
        min_value=5,
        max_value=200,
        value=20,
        step=5,
        help="This is global across the whole file. Lower = faster."
    )

    batch_size = st.number_input(
        "Segments per AI call",
        min_value=5,
        max_value=50,
        value=25,
        step=5,
        help="Higher batching means fewer API calls and faster runs."
    )

    max_chars_per_segment = st.number_input(
        "Max chars per segment",
        min_value=100,
        max_value=1500,
        value=700,
        step=100,
        help="Long segments slow the API. This clips very long text safely for QA preview."
    )

    st.divider()
    st.markdown("**Excel/CSV column mapping**")
    source_col_hint = st.text_input("Source column name or number", value="", placeholder="Source Text or 1")
    target_col_hint = st.text_input("Translation column name or number", value="", placeholder="Original Translation or 2")

    st.divider()
    st.markdown("**Speed options**")
    skip_common_sheets = st.checkbox("Skip non-content sheets", value=True)
    allow_single_text_scan = st.checkbox(
        "Deep scan single text cells if no source/translation columns",
        value=False,
        help="This is slower. Keep OFF for client demos unless the file has no source/translation columns."
    )

    st.divider()
    st.markdown("**Detection options**")
    run_rule_checks = st.checkbox(
        "Run deterministic punctuation/spacing/ZWNJ checks",
        value=True,
        help="Fast rule-based checks for double spaces, missing punctuation, brackets, bullets, numbers, placeholders, and Telugu ZWNJ issues."
    )
    run_ai_checks = st.checkbox(
        "Run AI semantic/language QA",
        value=True,
        help="AI checks meaning, grammar, script, terminology, and fluency. Turn OFF to test formatting rules only."
    )

    include_ai_style_terminology = st.checkbox(
        "Include AI terminology/style suggestions",
        value=False,
        help=(
            "OFF by default because terminology/style suggestions can be subjective. "
            "Keep OFF for reliable reports; turn ON only for reviewer-style analysis."
        )
    )

    st.divider()
    st.markdown("**Supported formats**")
    st.caption(".xlsx, .csv, .txt, .json, .xml, .xliff, .srt, .docx")


# ==============================
# Utility functions
# ==============================
def normalize_text(text):
    """
    Normalize visible spacing but preserve ZWNJ (U+200C).
    Earlier versions removed ZWNJ, which made ZWNJ QA impossible.
    """
    text = str(text)
    text = text.replace("\u00A0", " ")
    # Remove zero-width space and zero-width joiner for matching, but keep ZWNJ.
    for ch in ["\u200B", "\u200D"]:
        text = text.replace(ch, "")
    return text.strip()


def truncate_text(text, limit):
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."


def style_header(sheet):
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT


def extract_json_array(raw_text):
    text = (raw_text or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


def safe_output_text(response):
    # The SDK exposes output_text for normal text responses.
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text

    # Fallback for SDK response shapes.
    try:
        parts = []
        for item in response.output:
            for content in getattr(item, "content", []):
                if hasattr(content, "text"):
                    parts.append(content.text)
        return "\n".join(parts)
    except Exception:
        return ""


def build_report_row(sheet, location, language, source, translation, err):
    return {
        "Sheet": sheet,
        "Location": location,
        "Language": err.get("language_detected", language or "Unknown"),
        "Source Text": truncate_text(source or err.get("source", ""), 300),
        "Translation": truncate_text(translation or err.get("translation", err.get("text", "")), 300),
        "Error Type": err.get("error_type", ""),
        "Severity": err.get("severity", "Minor"),
        "Wrong Part": err.get("wrong_part", err.get("original", "")),
        "Suggestion": err.get("suggestion", ""),
        "Explanation": err.get("explanation", "")
    }


# ==============================
# Column detection
# ==============================
def clean_header_value(value):
    text = normalize_text(value).lower()
    text = text.replace("*", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_source_target_columns(headers, source_hint="", target_hint=""):
    """
    Strong header detection.
    Important: avoids false matches like:
    - Client -> English because "client" contains "en"
    - Source language / Target language metadata rows
    - Quality Evaluation formula rows
    """
    headers_clean = [clean_header_value(h) for h in headers]

    def by_hint(hint):
        if not hint:
            return None

        hint_clean = clean_header_value(hint)

        # Accept 1-based or 0-based indexes.
        try:
            idx = int(hint_clean)
            if 1 <= idx <= len(headers_clean):
                return idx - 1
            if 0 <= idx < len(headers_clean):
                return idx
        except ValueError:
            pass

        for i, h in enumerate(headers_clean):
            if h == hint_clean:
                return i

        for i, h in enumerate(headers_clean):
            if hint_clean and hint_clean in h:
                return i

        return None

    src_from_hint = by_hint(source_hint)
    tgt_from_hint = by_hint(target_hint)

    if src_from_hint is not None and tgt_from_hint is not None and src_from_hint != tgt_from_hint:
        return src_from_hint, tgt_from_hint

    # Strong source names. Do NOT include broad keywords like "en".
    source_exact = {
        "source text",
        "source",
        "source segment",
        "source string",
        "src text",
        "src"
    }

    source_contains = [
        "source text",
        "source segment",
        "source string"
    ]

    # Strong target names. Prefer original translation over suggested translation.
    target_priority = [
        "original translation",
        "translation",
        "target text",
        "target segment",
        "target string",
        "translated text",
        "localized text",
        "suggested translation",
        "target"
    ]

    def is_metadata_header(h):
        # These are form metadata rows, not the translation table header.
        metadata_terms = [
            "client",
            "project id",
            "date",
            "number of checked words",
            "source language",
            "target language",
            "review date",
            "word count"
        ]
        return any(term in h for term in metadata_terms)

    def is_source_header(h):
        if not h or is_metadata_header(h):
            return False
        if h in source_exact:
            return True
        return any(term in h for term in source_contains)

    def is_target_header(h):
        if not h or is_metadata_header(h):
            return False
        return any(term == h or term in h for term in target_priority)

    src_idx = None
    tgt_idx = None

    for i, h in enumerate(headers_clean):
        if is_source_header(h):
            src_idx = i
            break

    # Choose target by priority so Original Translation wins over Suggested Translation.
    for target_name in target_priority:
        for i, h in enumerate(headers_clean):
            if is_metadata_header(h):
                continue
            if target_name == h or target_name in h:
                tgt_idx = i
                break
        if tgt_idx is not None:
            break

    # If the user only gives one hint, infer the neighbor as a fallback.
    if src_idx is None and src_from_hint is not None:
        src_idx = src_from_hint
    if tgt_idx is None and tgt_from_hint is not None:
        tgt_idx = tgt_from_hint

    if src_idx is not None and tgt_idx is None:
        possible = src_idx + 1
        tgt_idx = possible if possible < len(headers_clean) else None

    if tgt_idx is not None and src_idx is None:
        possible = tgt_idx - 1
        src_idx = possible if possible >= 0 else None

    if src_idx is None or tgt_idx is None or src_idx == tgt_idx:
        return None, None

    return src_idx, tgt_idx

def find_excel_header_row(rows):
    max_scan = min(len(rows), 25)

    for row_index in range(max_scan):
        headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[row_index]]
        src_idx, tgt_idx = detect_source_target_columns(headers, source_col_hint, target_col_hint)

        if src_idx is not None and tgt_idx is not None:
            return row_index, headers, src_idx, tgt_idx

    if not rows:
        return 0, [], None, None

    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[0]]
    return 0, headers, None, None


# ==============================
# Segment collection
# ==============================
def collect_excel_segments(uploaded_file):
    uploaded_file.seek(0)
    wb = load_workbook(uploaded_file)
    segments = []
    cell_map = {}
    messages = []

    for ws in wb.worksheets:
        if ws.title in REPORT_SHEETS:
            continue

        if skip_common_sheets and ws.title in COMMON_SKIP_SHEETS:
            messages.append(f"Skipped sheet: {ws.title}")
            continue

        rows = list(ws.iter_rows(values_only=False))
        if not rows:
            continue

        header_row_index, header_row, src_idx, tgt_idx = find_excel_header_row(rows)

        if src_idx is not None and tgt_idx is not None:
            source_header = header_row[src_idx] if src_idx < len(header_row) else "Source"
            target_header = header_row[tgt_idx] if tgt_idx < len(header_row) else "Translation"
            messages.append(f"{ws.title}: bilingual mode [{source_header}] -> [{target_header}]")

            data_rows = rows[header_row_index + 1:]

            for absolute_row_index, row in enumerate(data_rows, start=header_row_index + 2):
                if len(segments) >= max_segments:
                    break

                if len(row) <= max(src_idx, tgt_idx):
                    continue

                src_val = truncate_text(row[src_idx].value or "", max_chars_per_segment)
                tgt_val = truncate_text(row[tgt_idx].value or "", max_chars_per_segment)

                if src_val and tgt_val and len(src_val) > 2 and not src_val.startswith("["):
                    loc = f"{ws.title}!Row {absolute_row_index}"
                    segments.append({
                        "mode": "bilingual",
                        "sheet": ws.title,
                        "location": loc,
                        "source": src_val,
                        "translation": tgt_val
                    })
                    cell_map[loc] = row[tgt_idx]

        elif allow_single_text_scan:
            messages.append(f"{ws.title}: single-text deep scan mode")
            for row in rows:
                for cell in row:
                    if len(segments) >= max_segments:
                        break
                    if cell.value and isinstance(cell.value, str) and len(cell.value.strip()) > 3:
                        loc = f"{ws.title}!{cell.coordinate}"
                        segments.append({
                            "mode": "monolingual",
                            "sheet": ws.title,
                            "location": loc,
                            "text": truncate_text(cell.value, max_chars_per_segment)
                        })
                        cell_map[loc] = cell
                if len(segments) >= max_segments:
                    break
        else:
            messages.append(f"{ws.title}: no source/translation columns found; skipped single-text scan")

        if len(segments) >= max_segments:
            break

    return wb, segments, cell_map, messages


def collect_csv_segments(uploaded_file):
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file)
    segments = []

    src_idx, tgt_idx = detect_source_target_columns(list(df.columns), source_col_hint, target_col_hint)

    if src_idx is not None and tgt_idx is not None:
        src_col = df.columns[src_idx]
        tgt_col = df.columns[tgt_idx]

        for i, row in df.iterrows():
            if len(segments) >= max_segments:
                break

            sv = truncate_text(row[src_col], max_chars_per_segment) if pd.notna(row[src_col]) else ""
            tv = truncate_text(row[tgt_col], max_chars_per_segment) if pd.notna(row[tgt_col]) else ""

            if sv and tv and len(sv) > 2:
                segments.append({
                    "mode": "bilingual",
                    "sheet": "CSV",
                    "location": f"Row {i + 2}",
                    "source": sv,
                    "translation": tv
                })
    elif allow_single_text_scan:
        for col in df.columns:
            for index, value in df[col].items():
                if len(segments) >= max_segments:
                    break
                if pd.notna(value) and isinstance(value, str) and len(str(value).strip()) > 3:
                    segments.append({
                        "mode": "monolingual",
                        "sheet": "CSV",
                        "location": f"Row {index + 2}, Column {col}",
                        "text": truncate_text(value, max_chars_per_segment)
                    })
            if len(segments) >= max_segments:
                break

    return df, segments


def collect_text_segments(uploaded_file):
    uploaded_file.seek(0)
    text = uploaded_file.read().decode("utf-8", errors="ignore")
    lines = [line.strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 3]

    segments = []
    possible_pairs = []

    for i, line in enumerate(lines[:max_segments]):
        parts = line.split("\t")
        if len(parts) >= 2 and len(parts[0].strip()) > 2 and len(parts[1].strip()) > 2:
            possible_pairs.append({
                "mode": "bilingual",
                "sheet": "File",
                "location": f"Line {i + 1}",
                "source": truncate_text(parts[0].strip(), max_chars_per_segment),
                "translation": truncate_text(parts[1].strip(), max_chars_per_segment)
            })

    if possible_pairs and len(possible_pairs) >= max(1, min(len(lines), max_segments) // 2):
        return possible_pairs[:max_segments]

    for i, line in enumerate(lines[:max_segments]):
        segments.append({
            "mode": "monolingual",
            "sheet": "File",
            "location": f"Line {i + 1}",
            "text": truncate_text(line, max_chars_per_segment)
        })

    return segments


def collect_docx_segments(uploaded_file):
    uploaded_file.seek(0)
    doc = Document(uploaded_file)
    segments = []

    for idx, p in enumerate(doc.paragraphs, start=1):
        if len(segments) >= max_segments:
            break
        text = p.text.strip()
        if text and len(text) > 3:
            segments.append({
                "mode": "monolingual",
                "sheet": "Document",
                "location": f"Paragraph {idx}",
                "text": truncate_text(text, max_chars_per_segment)
            })

    return segments



# ==============================
# Fast deterministic QA checks
# ==============================
def rule_clean(text):
    """Keep text readable for rule checks while preserving internal spaces and ZWNJ."""
    text = str(text or "")
    text = text.replace("\u00A0", " ")
    # Preserve ZWNJ (U+200C). It is meaningful in Telugu/Indic QA.
    for ch in ["\u200B", "\u200D"]:
        text = text.replace(ch, "")
    return text


def strip_closing_marks(text):
    return rule_clean(text).strip().rstrip('"\'”’)]}»›')


TERMINAL_PUNCT_EQUIV = {
    ".": {".", "।", "॥", "。"},
    "?": {"?", "؟", "？"},
    "!": {"!", "！"},
    ":": {":", "："},
    ";": {";", "；"},
}

QUOTE_CHARS = set(['"', "'", "“", "”", "‘", "’"])
BULLET_CHARS = {"•", "∙", "●", "○", "-", "–", "—", "*"}
PLACEHOLDER_PATTERN = re.compile(
    r"(\{\{[^}]+\}\}|\{\d+\}|%[sdif]|\$[A-Za-z_][A-Za-z0-9_]*|<[^>]+>|\[[A-Za-z0-9_]+\])"
)

ZWNJ = "\u200C"
ZWSP = "\u200B"
ZWJ = "\u200D"

TELUGU_ZWNJ_SUFFIXES = "లు|లను|ను|ని|తో|కు|కి|లో|గా|పై|వద్ద"
TELUGU_ZWNJ_PATTERNS = [
    (r"డాక్యుమెంట్(?!" + ZWNJ + r")(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "డాక్యుమెంట్" + ZWNJ, "డాక్యుమెంట్ + suffix"),
    (r"టెంప్లేట్(?!" + ZWNJ + r")(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "టెంప్లేట్" + ZWNJ, "టెంప్లేట్ + suffix"),
    (r"సెట్టింగ్(?!" + ZWNJ + r")(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "సెట్టింగ్" + ZWNJ, "సెట్టింగ్ + suffix"),
    (r"ట్రాకింగ్(?!" + ZWNJ + r")(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "ట్రాకింగ్" + ZWNJ, "ట్రాకింగ్ + suffix"),
    (r"కనెక్షన్(?!" + ZWNJ + r")(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "కనెక్షన్" + ZWNJ, "కనెక్షన్ + suffix"),
    (r"వెర్షన్(?!" + ZWNJ + r")(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "వెర్షన్" + ZWNJ, "వెర్షన్ + suffix"),
    (r"స్క్రీన్(?!" + ZWNJ + r")(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "స్క్రీన్" + ZWNJ, "స్క్రీన్ + suffix"),
    (r"ఫిట్(?!" + ZWNJ + r")(?=నెస్)", "ఫిట్" + ZWNJ, "ఫిట్ + నెస్"),
    (r"ఆన్(?!" + ZWNJ + r")(?=బోర్డింగ్)", "ఆన్" + ZWNJ, "ఆన్ + బోర్డింగ్"),
    (r"అప్(?!" + ZWNJ + r")(?=లోడ్)", "అప్" + ZWNJ, "అప్ + లోడ్"),
    (r"డాష్(?!" + ZWNJ + r")(?=బోర్డ్)", "డాష్" + ZWNJ, "డాష్ + బోర్డ్"),
    (r"పాస్(?!" + ZWNJ + r")(?=వర్డ్)", "పాస్" + ZWNJ, "పాస్ + వర్డ్"),
    # Common spacing/misspelling variants.
    (r"డాక్యుమెంట్\s+(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "డాక్యుమెంట్" + ZWNJ, "డాక్యుమెంట్ + suffix"),
    (r"టెంప్లేట్\s+(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "టెంప్లేట్" + ZWNJ, "టెంప్లేట్ + suffix"),
    (r"సెట్టింగ్\s+(?=" + TELUGU_ZWNJ_SUFFIXES + r")", "సెట్టింగ్" + ZWNJ, "సెట్టింగ్ + suffix"),
    (r"పాస్\s+వర్డ్", "పాస్" + ZWNJ + "వర్డ్", "పాస్ + వర్డ్"),
    (r"పాస్వర్డ్", "పాస్" + ZWNJ + "వర్డ్", "పాస్వర్డ్ -> పాస్⟨ZWNJ⟩వర్డ్"),
]


def show_invisible_chars(text):
    """Make invisible Unicode characters visible inside the report."""
    return (
        str(text)
        .replace(ZWNJ, "⟨ZWNJ⟩")
        .replace(ZWSP, "⟨ZWSP⟩")
        .replace(ZWJ, "⟨ZWJ⟩")
        .replace("\u00A0", "⟨NBSP⟩")
    )


def suggest_telugu_zwnj(text):
    """
    Suggests missing Telugu ZWNJ fixes for common UI/localization loanwords.
    Returns (fixed_text, labels).
    The report shows ⟨ZWNJ⟩ so reviewers can see the invisible character.
    """
    fixed = str(text or "")
    labels = []

    for pattern, replacement, label in TELUGU_ZWNJ_PATTERNS:
        new_fixed, count = re.subn(pattern, replacement, fixed)
        if count:
            fixed = new_fixed
            labels.append(label)

    return fixed, labels


def get_terminal_punctuation(text):
    cleaned = strip_closing_marks(text)
    if not cleaned:
        return ""
    last = cleaned[-1]
    return last if last in TERMINAL_PUNCT_EQUIV else ""


def has_equivalent_terminal_punctuation(target, source_punct):
    cleaned = strip_closing_marks(target)
    if not cleaned:
        return False
    return cleaned[-1] in TERMINAL_PUNCT_EQUIV.get(source_punct, {source_punct})


def first_visible_char(text):
    cleaned = rule_clean(text).strip()
    return cleaned[0] if cleaned else ""


def count_quote_like(text):
    return sum(1 for ch in rule_clean(text) if ch in QUOTE_CHARS)


def find_placeholders(text):
    return PLACEHOLDER_PATTERN.findall(rule_clean(text))


def make_rule_report(seg, error_type, severity, wrong_part, suggestion, explanation):
    source = seg.get("source", "")
    translation = seg.get("translation", seg.get("text", ""))
    sheet = seg.get("sheet", "")
    location = seg.get("location", "")
    return build_report_row(
        sheet=sheet,
        location=location,
        language="Rule Check",
        source=source,
        translation=translation,
        err={
            "language_detected": "Rule Check",
            "error_type": error_type,
            "severity": severity,
            "wrong_part": wrong_part,
            "suggestion": suggestion,
            "explanation": explanation,
        }
    )


def run_deterministic_checks(seg):
    """
    Fast rule-based checks catch issues that AI often misses:
    double spaces, missing ending punctuation, missing brackets, bullets, placeholders, and numbers.
    """
    rows = []
    is_bilingual = seg.get("mode") == "bilingual"
    source = rule_clean(seg.get("source", "")) if is_bilingual else ""
    target = rule_clean(seg.get("translation", seg.get("text", "")))

    if not target.strip():
        return rows

    # 0. Invisible Unicode / ZWNJ checks.
    if ZWSP in target or ZWJ in target:
        cleaned_target = target.replace(ZWSP, "").replace(ZWJ, "")
        rows.append(make_rule_report(
            seg,
            "Unicode / Invisible Character",
            "Major",
            show_invisible_chars(target),
            show_invisible_chars(cleaned_target),
            "Target contains invisible Unicode characters such as ZWSP/ZWJ. Remove them unless specifically required."
        ))

    zwnj_fixed_target, zwnj_labels = suggest_telugu_zwnj(target)
    if zwnj_labels and zwnj_fixed_target != target:
        rows.append(make_rule_report(
            seg,
            "ZWNJ / Unicode",
            "Major",
            "Possible missing Zero Width Non-Joiner (U+200C): " + ", ".join(zwnj_labels),
            show_invisible_chars(zwnj_fixed_target),
            "Telugu UI/loanword suffixes often need ZWNJ. The report uses ⟨ZWNJ⟩ to make the invisible character visible."
        ))

    if ZWNJ in target:
        # Helpful note only when there are suspicious adjacent spaces around ZWNJ.
        if re.search(r"\s" + ZWNJ + r"|" + ZWNJ + r"\s", target):
            rows.append(make_rule_report(
                seg,
                "ZWNJ / Unicode",
                "Minor",
                "Space adjacent to ZWNJ",
                show_invisible_chars(re.sub(r"\s*" + ZWNJ + r"\s*", ZWNJ, target)),
                "ZWNJ should usually sit directly between the stem and suffix, without surrounding spaces."
            ))

    # 1. Multiple spaces inside target text.
    multi_space_matches = list(re.finditer(r" {2,}", target))
    if multi_space_matches:
        collapsed = re.sub(r" {2,}", " ", target)
        rows.append(make_rule_report(
            seg,
            "Formatting",
            "Minor",
            "Multiple consecutive spaces",
            collapsed,
            "Target text contains extra spaces. Collapse repeated spaces to a single space."
        ))

    # 2. Leading/trailing spaces in target text.
    if target != target.strip():
        rows.append(make_rule_report(
            seg,
            "Formatting",
            "Minor",
            "Leading/trailing space",
            target.strip(),
            "Target text has unnecessary leading or trailing spaces."
        ))

    if is_bilingual and source.strip():
        # 3. Missing terminal punctuation from source.
        src_end = get_terminal_punctuation(source)
        if src_end and not has_equivalent_terminal_punctuation(target, src_end):
            rows.append(make_rule_report(
                seg,
                "Formatting",
                "Minor",
                f"Missing ending punctuation: {src_end}",
                target.strip() + src_end,
                "Source ends with punctuation, but target does not preserve equivalent ending punctuation."
            ))

        # 4. Bullet prefix should be preserved for UI/menu strings.
        src_first = first_visible_char(source)
        tgt_first = first_visible_char(target)
        if src_first in BULLET_CHARS and tgt_first not in BULLET_CHARS:
            rows.append(make_rule_report(
                seg,
                "Formatting",
                "Minor",
                f"Missing bullet prefix: {src_first}",
                src_first + target.strip(),
                "Source starts with a bullet/list marker, but target does not."
            ))

        # 5. Brackets often mark UI labels and should be preserved.
        bracket_pairs = [("[", "]"), ("(", ")"), ("{", "}")]
        for open_b, close_b in bracket_pairs:
            if open_b in source and close_b in source:
                if open_b not in target or close_b not in target:
                    rows.append(make_rule_report(
                        seg,
                        "Formatting",
                        "Minor",
                        f"Missing bracket pair: {open_b}{close_b}",
                        f"Preserve {open_b}{close_b} around the translated label where appropriate",
                        "Source contains bracket formatting, but target does not preserve the same bracket structure."
                    ))
                    break

        # 6. Colon preservation for step labels, UI labels, and commands.
        if ":" in source and ":" not in target and "：" not in target:
            rows.append(make_rule_report(
                seg,
                "Formatting",
                "Minor",
                "Missing colon",
                "Add ':' at the equivalent location in the target text",
                "Source contains a colon that is typically required in UI labels or step text."
            ))

        # 7. Quote presence/balance.
        source_quote_count = count_quote_like(source)
        target_quote_count = count_quote_like(target)
        if source_quote_count >= 2 and target_quote_count < 2:
            rows.append(make_rule_report(
                seg,
                "Formatting",
                "Minor",
                "Missing quotation marks",
                "Preserve opening and closing quotation marks around the translated text",
                "Source uses quotation marks, but target is missing a matching quote pair."
            ))
        elif target_quote_count % 2 == 1:
            rows.append(make_rule_report(
                seg,
                "Formatting",
                "Minor",
                "Unbalanced quotation marks",
                "Use matching opening and closing quotation marks",
                "Target appears to have an unmatched quotation mark."
            ))

        # 8. Placeholders/tags must be preserved exactly.
        source_placeholders = find_placeholders(source)
        target_placeholders = find_placeholders(target)
        for ph in source_placeholders:
            if ph not in target_placeholders:
                rows.append(make_rule_report(
                    seg,
                    "Formatting",
                    "Major",
                    f"Missing placeholder/tag: {ph}",
                    f"Keep placeholder/tag exactly as source: {ph}",
                    "A placeholder, variable, or tag from the source is missing in the target."
                ))

        # 9. Numbers in source should generally be preserved in UI strings.
        source_numbers = re.findall(r"\d+", source)
        target_numbers = re.findall(r"\d+", target)
        for num in source_numbers:
            if num not in target_numbers:
                rows.append(make_rule_report(
                    seg,
                    "Formatting",
                    "Major",
                    f"Missing number: {num}",
                    f"Preserve number: {num}",
                    "A number from the source text is missing in the target text."
                ))

    return rows


def dedupe_report_rows(rows):
    seen = set()
    deduped = []
    for row in rows:
        key = (
            row.get("Sheet", ""),
            row.get("Location", ""),
            row.get("Error Type", ""),
            row.get("Wrong Part", ""),
            row.get("Suggestion", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped

# ==============================
# OpenAI QA
# ==============================
def make_batch_prompt(batch):
    lines = []

    for i, seg in enumerate(batch, start=1):
        if seg["mode"] == "bilingual":
            lines.append(
                f"[Segment {i}] ({seg['location']})\n"
                f"SOURCE: {seg['source']}\n"
                f"TRANSLATION: {seg['translation']}"
            )
        else:
            lines.append(
                f"[Segment {i}] ({seg['location']})\n"
                f"TEXT: {seg['text']}"
            )

    return "\n\n".join(lines)


def should_keep_ai_error(err, segment):
    """
    Filter out low-confidence AI suggestions that can hurt trust.
    Rule-based checks still catch mechanical issues like punctuation, spaces, placeholders, and ZWNJ.
    """
    error_type = str(err.get("error_type", "")).strip()
    wrong_part = str(err.get("wrong_part", "")).strip()
    suggestion = str(err.get("suggestion", "")).strip()

    if not suggestion:
        return False

    # Soft/subjective categories are optional because they can produce bad suggestions.
    soft_types = {"Terminology", "Style & Tone", "Readability"}
    if error_type in soft_types and not include_ai_style_terminology:
        return False

    # For local issues, the wrong fragment should appear in the translation/text.
    translation = ""
    if segment:
        translation = str(segment.get("translation", segment.get("text", "")))

    if error_type not in {"Accuracy"} and wrong_part and translation and wrong_part not in translation:
        return False

    # Basic guardrails against obviously broken suggestions.
    suspicious_fragments = [
        "డానికించటానికి",
        "కించటానికి",
        "డానికించ",
        "చడానికించ"
    ]
    if any(fragment in suggestion for fragment in suspicious_fragments):
        return False

    # Do not allow very long rewrite suggestions for soft categories.
    if error_type in soft_types and len(suggestion) > max(80, len(translation) + 40):
        return False

    return True


def run_ai_batch(batch):
    if not batch:
        return []

    prompt_body = make_batch_prompt(batch)

    instructions = (
        "You are an expert linguistic QA specialist. "
        "For bilingual segments, compare SOURCE against TRANSLATION. "
        "For monolingual TEXT segments, check language quality only. "
        "Return only valid JSON."
    )

    user_prompt = f"""
Domain: {domain}
Strictness: {STRICTNESS_GUIDE[strictness]}

Review these segments:

{prompt_body}

Check only real issues:
1. Accuracy or meaning mismatch for bilingual source-vs-translation pairs.
2. Missing or added content.
3. Mixed script or wrong script for target language.
4. Grammar, spelling, punctuation, or spacing.
5. Terminology problems for the domain.
6. Formatting or placeholder problems like {{variable}}, %s, {{0}}, <tag>, URLs, numbers.
7. Unnatural style or tone.
8. Do not ignore missing final punctuation, removed quotes, removed brackets, removed bullets, extra internal spaces, missing numbers/placeholders, or Unicode/ZWNJ issues.
9. For Telugu/Indic localization, check Zero Width Non-Joiner U+200C placement. Use the visible marker ⟨ZWNJ⟩ in suggestions when needed.
10. Avoid subjective terminology/style rewrites unless clearly wrong. Suggestions must be grammatical and minimal. Do not invent awkward compound forms.

Return ONLY a valid JSON array. No markdown. No explanation outside JSON.

Required format:
[
  {{
    "segment_index": 1,
    "location": "exact location string from input",
    "source": "source text if available",
    "translation": "translation or text",
    "language_detected": "detected language",
    "error_type": "Accuracy|Mixed Script|Grammar|Spelling|Terminology|Style & Tone|Formatting|Readability",
    "severity": "Minor|Major|Critical",
    "wrong_part": "specific wrong fragment",
    "suggestion": "corrected phrase or corrected translation",
    "explanation": "brief reason"
  }}
]

If there are no errors, return [].

Severity:
Minor = typo, punctuation, spacing, small grammar issue.
Major = wrong meaning, missing content, wrong script, serious terminology issue.
Critical = offensive, unsafe, legally dangerous, or incomprehensible.
"""

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=user_prompt,
        max_output_tokens=2500
    )

    raw = safe_output_text(response)
    parsed = extract_json_array(raw)

    if not isinstance(parsed, list):
        return []

    return parsed


def run_qa_on_segments(segments, status_text, progress_bar):
    report_rows = []
    errors = []

    if not segments:
        return report_rows, errors

    # Fast deterministic checks run first. These catch formatting issues that AI may skip.
    if run_rule_checks:
        status_text.text("Running deterministic punctuation/spacing checks...")
        for seg_index, seg in enumerate(segments, start=1):
            report_rows.extend(run_deterministic_checks(seg))
            if len(segments) > 0:
                progress_bar.progress(min(seg_index / len(segments), 1.0) * 0.25)

    # AI semantic QA is optional. It handles meaning, grammar, style, and terminology.
    if run_ai_checks:
        total_batches = max(1, (len(segments) + batch_size - 1) // batch_size)

        for batch_index in range(total_batches):
            batch = segments[batch_index * batch_size:(batch_index + 1) * batch_size]

            start_num = batch_index * batch_size + 1
            end_num = min((batch_index + 1) * batch_size, len(segments))

            status_text.text(f"AI batch {batch_index + 1}/{total_batches}: checking segments {start_num}-{end_num} of {len(segments)}")
            progress_base = 0.25 if run_rule_checks else 0.0
            progress_span = 0.75 if run_rule_checks else 1.0
            progress_bar.progress(progress_base + (batch_index / total_batches) * progress_span)

            try:
                batch_errors = run_ai_batch(batch)
            except Exception as e:
                errors.append(f"Batch {batch_index + 1} failed: {str(e)}")
                continue

            for err in batch_errors:
                loc = err.get("location", "")

                original_segment = next((s for s in batch if s.get("location") == loc), None)

                if original_segment:
                    sheet = original_segment.get("sheet", "")
                    source = original_segment.get("source", "")
                    translation = original_segment.get("translation", original_segment.get("text", ""))
                else:
                    sheet = ""
                    source = err.get("source", "")
                    translation = err.get("translation", "")

                if not should_keep_ai_error(err, original_segment):
                    continue

                report_rows.append(
                    build_report_row(
                        sheet=sheet,
                        location=loc,
                        language=err.get("language_detected", "Unknown"),
                        source=source,
                        translation=translation,
                        err=err
                    )
                )

            progress_bar.progress(progress_base + ((batch_index + 1) / total_batches) * progress_span)
    else:
        status_text.text("AI semantic QA skipped. Rule-based checks completed.")

    return dedupe_report_rows(report_rows), errors


# ==============================
# Output builders
# ==============================
def add_report_sheet_to_workbook(wb, report_rows):
    for report_sheet_name in REPORT_SHEETS:
        if report_sheet_name in wb.sheetnames:
            del wb[report_sheet_name]

    rpt = wb.create_sheet("ErrorSweep Report")
    headers = [
        "Sheet", "Location", "Language", "Source Text", "Translation",
        "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation"
    ]

    rpt.append(headers)

    for item in report_rows:
        rpt.append([item.get(h, "") for h in headers])

    style_header(rpt)


def apply_excel_highlights(cell_map, report_rows):
    grouped = {}

    for row in report_rows:
        loc = row.get("Location", "")
        if loc not in grouped:
            grouped[loc] = []
        grouped[loc].append(row)

    for loc, rows in grouped.items():
        cell = cell_map.get(loc)
        if not cell:
            continue

        cell.fill = HIGHLIGHT_FILL

        notes = []
        for row in rows:
            notes.append(
                f"[{row.get('Severity', '').upper()}] {row.get('Error Type', '')}\n"
                f"Issue: {row.get('Wrong Part', '')}\n"
                f"Suggestion: {row.get('Suggestion', '')}\n"
                f"Why: {row.get('Explanation', '')}"
            )

        existing = cell.comment.text if cell.comment else ""
        combined = (existing + "\n\n" + "\n\n".join(notes)).strip() if existing else "\n\n".join(notes)
        cell.comment = Comment(combined, "ErrorSweep")


def report_csv_output(report_rows):
    output = io.BytesIO()
    pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8")
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)
    return output


# ==============================
# Main UI
# ==============================
col_upload, col_info = st.columns([3, 1])

with col_upload:
    st.markdown("#### Upload your file")
    uploaded_file = st.file_uploader(
        "Drop file here",
        type=["xlsx", "csv", "txt", "json", "xml", "xliff", "srt", "docx"],
        label_visibility="collapsed"
    )

with col_info:
    st.markdown("#### Fast QA mode")
    st.markdown("<small>Default mode checks source/translation pairs only.</small>", unsafe_allow_html=True)
    st.markdown("<small>Use Deep Scan only for files without source/target columns.</small>", unsafe_allow_html=True)
    st.markdown("<small>Recommended demo: 20 segments, gpt-4o-mini.</small>", unsafe_allow_html=True)

st.divider()

run_button = st.button("Run Fast AI QA Check", use_container_width=True, type="primary", disabled=not uploaded_file)


if uploaded_file and run_button:
    start_time = time.time()
    status_text = st.empty()
    progress_bar = st.progress(0)

    lower_name = uploaded_file.name.lower()

    try:
        status_text.text("Reading file and collecting QA segments...")

        if lower_name.endswith(".xlsx"):
            wb, segments, cell_map, messages = collect_excel_segments(uploaded_file)
            for msg in messages[:8]:
                st.caption(msg)
        elif lower_name.endswith(".csv"):
            df, segments = collect_csv_segments(uploaded_file)
            wb = None
            cell_map = {}
        elif lower_name.endswith(".docx"):
            segments = collect_docx_segments(uploaded_file)
            wb = None
            cell_map = {}
        else:
            segments = collect_text_segments(uploaded_file)
            wb = None
            cell_map = {}

        if not segments:
            progress_bar.empty()
            status_text.empty()
            st.warning("No QA segments found.")
            st.info("If this is an Excel/CSV file, set Source and Translation column names in the sidebar, or enable Deep Scan.")
            st.stop()

        estimated_calls = max(1, (len(segments) + batch_size - 1) // batch_size)
        st.info(f"Checking {len(segments)} segments. Deterministic checks run instantly; AI will use about {estimated_calls} API call(s) if enabled.")

        report_rows, api_errors = run_qa_on_segments(segments, status_text, progress_bar)

        processing_time = round(time.time() - start_time, 2)

        progress_bar.progress(1.0)
        status_text.text("QA complete.")

        if api_errors:
            with st.expander("API warnings", expanded=True):
                for err in api_errors:
                    st.warning(err)

        if api_errors and not report_rows:
            st.error("The AI API call failed, so this is NOT a clean-file result. Check the API warnings above, model access, and OPENAI_API_KEY.")
            st.stop()

        if report_rows:
            df_report = pd.DataFrame(report_rows)

            critical_count = len(df_report[df_report["Severity"] == "Critical"])
            major_count = len(df_report[df_report["Severity"] == "Major"])
            minor_count = len(df_report[df_report["Severity"] == "Minor"])

            languages_found = ", ".join(
                [str(x) for x in df_report["Language"].dropna().unique() if str(x).strip()]
            )

            st.markdown("### QA Summary")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Errors", len(df_report))
            c2.metric("Critical", critical_count)
            c3.metric("Major", major_count)
            c4.metric("Minor", minor_count)
            c5.metric("Seconds", processing_time)

            if languages_found:
                st.info(f"Languages detected: {languages_found}")

            st.markdown("### Errors by Type")
            type_counts = df_report["Error Type"].value_counts().reset_index()
            type_counts.columns = ["Error Type", "Count"]
            st.dataframe(type_counts, use_container_width=True, hide_index=True)

            st.markdown("### Detailed Findings")

            for _, row in df_report.iterrows():
                severity_value = str(row["Severity"]).lower()
                if severity_value not in ["minor", "major", "critical"]:
                    severity_value = "minor"

                badge = (
                    f'<span class="severity-badge sev-{severity_value}">'
                    f'{row["Severity"]}</span>'
                )

                source_html = ""
                if str(row.get("Source Text", "")).strip():
                    source_html = f'<div class="error-source">Source: {str(row["Source Text"])[:160]}</div>'

                wrong_part = row["Wrong Part"] or str(row["Translation"])[:100]

                st.markdown(f"""
                <div class="error-card {severity_value}">
                    <div class="error-type">
                        {row['Error Type']} · {row['Location']} · {row['Language']} {badge}
                    </div>
                    {source_html}
                    <div class="error-before">Issue: {wrong_part}</div>
                    <div class="error-after">Suggestion: {row['Suggestion']}</div>
                    <small style="color:#888">{row['Explanation']}</small>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            if lower_name.endswith(".xlsx") and wb is not None:
                apply_excel_highlights(cell_map, report_rows)
                add_report_sheet_to_workbook(wb, report_rows)

                output = io.BytesIO()
                wb.save(output)
                output.seek(0)

                st.download_button(
                    label="Download Highlighted Excel Report",
                    data=output.getvalue(),
                    file_name="errorsweep_fast_report_" + uploaded_file.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary"
                )
            else:
                output = report_csv_output(report_rows)

                st.download_button(
                    label="Download QA Report CSV",
                    data=output.getvalue(),
                    file_name="errorsweep_fast_report_" + uploaded_file.name + ".csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )

        else:
            st.success(f"No errors found in {len(segments)} checked segment(s). Completed in {processing_time} seconds.")
            st.caption("If you intentionally added errors, confirm detected columns show Source Text -> Original Translation, and keep deterministic punctuation/spacing checks ON.")

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Error during processing: {str(e)}")
        st.exception(e)


elif not uploaded_file:
    st.markdown("""
    <div class="empty-state">
        <div style="font-family:'Space Mono',monospace; margin-top:12px; color:#666">
            Upload a file to begin fast AI QA
        </div>
        <div style="font-size:13px; margin-top:8px; color:#444">
            Supports .xlsx · .csv · .docx · .txt · .xliff · .srt · .json · .xml
        </div>
        <div style="font-size:12px; margin-top:12px; color:#555">
            For Excel/CSV: best speed comes from source + translation columns.
        </div>
    </div>
    """, unsafe_allow_html=True)
