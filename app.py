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
    <div class="hero-badge">✦ No corrections file needed &nbsp;·&nbsp; Auto language detection &nbsp;·&nbsp; Powered by Claude AI</div>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧹 ErrorSweep Pro")
    st.caption("v3.0 — Fully AI-Powered")
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
    st.caption("💡 Set domain correctly for best results.")

# ─── Constants ────────────────────────────────────────────────────────────────
HIGHLIGHT_FILL = PatternFill(start_color="FFF59D", end_color="FFF59D", fill_type="solid")
HEADER_FILL    = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
HEADER_FONT    = Font(bold=True)
REPORT_SHEETS  = ["ErrorSweep Report"]

# ─── Core AI QA ───────────────────────────────────────────────────────────────
def ai_qa_segment(text, domain, strictness, client):
    if not text or not text.strip() or len(text.strip()) < 3:
        return []

    strictness_guide = {
        "Lenient":     "Only flag clear, obvious errors. Ignore minor style preferences.",
        "Standard":    "Flag clear errors and notable quality issues.",
        "Strict":      "Flag all errors including minor style, tone, and consistency issues.",
        "Very Strict": "Flag everything including subtle fluency, register, and micro-style issues."
    }

    prompt = f"""You are an expert multilingual linguistic QA specialist.

Analyze the following text segment for quality issues.
Domain: {domain}
Strictness: {strictness_guide[strictness]}

Text to analyze:
\"\"\"
{text}
\"\"\"

Instructions:
1. Auto-detect the language(s) present
2. Check for: Mistranslation, Terminology, Grammar, Spelling, Punctuation, Formatting, Style/Tone, Mixed Language, Consistency
3. For EACH error found, return a JSON object
4. If NO errors found, return empty array []

Return ONLY a valid JSON array, no other text:
[
  {{
    "language_detected": "Telugu",
    "error_type": "Mistranslation",
    "severity": "Major",
    "original": "exact wrong text",
    "suggestion": "corrected text",
    "explanation": "brief reason"
  }}
]

Severity: Minor, Major, or Critical only.
If text is correct, return: []"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'^```\s*',     '', response_text)
        response_text = re.sub(r'\s*```$',     '', response_text)
        errors = json.loads(response_text)
        return errors if isinstance(errors, list) else []
    except Exception:
        return []


def normalize_text(text):
    text = str(text)
    for ch in ["\u200B", "\u200C", "\u200D"]:
        text = text.replace(ch, "")
    return text


def style_header(sheet):
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT


def build_report_row(sheet, location, language, original, err):
    return {
        "Sheet":         sheet,
        "Location":      location,
        "Language":      language,
        "Original Text": original[:200],
        "Error Type":    err.get("error_type", ""),
        "Severity":      err.get("severity", "Minor"),
        "Wrong Segment": err.get("original", ""),
        "Suggestion":    err.get("suggestion", ""),
        "Explanation":   err.get("explanation", ""),
    }


# ─── Processors ───────────────────────────────────────────────────────────────
def process_excel(uploaded_file, domain, strictness, client, progress_bar, status_text):
    wb          = load_workbook(uploaded_file)
    report_rows = []

    all_cells = [
        (ws, cell)
        for ws in wb.worksheets
        if ws.title not in REPORT_SHEETS
        for row in ws.iter_rows()
        for cell in row
        if cell.value and isinstance(cell.value, str) and len(cell.value.strip()) > 3
    ]

    total = min(len(all_cells), max_segments)

    for idx, (ws, cell) in enumerate(all_cells[:max_segments]):
        text = normalize_text(cell.value)
        status_text.text(f"🔍 Checking segment {idx+1} of {total}...")
        progress_bar.progress((idx + 1) / total)

        errors = ai_qa_segment(text, domain, strictness, client)

        if errors:
            cell.fill = HIGHLIGHT_FILL
            notes = []
            for err in errors:
                lang = err.get("language_detected", "Unknown")
                report_rows.append(build_report_row(ws.title, cell.coordinate, lang, text, err))
                notes.append(
                    f"[{err.get('severity','').upper()}] {err.get('error_type','')}\n"
                    f"Issue: {err.get('original','')}\n"
                    f"Fix:   {err.get('suggestion','')}\n"
                    f"Why:   {err.get('explanation','')}"
                )
            cell.comment = Comment("\n\n".join(notes), "ErrorSweep")

    for sn in REPORT_SHEETS:
        if sn in wb.sheetnames:
            del wb[sn]

    rpt     = wb.create_sheet("ErrorSweep Report")
    headers = ["Sheet","Location","Language","Original Text","Error Type","Severity","Wrong Segment","Suggestion","Explanation"]
    rpt.append(headers)
    for item in report_rows:
        rpt.append([item.get(h, "") for h in headers])
    style_header(rpt)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output, report_rows, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def process_csv(uploaded_file, domain, strictness, client, progress_bar, status_text):
    df          = pd.read_csv(uploaded_file)
    report_rows = []

    segments = [
        (col, index, str(value))
        for col in df.columns
        for index, value in df[col].items()
        if pd.notna(value) and isinstance(value, str) and len(str(value).strip()) > 3
    ]
    total = min(len(segments), max_segments)

    for idx, (col, index, text) in enumerate(segments[:max_segments]):
        status_text.text(f"🔍 Checking segment {idx+1} of {total}...")
        progress_bar.progress((idx + 1) / total)
        errors = ai_qa_segment(normalize_text(text), domain, strictness, client)
        for err in errors:
            lang = err.get("language_detected", "Unknown")
            report_rows.append(build_report_row("CSV", f"Row {index+2}, Col: {col}", lang, text, err))

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)
    return output, report_rows, "text/csv"


def process_text_based(uploaded_file, domain, strictness, client, progress_bar, status_text):
    text        = uploaded_file.read().decode("utf-8", errors="ignore")
    lines       = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]
    report_rows = []
    total       = min(len(lines), max_segments)

    for idx, line in enumerate(lines[:max_segments]):
        status_text.text(f"🔍 Checking line {idx+1} of {total}...")
        progress_bar.progress((idx + 1) / total)
        errors = ai_qa_segment(normalize_text(line), domain, strictness, client)
        for err in errors:
            lang = err.get("language_detected", "Unknown")
            report_rows.append(build_report_row("File", f"Line {idx+1}", lang, line, err))

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)
    return output, report_rows, "text/csv"


def process_docx(uploaded_file, domain, strictness, client, progress_bar, status_text):
    doc         = Document(uploaded_file)
    report_rows = []
    paragraphs  = [p.text.strip() for p in doc.paragraphs if p.text.strip() and len(p.text.strip()) > 3]
    total       = min(len(paragraphs), max_segments)

    for idx, text in enumerate(paragraphs[:max_segments]):
        status_text.text(f"🔍 Checking paragraph {idx+1} of {total}...")
        progress_bar.progress((idx + 1) / total)
        errors = ai_qa_segment(normalize_text(text), domain, strictness, client)
        for err in errors:
            lang = err.get("language_detected", "Unknown")
            report_rows.append(build_report_row("Document", f"Paragraph {idx+1}", lang, text, err))

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
    for item in ["✦ Auto language detection", "✦ Mistranslation", "✦ Grammar & spelling",
                 "✦ Terminology", "✦ Mixed language", "✦ Style & tone", "✦ Formatting"]:
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
                st.markdown(f"""
                <div class="error-card {sev}">
                    <div class="error-type">{row['Error Type']} · {row['Location']} · {row['Language']} {badge}</div>
                    <div class="error-before">✗ {row['Wrong Segment'] or row['Original Text'][:80]}</div>
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

elif not uploaded_file:
    st.markdown("""
    <div class="empty-state">
        <div style="font-size:48px">📂</div>
        <div style="font-family:'Space Mono',monospace; margin-top:12px; color:#666">Upload a file to begin AI QA</div>
        <div style="font-size:13px; margin-top:8px; color:#444">Supports .xlsx · .csv · .docx · .txt · .xliff · .srt · .json · .xml</div>
    </div>
    """, unsafe_allow_html=True)
