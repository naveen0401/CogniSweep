import streamlit as st
import pandas as pd
import io
import time
import json
import os
import re
import anthropic
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.comments import Comment
from docx import Document

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="ErrorSweep Pro", layout="wide", page_icon="🧹")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.hero {
    background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 50%, #16213e 100%);
    border: 1px solid #2a2a4a; border-radius: 16px;
    padding: 40px; margin-bottom: 24px; text-align: center;
}
.hero-title { font-family: 'Space Mono', monospace; font-size: 48px; color: #00ff88; font-weight: 700; margin: 0; }
.hero-sub   { font-size: 16px; color: #8888aa; margin-top: 8px; font-weight: 300; }
.hero-badge {
    display: inline-block; background: rgba(0,255,136,0.1);
    border: 1px solid rgba(0,255,136,0.3); color: #00ff88;
    border-radius: 20px; padding: 4px 14px; font-size: 12px;
    font-family: 'Space Mono', monospace; margin-top: 12px;
}
.error-card {
    background: #0f0f1a; border-left: 3px solid #ff4466;
    border-radius: 0 8px 8px 0; padding: 16px; margin-bottom: 12px;
}
.error-card.minor    { border-left-color: #ffaa00; }
.error-card.major    { border-left-color: #ff4466; }
.error-card.critical { border-left-color: #ff0044; }
.error-type   { font-family: 'Space Mono', monospace; font-size: 11px; color: #8888aa; text-transform: uppercase; letter-spacing: 1px; }
.error-source { color: #555577; font-size: 12px; margin: 4px 0; }
.error-before { color: #ff6680; font-size: 14px; margin: 6px 0 2px; }
.error-after  { color: #00ff88; font-size: 14px; }
.severity-badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-family: 'Space Mono', monospace; font-weight: 700; }
.sev-minor    { background: rgba(255,170,0,0.15);  color: #ffaa00; }
.sev-major    { background: rgba(255,68,102,0.15); color: #ff4466; }
.sev-critical { background: rgba(255,0,68,0.2);    color: #ff0044; }
.empty-state  { text-align:center; padding:60px; color:#444; border: 1px dashed #2a2a4a; border-radius:12px; }
</style>
""", unsafe_allow_html=True)

# ─── Hero ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-title">🧹 ErrorSweep Pro</div>
    <div class="hero-sub">Fully AI-powered linguistic QA — any language, any file, zero setup</div>
    <div class="hero-badge">✦ Bilingual source-vs-translation QA &nbsp;·&nbsp; Auto language detection &nbsp;·&nbsp; Powered by Claude AI</div>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧹 ErrorSweep Pro")
    st.caption("v3.1 — Bilingual QA Engine")
    st.divider()

    st.markdown("**📁 Supported Formats**")
    for fmt in [".xlsx", ".csv", ".txt", ".json", ".xml", ".xliff", ".srt", ".docx"]:
        st.markdown(f"`{fmt}`")

    st.divider()
    st.markdown("**⚙️ QA Settings**")

    domain = st.selectbox(
        "Content Domain",
        ["Auto-detect", "Software UI / App Strings", "Subtitles / Captions",
         "Legal / Compliance", "Medical / Healthcare", "Marketing / Ad Copy",
         "E-learning / Education", "General"],
        help="Helps Claude apply domain-specific quality rules"
    )

    strictness = st.select_slider(
        "QA Strictness",
        options=["Lenient", "Standard", "Strict", "Very Strict"],
        value="Standard"
    )

    max_segments = st.number_input(
        "Max segments to check", min_value=5, max_value=200, value=50,
        help="Limit AI checks to control API cost"
    )

    st.divider()
    st.markdown("**🔢 Column Mapping (Excel/CSV)**")
    st.caption("Override auto-detection if needed")
    source_col_hint = st.text_input("Source column (name or index)", value="",
                                     placeholder="e.g. Source Text or 1")
    target_col_hint = st.text_input("Translation column (name or index)", value="",
                                     placeholder="e.g. Original Translation or 2")
    st.divider()
    st.caption("💡 Set domain correctly for best results.")

# ─── Constants ────────────────────────────────────────────────────────────────
HIGHLIGHT_FILL = PatternFill(start_color="FFF59D", end_color="FFF59D", fill_type="solid")
HEADER_FILL    = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
HEADER_FONT    = Font(bold=True)
REPORT_SHEETS  = ["ErrorSweep Report"]
BATCH_SIZE     = 10  # segments per API call

STRICTNESS_GUIDE = {
    "Lenient":     "Only flag clear, obvious errors. Ignore minor style preferences.",
    "Standard":    "Flag clear errors and notable quality issues.",
    "Strict":      "Flag all errors including minor style, tone, and consistency issues.",
    "Very Strict": "Flag everything including subtle fluency, register, and micro-style issues."
}

# ─── Core AI QA ───────────────────────────────────────────────────────────────

def ai_qa_bilingual_batch(pairs, domain, strictness, client):
    """
    Bilingual QA: compare source vs translation in batches.
    pairs = [{"source": str, "translation": str, "location": str}, ...]
    Returns list of error dicts.
    """
    if not pairs:
        return []

    numbered = "\n\n".join(
        f"[Segment {i+1}] ({p['location']})\n"
        f"SOURCE: {p['source']}\n"
        f"TRANSLATION: {p['translation']}"
        for i, p in enumerate(pairs)
    )

    prompt = f"""You are an expert bilingual linguistic QA specialist reviewing source-vs-translation pairs.

Domain: {domain}
Strictness: {STRICTNESS_GUIDE[strictness]}

Translation pairs to review:

{numbered}

For EACH segment, check:
1. Accuracy — does the translation faithfully convey the source meaning? Any omissions, additions, or wrong meaning?
2. Mixed script — are target-language words written in the wrong script? (e.g. Roman/Latin characters used where native script like Telugu/Hindi is expected)
3. Grammar — grammatical errors in the target language
4. Terminology — wrong or inconsistent UI/domain terms
5. Style & Tone — formality mismatch, unnatural phrasing for native speakers
6. Formatting — extra spaces, wrong punctuation, missing/changed placeholders like {{{{variable}}}}
7. Readability — awkward structure unnatural for native speakers

Return ONLY a valid JSON array — no markdown, no explanation outside the JSON:
[
  {{
    "segment_index": 1,
    "location": "exact location string from input",
    "source": "source text",
    "translation": "translation text",
    "language_detected": "detected target language",
    "error_type": "Accuracy|Mixed Script|Grammar|Terminology|Style & Tone|Formatting|Readability",
    "severity": "Minor|Major|Critical",
    "wrong_part": "the specific wrong fragment in the translation",
    "suggestion": "corrected translation or fix",
    "explanation": "brief, specific reason"
  }}
]

Only include entries where you found a REAL error. If all segments are correct, return [].
Severity: Minor = typo/punctuation/spacing; Major = wrong meaning or wrong script; Critical = offensive or completely incomprehensible."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'^```\s*',     '', text)
        text = re.sub(r'\s*```$',     '', text)
        result = json.loads(text)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def ai_qa_monolingual(text, location, domain, strictness, client):
    """Fallback: single-text QA when no source column is available."""
    prompt = f"""You are an expert multilingual linguistic QA specialist.

Analyze this text for quality issues.
Domain: {domain}
Strictness: {STRICTNESS_GUIDE[strictness]}

Text: \"\"\"{text}\"\"\"

Check: Grammar, Spelling, Punctuation, Mixed Language/Script, Style, Formatting.
Return ONLY a valid JSON array:
[
  {{
    "language_detected": "detected language",
    "error_type": "Grammar|Spelling|Mixed Script|Formatting|Style",
    "severity": "Minor|Major|Critical",
    "wrong_part": "exact wrong fragment",
    "suggestion": "corrected text",
    "explanation": "brief reason"
  }}
]
If no errors, return: []"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        resp = message.content[0].text.strip()
        resp = re.sub(r'^```json\s*', '', resp)
        resp = re.sub(r'^```\s*',     '', resp)
        resp = re.sub(r'\s*```$',     '', resp)
        result = json.loads(resp)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def normalize_text(text):
    text = str(text)
    for ch in ["\u200B", "\u200C", "\u200D"]:
        text = text.replace(ch, "")
    return text.strip()


def style_header(sheet):
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT


def build_report_row(sheet, location, language, source, translation, err):
    return {
        "Sheet":       sheet,
        "Location":    location,
        "Language":    language,
        "Source Text": (source or "")[:200],
        "Translation": (translation or "")[:200],
        "Error Type":  err.get("error_type", ""),
        "Severity":    err.get("severity", "Minor"),
        "Wrong Part":  err.get("wrong_part", err.get("original", "")),
        "Suggestion":  err.get("suggestion", ""),
        "Explanation": err.get("explanation", ""),
    }


# ─── Column detection ─────────────────────────────────────────────────────────
def detect_source_target_columns(headers, source_hint="", target_hint=""):
    headers_lower = [str(h).lower().strip() for h in headers]
    source_keywords = ["source text", "source", "src", "english", "en", "original"]
    target_keywords = ["original translation", "translation", "target", "translated",
                       "suggested translation", "tgt", "output", "localized"]

    def find_col(hint, keywords):
        if hint:
            for i, h in enumerate(headers_lower):
                if h == hint.lower().strip():
                    return i
            try:
                idx = int(hint)
                if 0 <= idx < len(headers):
                    return idx
            except ValueError:
                pass
            for i, h in enumerate(headers_lower):
                if hint.lower() in h:
                    return i
        for kw in keywords:
            for i, h in enumerate(headers_lower):
                if kw in h:
                    return i
        return None

    src_idx = find_col(source_hint, source_keywords)
    tgt_idx = find_col(target_hint, target_keywords)

    if src_idx is not None and tgt_idx is None:
        tgt_idx = src_idx + 1 if src_idx + 1 < len(headers) else None
    if tgt_idx is not None and src_idx is None:
        src_idx = tgt_idx - 1 if tgt_idx - 1 >= 0 else None

    return src_idx, tgt_idx


# ─── Processors ───────────────────────────────────────────────────────────────
def process_excel(uploaded_file, domain, strictness, client, progress_bar, status_text):
    wb = load_workbook(uploaded_file)
    report_rows = []

    for ws in wb.worksheets:
        if ws.title in REPORT_SHEETS:
            continue

        rows = list(ws.iter_rows(values_only=False))
        if not rows:
            continue

        header_row = [str(cell.value).strip() if cell.value else "" for cell in rows[0]]
        src_idx, tgt_idx = detect_source_target_columns(
            header_row, source_col_hint, target_col_hint
        )

        if src_idx is not None and tgt_idx is not None:
            # ── Bilingual mode ──
            status_text.text(f"📋 Sheet '{ws.title}': [{header_row[src_idx]}] → [{header_row[tgt_idx]}] (bilingual mode)")
            pairs = []
            cell_map = {}

            for row_idx, row in enumerate(rows[1:], start=2):
                if len(row) <= max(src_idx, tgt_idx):
                    continue
                src_val = normalize_text(row[src_idx].value or "")
                tgt_val = normalize_text(row[tgt_idx].value or "")
                if src_val and tgt_val and len(src_val) > 2 and not src_val.startswith("["):
                    loc = f"Row {row_idx}"
                    pairs.append({"source": src_val, "translation": tgt_val, "location": loc})
                    cell_map[loc] = row[tgt_idx]

            pairs = pairs[:max_segments]
            total_batches = max(1, (len(pairs) + BATCH_SIZE - 1) // BATCH_SIZE)

            for b in range(total_batches):
                batch = pairs[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
                status_text.text(
                    f"🔍 Sheet '{ws.title}': checking segments "
                    f"{b*BATCH_SIZE+1}–{min((b+1)*BATCH_SIZE, len(pairs))} of {len(pairs)}..."
                )
                progress_bar.progress((b + 1) / total_batches)
                errors = ai_qa_bilingual_batch(batch, domain, strictness, client)

                for err in errors:
                    loc = err.get("location", "")
                    lang = err.get("language_detected", "Unknown")
                    report_rows.append(build_report_row(
                        ws.title, loc, lang,
                        err.get("source", ""), err.get("translation", ""), err
                    ))
                    if loc in cell_map:
                        cell_map[loc].fill = HIGHLIGHT_FILL
                        existing = cell_map[loc].comment.text if cell_map[loc].comment else ""
                        note = (
                            f"[{err.get('severity','').upper()}] {err.get('error_type','')}\n"
                            f"Issue: {err.get('wrong_part','')}\n"
                            f"Fix:   {err.get('suggestion','')}\n"
                            f"Why:   {err.get('explanation','')}"
                        )
                        combined = (existing + "\n\n" + note).strip() if existing else note
                        cell_map[loc].comment = Comment(combined, "ErrorSweep")
        else:
            # ── Monolingual fallback ──
            status_text.text(f"📋 Sheet '{ws.title}': no source/translation columns found — single-text QA mode")
            all_cells = [
                cell for row in rows
                for cell in row
                if cell.value and isinstance(cell.value, str) and len(cell.value.strip()) > 3
            ]
            total = min(len(all_cells), max_segments)
            for idx, cell in enumerate(all_cells[:max_segments]):
                text = normalize_text(cell.value)
                status_text.text(f"🔍 Checking cell {idx+1}/{total} ({cell.coordinate})...")
                progress_bar.progress((idx + 1) / total)
                errors = ai_qa_monolingual(text, cell.coordinate, domain, strictness, client)
                if errors:
                    cell.fill = HIGHLIGHT_FILL
                    notes = []
                    for err in errors:
                        report_rows.append(build_report_row(ws.title, cell.coordinate,
                                                             err.get("language_detected", "Unknown"), "", text, err))
                        notes.append(
                            f"[{err.get('severity','').upper()}] {err.get('error_type','')}\n"
                            f"Issue: {err.get('wrong_part', err.get('original',''))}\n"
                            f"Fix:   {err.get('suggestion','')}\n"
                            f"Why:   {err.get('explanation','')}"
                        )
                    cell.comment = Comment("\n\n".join(notes), "ErrorSweep")

    # Write report sheet
    for sn in REPORT_SHEETS:
        if sn in wb.sheetnames:
            del wb[sn]
    rpt = wb.create_sheet("ErrorSweep Report")
    headers = ["Sheet", "Location", "Language", "Source Text", "Translation",
               "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation"]
    rpt.append(headers)
    for item in report_rows:
        rpt.append([item.get(h, "") for h in headers])
    style_header(rpt)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output, report_rows, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def process_csv(uploaded_file, domain, strictness, client, progress_bar, status_text):
    df = pd.read_csv(uploaded_file)
    report_rows = []

    src_idx, tgt_idx = detect_source_target_columns(
        list(df.columns), source_col_hint, target_col_hint
    )

    if src_idx is not None and tgt_idx is not None:
        src_col = df.columns[src_idx]
        tgt_col = df.columns[tgt_idx]
        status_text.text(f"📋 Bilingual mode: [{src_col}] → [{tgt_col}]")

        pairs = []
        for i, row in df.iterrows():
            sv = normalize_text(str(row[src_col])) if pd.notna(row[src_col]) else ""
            tv = normalize_text(str(row[tgt_col])) if pd.notna(row[tgt_col]) else ""
            if sv and tv and len(sv) > 2:
                pairs.append({"source": sv, "translation": tv, "location": f"Row {i+2}"})

        pairs = pairs[:max_segments]
        total_batches = max(1, (len(pairs) + BATCH_SIZE - 1) // BATCH_SIZE)
        for b in range(total_batches):
            batch = pairs[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
            status_text.text(f"🔍 Checking segments {b*BATCH_SIZE+1}–{min((b+1)*BATCH_SIZE, len(pairs))} of {len(pairs)}...")
            progress_bar.progress((b + 1) / total_batches)
            errors = ai_qa_bilingual_batch(batch, domain, strictness, client)
            for err in errors:
                report_rows.append(build_report_row(
                    "CSV", err.get("location", ""), err.get("language_detected", "Unknown"),
                    err.get("source", ""), err.get("translation", ""), err
                ))
    else:
        segments = [
            (col, index, str(value))
            for col in df.columns
            for index, value in df[col].items()
            if pd.notna(value) and isinstance(value, str) and len(str(value).strip()) > 3
        ]
        total = min(len(segments), max_segments)
        for idx, (col, index, text) in enumerate(segments[:max_segments]):
            status_text.text(f"🔍 Checking segment {idx+1}/{total}...")
            progress_bar.progress((idx + 1) / total)
            errors = ai_qa_monolingual(normalize_text(text), f"Row {index+2}, Col: {col}", domain, strictness, client)
            for err in errors:
                report_rows.append(build_report_row("CSV", f"Row {index+2}, Col: {col}",
                                                     err.get("language_detected", "Unknown"), "", text, err))

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)
    return output, report_rows, "text/csv"


def process_text_based(uploaded_file, domain, strictness, client, progress_bar, status_text):
    text = uploaded_file.read().decode("utf-8", errors="ignore")
    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]
    report_rows = []
    total = min(len(lines), max_segments)

    # Detect tab-separated bilingual pairs
    pairs = []
    for i, line in enumerate(lines[:max_segments]):
        parts = line.split("\t")
        if len(parts) >= 2 and len(parts[0].strip()) > 2 and len(parts[1].strip()) > 2:
            pairs.append({"source": parts[0].strip(), "translation": parts[1].strip(), "location": f"Line {i+1}"})

    if len(pairs) > total // 2:
        status_text.text("📋 Detected tab-separated pairs — using bilingual mode")
        total_batches = max(1, (len(pairs) + BATCH_SIZE - 1) // BATCH_SIZE)
        for b in range(total_batches):
            batch = pairs[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
            status_text.text(f"🔍 Checking pairs {b*BATCH_SIZE+1}–{min((b+1)*BATCH_SIZE, len(pairs))} of {len(pairs)}...")
            progress_bar.progress((b + 1) / total_batches)
            errors = ai_qa_bilingual_batch(batch, domain, strictness, client)
            for err in errors:
                report_rows.append(build_report_row(
                    "File", err.get("location", ""), err.get("language_detected", "Unknown"),
                    err.get("source", ""), err.get("translation", ""), err
                ))
    else:
        for idx, line in enumerate(lines[:max_segments]):
            status_text.text(f"🔍 Checking line {idx+1}/{total}...")
            progress_bar.progress((idx + 1) / total)
            errors = ai_qa_monolingual(normalize_text(line), f"Line {idx+1}", domain, strictness, client)
            for err in errors:
                report_rows.append(build_report_row("File", f"Line {idx+1}",
                                                     err.get("language_detected", "Unknown"), "", line, err))

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)
    return output, report_rows, "text/csv"


def process_docx(uploaded_file, domain, strictness, client, progress_bar, status_text):
    doc = Document(uploaded_file)
    report_rows = []
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip() and len(p.text.strip()) > 3]
    total = min(len(paragraphs), max_segments)

    for idx, text in enumerate(paragraphs[:max_segments]):
        status_text.text(f"🔍 Checking paragraph {idx+1}/{total}...")
        progress_bar.progress((idx + 1) / total)
        errors = ai_qa_monolingual(normalize_text(text), f"Paragraph {idx+1}", domain, strictness, client)
        for err in errors:
            report_rows.append(build_report_row("Document", f"Paragraph {idx+1}",
                                                 err.get("language_detected", "Unknown"), "", text, err))

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)
    return output, report_rows, "text/csv"


# ─── Main UI ──────────────────────────────────────────────────────────────────
col_upload, col_info = st.columns([3, 1])

with col_upload:
    st.markdown("#### 📤 Upload Your File")
    uploaded_file = st.file_uploader(
        "Drop any file — AI detects language and errors automatically",
        type=["xlsx", "csv", "txt", "json", "xml", "xliff", "srt", "docx"],
        label_visibility="collapsed"
    )

with col_info:
    st.markdown("#### What AI checks")
    for item in ["✦ Source vs translation accuracy", "✦ Mixed script detection",
                 "✦ Grammar & spelling", "✦ Terminology",
                 "✦ Mixed language", "✦ Style & tone", "✦ Formatting & placeholders"]:
        st.markdown(f"<small>{item}</small>", unsafe_allow_html=True)

st.divider()

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    st.error("⚠️ ANTHROPIC_API_KEY not set. Add it in Streamlit Cloud → Settings → Secrets.")
    st.stop()

run_button = st.button(
    "🚀 Run AI QA Check", use_container_width=True,
    type="primary", disabled=not uploaded_file
)

if uploaded_file and run_button:
    client     = anthropic.Anthropic(api_key=api_key)
    start_time = time.time()
    st.markdown("---")
    status_text  = st.empty()
    progress_bar = st.progress(0)

    lower_name = uploaded_file.name.lower()

    try:
        if lower_name.endswith(".xlsx"):
            output, report_rows, mime_type = process_excel(uploaded_file, domain, strictness, client, progress_bar, status_text)
        elif lower_name.endswith(".csv"):
            output, report_rows, mime_type = process_csv(uploaded_file, domain, strictness, client, progress_bar, status_text)
        elif lower_name.endswith(".docx"):
            output, report_rows, mime_type = process_docx(uploaded_file, domain, strictness, client, progress_bar, status_text)
        else:
            output, report_rows, mime_type = process_text_based(uploaded_file, domain, strictness, client, progress_bar, status_text)

        progress_bar.progress(1.0)
        status_text.text("✅ QA complete!")
        processing_time = round(time.time() - start_time, 2)

        if report_rows:
            df = pd.DataFrame(report_rows)
            critical_count  = len(df[df["Severity"] == "Critical"])
            major_count     = len(df[df["Severity"] == "Major"])
            minor_count     = len(df[df["Severity"] == "Minor"])
            languages_found = ", ".join(df["Language"].unique())

            st.markdown("### 📊 QA Summary")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Errors",  len(df))
            c2.metric("🔴 Critical",   critical_count)
            c3.metric("🟠 Major",      major_count)
            c4.metric("🟡 Minor",      minor_count)
            c5.metric("⏱ Secs",        processing_time)

            st.info(f"🌐 **Languages detected:** {languages_found}")

            st.markdown("### 🔍 Errors by Type")
            type_counts = df["Error Type"].value_counts().reset_index()
            type_counts.columns = ["Error Type", "Count"]
            st.dataframe(type_counts, use_container_width=True, hide_index=True)

            st.markdown("### 📋 Detailed Findings")
            for _, row in df.iterrows():
                sev   = row["Severity"].lower() if row["Severity"].lower() in ["minor","major","critical"] else "minor"
                badge = f'<span class="severity-badge sev-{sev}">{row["Severity"]}</span>'
                src_html = (f'<div class="error-source">↑ Source: {row["Source Text"][:120]}</div>'
                            if row.get("Source Text") else "")
                st.markdown(f"""
                <div class="error-card {sev}">
                    <div class="error-type">{row['Error Type']} · {row['Location']} · {row['Language']} {badge}</div>
                    {src_html}
                    <div class="error-before">✗ {row['Wrong Part'] or row['Translation'][:80]}</div>
                    <div class="error-after">✓ {row['Suggestion']}</div>
                    <small style="color:#888">{row['Explanation']}</small>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.download_button(
                label="⬇️ Download Full QA Report",
                data=output.getvalue(),
                file_name="errorsweep_report_" + uploaded_file.name,
                mime=mime_type,
                use_container_width=True,
                type="primary"
            )

        else:
            progress_bar.empty()
            status_text.empty()
            st.success("✅ No errors found! Your file looks clean.")

    except Exception as e:
        st.error(f"❌ Error during processing: {str(e)}")
        st.exception(e)

elif not uploaded_file:
    st.markdown("""
    <div class="empty-state">
        <div style="font-size:48px">📂</div>
        <div style="font-family:'Space Mono',monospace; margin-top:12px; color:#666">Upload a file to begin AI QA</div>
        <div style="font-size:13px; margin-top:8px; color:#444">Supports .xlsx · .csv · .docx · .txt · .xliff · .srt · .json · .xml</div>
        <div style="font-size:12px; margin-top:12px; color:#555">For Excel/CSV: AI auto-detects source & translation columns<br>or set column names in the sidebar</div>
    </div>
    """, unsafe_allow_html=True)
