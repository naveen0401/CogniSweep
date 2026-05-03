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


# ---------------- Page Config ----------------
st.set_page_config(page_title="ErrorSweep Pro", layout="wide")


# ---------------- Styling ----------------
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
    padding: 40px;
    margin-bottom: 24px;
    text-align: center;
}

.hero-title {
    font-family: 'Space Mono', monospace;
    font-size: 48px;
    color: #00ff88;
    font-weight: 700;
    margin: 0;
}

.hero-sub {
    font-size: 16px;
    color: #8888aa;
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
    color: #555577;
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
    padding:60px;
    color:#444;
    border: 1px dashed #2a2a4a;
    border-radius:12px;
}
</style>
""", unsafe_allow_html=True)


# ---------------- Hero ----------------
st.markdown("""
<div class="hero">
    <div class="hero-title">ErrorSweep Pro</div>
    <div class="hero-sub">AI-powered linguistic QA for source-vs-translation review</div>
    <div class="hero-badge">Bilingual QA · Auto language detection · Powered by ChatGPT API</div>
</div>
""", unsafe_allow_html=True)


# ---------------- Constants ----------------
HIGHLIGHT_FILL = PatternFill(start_color="FFF59D", end_color="FFF59D", fill_type="solid")
HEADER_FILL = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
HEADER_FONT = Font(bold=True)

REPORT_SHEETS = ["ErrorSweep Report"]
BATCH_SIZE = 10

STRICTNESS_GUIDE = {
    "Lenient": "Only flag clear, obvious errors. Ignore minor style preferences.",
    "Standard": "Flag clear errors and notable quality issues.",
    "Strict": "Flag all errors including minor style, tone, and consistency issues.",
    "Very Strict": "Flag everything including subtle fluency, register, and micro-style issues."
}


# ---------------- Secrets ----------------
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


# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### ErrorSweep Pro")
    st.caption("v4.0 — OpenAI / ChatGPT QA Engine")
    st.divider()

    st.markdown("**Supported Formats**")
    for fmt in [".xlsx", ".csv", ".txt", ".json", ".xml", ".xliff", ".srt", ".docx"]:
        st.markdown(f"`{fmt}`")

    st.divider()
    st.markdown("**OpenAI Settings**")

    openai_model = st.selectbox(
        "Model",
        ["gpt-4o-mini", "gpt-5.5"],
        index=0,
        help="Use gpt-4o-mini for faster/lower-cost testing. Use gpt-5.5 for stronger QA if your API account supports it."
    )

    st.divider()
    st.markdown("**QA Settings**")

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
            "General"
        ],
        help="Helps the AI apply domain-specific QA rules."
    )

    strictness = st.select_slider(
        "QA Strictness",
        options=["Lenient", "Standard", "Strict", "Very Strict"],
        value="Standard"
    )

    max_segments = st.number_input(
        "Max segments to check",
        min_value=5,
        max_value=200,
        value=50,
        help="Limit AI checks to control API cost."
    )

    st.divider()
    st.markdown("**Column Mapping for Excel/CSV**")
    st.caption("Override auto-detection if needed.")

    source_col_hint = st.text_input(
        "Source column name or number",
        value="",
        placeholder="Example: Source Text or 1"
    )

    target_col_hint = st.text_input(
        "Translation column name or number",
        value="",
        placeholder="Example: Original Translation or 2"
    )

    st.divider()
    st.caption("For Streamlit Cloud, add OPENAI_API_KEY in app Secrets.")


# ---------------- OpenAI Client ----------------
api_key = get_secret_value("OPENAI_API_KEY")

if not api_key:
    st.error("OPENAI_API_KEY is not set.")
    st.info("In Streamlit Cloud, go to App Settings > Secrets and add:")
    st.code('OPENAI_API_KEY = "your_new_openai_api_key_here"', language="toml")
    st.stop()

client = OpenAI(api_key=api_key)


# ---------------- Utility Functions ----------------
def normalize_text(text):
    text = str(text)

    for ch in ["\u200B", "\u200C", "\u200D"]:
        text = text.replace(ch, "")

    return text.strip()


def style_header(sheet):
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT


def extract_json_array(raw_text):
    text = raw_text.strip()

    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    parsed = json.loads(text)

    if isinstance(parsed, list):
        return parsed

    return []


def call_openai_json(system_instructions, user_prompt, max_output_tokens=4096):
    response = client.responses.create(
        model=openai_model,
        instructions=system_instructions,
        input=user_prompt,
        max_output_tokens=max_output_tokens
    )

    return extract_json_array(response.output_text)


def build_report_row(sheet, location, language, source, translation, err):
    return {
        "Sheet": sheet,
        "Location": location,
        "Language": language,
        "Source Text": (source or "")[:300],
        "Translation": (translation or "")[:300],
        "Error Type": err.get("error_type", ""),
        "Severity": err.get("severity", "Minor"),
        "Wrong Part": err.get("wrong_part", err.get("original", "")),
        "Suggestion": err.get("suggestion", ""),
        "Explanation": err.get("explanation", "")
    }


# ---------------- AI QA Functions ----------------
def ai_qa_bilingual_batch(pairs, domain_value, strictness_value):
    """
    Bilingual QA: compares source text against translation text.
    pairs = [{"source": str, "translation": str, "location": str}, ...]
    Returns list of error dictionaries.
    """
    if not pairs:
        return []

    numbered = "\n\n".join(
        f"[Segment {i + 1}] ({p['location']})\n"
        f"SOURCE: {p['source']}\n"
        f"TRANSLATION: {p['translation']}"
        for i, p in enumerate(pairs)
    )

    system_instructions = (
        "You are an expert bilingual linguistic QA specialist. "
        "You review source-vs-translation pairs and return only valid JSON."
    )

    user_prompt = f"""
Domain: {domain_value}
Strictness: {STRICTNESS_GUIDE[strictness_value]}

Translation pairs to review:

{numbered}

For each segment, check:
1. Accuracy: Does the translation faithfully convey the source meaning? Check omissions, additions, mistranslations, and wrong meaning.
2. Mixed script: Are target-language words written in the wrong script? Example: Roman/Latin characters where native script is expected.
3. Grammar: Grammar errors in the target language.
4. Terminology: Wrong or inconsistent UI/domain terms.
5. Style and tone: Formality mismatch or unnatural phrasing.
6. Formatting: Extra spaces, wrong punctuation, missing/changed placeholders like {{variable}}, %s, {{0}}, or HTML/XML tags.
7. Readability: Awkward structure unnatural for native speakers.

Return ONLY a valid JSON array. No markdown. No explanation outside JSON.

Required JSON format:
[
  {{
    "segment_index": 1,
    "location": "exact location string from input",
    "source": "source text",
    "translation": "translation text",
    "language_detected": "detected target language",
    "error_type": "Accuracy|Mixed Script|Grammar|Terminology|Style & Tone|Formatting|Readability",
    "severity": "Minor|Major|Critical",
    "wrong_part": "specific wrong fragment in the translation",
    "suggestion": "corrected translation or fix",
    "explanation": "brief, specific reason"
  }}
]

Only include entries where a real error is found.
If all segments are correct, return [].

Severity guide:
Minor = typo, punctuation, spacing, or small grammar issue.
Major = wrong meaning, missing content, wrong script, serious terminology issue.
Critical = offensive, unsafe, legally dangerous, or completely incomprehensible.
"""

    try:
        result = call_openai_json(system_instructions, user_prompt, max_output_tokens=4096)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def ai_qa_monolingual(text, location, domain_value, strictness_value):
    """
    Fallback QA when no source column is available.
    """
    system_instructions = (
        "You are an expert multilingual linguistic QA specialist. "
        "You review text for language quality issues and return only valid JSON."
    )

    user_prompt = f"""
Analyze this text for quality issues.

Domain: {domain_value}
Strictness: {STRICTNESS_GUIDE[strictness_value]}

Location: {location}

Text:
\"\"\"{text}\"\"\"

Check:
- Grammar
- Spelling
- Punctuation
- Mixed language/script
- Style
- Formatting
- Placeholder issues

Return ONLY a valid JSON array. No markdown. No explanation outside JSON.

Required JSON format:
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

If no errors, return [].
"""

    try:
        result = call_openai_json(system_instructions, user_prompt, max_output_tokens=2048)
        return result if isinstance(result, list) else []
    except Exception:
        return []


# ---------------- Column Detection ----------------
def detect_source_target_columns(headers, source_hint="", target_hint=""):
    headers_lower = [str(h).lower().strip() for h in headers]

    source_keywords = [
        "source text",
        "source",
        "src",
        "english",
        "en"
    ]

    target_keywords = [
        "original translation",
        "translation",
        "target",
        "translated",
        "suggested translation",
        "tgt",
        "output",
        "localized"
    ]

    def find_col(hint, keywords):
        if hint:
            hint_clean = hint.lower().strip()

            for i, h in enumerate(headers_lower):
                if h == hint_clean:
                    return i

            try:
                idx = int(hint_clean)

                # Accept both user-friendly 1-based index and Python 0-based index.
                if 1 <= idx <= len(headers):
                    return idx - 1

                if 0 <= idx < len(headers):
                    return idx

            except ValueError:
                pass

            for i, h in enumerate(headers_lower):
                if hint_clean in h:
                    return i

        for keyword in keywords:
            for i, h in enumerate(headers_lower):
                if keyword in h:
                    return i

        return None

    src_idx = find_col(source_hint, source_keywords)
    tgt_idx = find_col(target_hint, target_keywords)

    if src_idx is not None and tgt_idx is None:
        possible = src_idx + 1
        tgt_idx = possible if possible < len(headers) else None

    if tgt_idx is not None and src_idx is None:
        possible = tgt_idx - 1
        src_idx = possible if possible >= 0 else None

    return src_idx, tgt_idx


def find_excel_header_row(rows):
    """
    Looks through the first 15 rows to find a likely header row.
    This helps with Excel review forms where the real table header is not row 1.
    """
    max_scan = min(len(rows), 15)

    for row_index in range(max_scan):
        headers = [
            str(cell.value).strip() if cell.value is not None else ""
            for cell in rows[row_index]
        ]

        src_idx, tgt_idx = detect_source_target_columns(
            headers,
            source_col_hint,
            target_col_hint
        )

        if src_idx is not None and tgt_idx is not None:
            return row_index, headers, src_idx, tgt_idx

    if not rows:
        return 0, [], None, None

    headers = [
        str(cell.value).strip() if cell.value is not None else ""
        for cell in rows[0]
    ]

    return 0, headers, None, None


# ---------------- File Processors ----------------
def process_excel(uploaded_file, progress_bar, status_text):
    wb = load_workbook(uploaded_file)
    report_rows = []

    for ws in wb.worksheets:
        if ws.title in REPORT_SHEETS:
            continue

        rows = list(ws.iter_rows(values_only=False))

        if not rows:
            continue

        header_row_index, header_row, src_idx, tgt_idx = find_excel_header_row(rows)

        if src_idx is not None and tgt_idx is not None:
            source_header = header_row[src_idx] if src_idx < len(header_row) else "Source"
            target_header = header_row[tgt_idx] if tgt_idx < len(header_row) else "Translation"

            status_text.text(
                f"Sheet '{ws.title}': bilingual mode [{source_header}] -> [{target_header}]"
            )

            pairs = []
            cell_map = {}

            data_rows = rows[header_row_index + 1:]

            for absolute_row_index, row in enumerate(data_rows, start=header_row_index + 2):
                if len(row) <= max(src_idx, tgt_idx):
                    continue

                src_val = normalize_text(row[src_idx].value or "")
                tgt_val = normalize_text(row[tgt_idx].value or "")

                if src_val and tgt_val and len(src_val) > 2 and not src_val.startswith("["):
                    loc = f"Row {absolute_row_index}"
                    pairs.append({
                        "source": src_val,
                        "translation": tgt_val,
                        "location": loc
                    })
                    cell_map[loc] = row[tgt_idx]

            pairs = pairs[:max_segments]
            total_batches = max(1, (len(pairs) + BATCH_SIZE - 1) // BATCH_SIZE)

            for batch_index in range(total_batches):
                batch = pairs[batch_index * BATCH_SIZE:(batch_index + 1) * BATCH_SIZE]

                if not batch:
                    continue

                start_seg = batch_index * BATCH_SIZE + 1
                end_seg = min((batch_index + 1) * BATCH_SIZE, len(pairs))

                status_text.text(
                    f"Sheet '{ws.title}': checking segments {start_seg}-{end_seg} of {len(pairs)}"
                )

                progress_bar.progress((batch_index + 1) / total_batches)

                errors = ai_qa_bilingual_batch(batch, domain, strictness)

                for err in errors:
                    loc = err.get("location", "")
                    lang = err.get("language_detected", "Unknown")

                    report_rows.append(
                        build_report_row(
                            ws.title,
                            loc,
                            lang,
                            err.get("source", ""),
                            err.get("translation", ""),
                            err
                        )
                    )

                    if loc in cell_map:
                        cell_map[loc].fill = HIGHLIGHT_FILL

                        existing = cell_map[loc].comment.text if cell_map[loc].comment else ""

                        note = (
                            f"[{err.get('severity', '').upper()}] {err.get('error_type', '')}\n"
                            f"Issue: {err.get('wrong_part', '')}\n"
                            f"Fix: {err.get('suggestion', '')}\n"
                            f"Why: {err.get('explanation', '')}"
                        )

                        combined = (existing + "\n\n" + note).strip() if existing else note
                        cell_map[loc].comment = Comment(combined, "ErrorSweep")

        else:
            status_text.text(
                f"Sheet '{ws.title}': no source/translation columns found — single-text QA mode"
            )

            all_cells = [
                cell
                for row in rows
                for cell in row
                if cell.value and isinstance(cell.value, str) and len(cell.value.strip()) > 3
            ]

            total = min(len(all_cells), max_segments)

            for idx, cell in enumerate(all_cells[:max_segments]):
                text = normalize_text(cell.value)

                status_text.text(
                    f"Sheet '{ws.title}': checking cell {idx + 1}/{total} ({cell.coordinate})"
                )

                if total > 0:
                    progress_bar.progress((idx + 1) / total)

                errors = ai_qa_monolingual(text, cell.coordinate, domain, strictness)

                if errors:
                    cell.fill = HIGHLIGHT_FILL
                    notes = []

                    for err in errors:
                        report_rows.append(
                            build_report_row(
                                ws.title,
                                cell.coordinate,
                                err.get("language_detected", "Unknown"),
                                "",
                                text,
                                err
                            )
                        )

                        notes.append(
                            f"[{err.get('severity', '').upper()}] {err.get('error_type', '')}\n"
                            f"Issue: {err.get('wrong_part', err.get('original', ''))}\n"
                            f"Fix: {err.get('suggestion', '')}\n"
                            f"Why: {err.get('explanation', '')}"
                        )

                    cell.comment = Comment("\n\n".join(notes), "ErrorSweep")

    for report_sheet_name in REPORT_SHEETS:
        if report_sheet_name in wb.sheetnames:
            del wb[report_sheet_name]

    rpt = wb.create_sheet("ErrorSweep Report")

    headers = [
        "Sheet",
        "Location",
        "Language",
        "Source Text",
        "Translation",
        "Error Type",
        "Severity",
        "Wrong Part",
        "Suggestion",
        "Explanation"
    ]

    rpt.append(headers)

    for item in report_rows:
        rpt.append([item.get(h, "") for h in headers])

    style_header(rpt)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return output, report_rows, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def process_csv(uploaded_file, progress_bar, status_text):
    df = pd.read_csv(uploaded_file)
    report_rows = []

    src_idx, tgt_idx = detect_source_target_columns(
        list(df.columns),
        source_col_hint,
        target_col_hint
    )

    if src_idx is not None and tgt_idx is not None:
        src_col = df.columns[src_idx]
        tgt_col = df.columns[tgt_idx]

        status_text.text(f"Bilingual mode: [{src_col}] -> [{tgt_col}]")

        pairs = []

        for i, row in df.iterrows():
            source_value = normalize_text(str(row[src_col])) if pd.notna(row[src_col]) else ""
            target_value = normalize_text(str(row[tgt_col])) if pd.notna(row[tgt_col]) else ""

            if source_value and target_value and len(source_value) > 2:
                pairs.append({
                    "source": source_value,
                    "translation": target_value,
                    "location": f"Row {i + 2}"
                })

        pairs = pairs[:max_segments]
        total_batches = max(1, (len(pairs) + BATCH_SIZE - 1) // BATCH_SIZE)

        for batch_index in range(total_batches):
            batch = pairs[batch_index * BATCH_SIZE:(batch_index + 1) * BATCH_SIZE]

            if not batch:
                continue

            start_seg = batch_index * BATCH_SIZE + 1
            end_seg = min((batch_index + 1) * BATCH_SIZE, len(pairs))

            status_text.text(
                f"Checking segments {start_seg}-{end_seg} of {len(pairs)}"
            )

            progress_bar.progress((batch_index + 1) / total_batches)

            errors = ai_qa_bilingual_batch(batch, domain, strictness)

            for err in errors:
                report_rows.append(
                    build_report_row(
                        "CSV",
                        err.get("location", ""),
                        err.get("language_detected", "Unknown"),
                        err.get("source", ""),
                        err.get("translation", ""),
                        err
                    )
                )

    else:
        segments = [
            (col, index, str(value))
            for col in df.columns
            for index, value in df[col].items()
            if pd.notna(value) and isinstance(value, str) and len(str(value).strip()) > 3
        ]

        total = min(len(segments), max_segments)

        for idx, (col, index, text) in enumerate(segments[:max_segments]):
            status_text.text(f"Checking segment {idx + 1}/{total}")

            if total > 0:
                progress_bar.progress((idx + 1) / total)

            errors = ai_qa_monolingual(
                normalize_text(text),
                f"Row {index + 2}, Col: {col}",
                domain,
                strictness
            )

            for err in errors:
                report_rows.append(
                    build_report_row(
                        "CSV",
                        f"Row {index + 2}, Col: {col}",
                        err.get("language_detected", "Unknown"),
                        "",
                        text,
                        err
                    )
                )

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)

    return output, report_rows, "text/csv"


def process_text_based(uploaded_file, progress_bar, status_text):
    text = uploaded_file.read().decode("utf-8", errors="ignore")

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip() and len(line.strip()) > 3
    ]

    report_rows = []
    total = min(len(lines), max_segments)

    pairs = []

    for i, line in enumerate(lines[:max_segments]):
        parts = line.split("\t")

        if len(parts) >= 2 and len(parts[0].strip()) > 2 and len(parts[1].strip()) > 2:
            pairs.append({
                "source": parts[0].strip(),
                "translation": parts[1].strip(),
                "location": f"Line {i + 1}"
            })

    if total > 0 and len(pairs) > total // 2:
        status_text.text("Detected tab-separated pairs — using bilingual mode")

        total_batches = max(1, (len(pairs) + BATCH_SIZE - 1) // BATCH_SIZE)

        for batch_index in range(total_batches):
            batch = pairs[batch_index * BATCH_SIZE:(batch_index + 1) * BATCH_SIZE]

            if not batch:
                continue

            start_pair = batch_index * BATCH_SIZE + 1
            end_pair = min((batch_index + 1) * BATCH_SIZE, len(pairs))

            status_text.text(
                f"Checking pairs {start_pair}-{end_pair} of {len(pairs)}"
            )

            progress_bar.progress((batch_index + 1) / total_batches)

            errors = ai_qa_bilingual_batch(batch, domain, strictness)

            for err in errors:
                report_rows.append(
                    build_report_row(
                        "File",
                        err.get("location", ""),
                        err.get("language_detected", "Unknown"),
                        err.get("source", ""),
                        err.get("translation", ""),
                        err
                    )
                )
    else:
        for idx, line in enumerate(lines[:max_segments]):
            status_text.text(f"Checking line {idx + 1}/{total}")

            if total > 0:
                progress_bar.progress((idx + 1) / total)

            errors = ai_qa_monolingual(
                normalize_text(line),
                f"Line {idx + 1}",
                domain,
                strictness
            )

            for err in errors:
                report_rows.append(
                    build_report_row(
                        "File",
                        f"Line {idx + 1}",
                        err.get("language_detected", "Unknown"),
                        "",
                        line,
                        err
                    )
                )

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)

    return output, report_rows, "text/csv"


def process_docx(uploaded_file, progress_bar, status_text):
    doc = Document(uploaded_file)
    report_rows = []

    paragraphs = [
        p.text.strip()
        for p in doc.paragraphs
        if p.text.strip() and len(p.text.strip()) > 3
    ]

    total = min(len(paragraphs), max_segments)

    for idx, text in enumerate(paragraphs[:max_segments]):
        status_text.text(f"Checking paragraph {idx + 1}/{total}")

        if total > 0:
            progress_bar.progress((idx + 1) / total)

        errors = ai_qa_monolingual(
            normalize_text(text),
            f"Paragraph {idx + 1}",
            domain,
            strictness
        )

        for err in errors:
            report_rows.append(
                build_report_row(
                    "Document",
                    f"Paragraph {idx + 1}",
                    err.get("language_detected", "Unknown"),
                    "",
                    text,
                    err
                )
            )

    output = io.BytesIO()
    output.write(pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8"))
    output.seek(0)

    return output, report_rows, "text/csv"


# ---------------- Main UI ----------------
col_upload, col_info = st.columns([3, 1])

with col_upload:
    st.markdown("#### Upload Your File")

    uploaded_file = st.file_uploader(
        "Drop any file — AI detects language and errors automatically",
        type=["xlsx", "csv", "txt", "json", "xml", "xliff", "srt", "docx"],
        label_visibility="collapsed"
    )

with col_info:
    st.markdown("#### What AI checks")

    checks = [
        "Source vs translation accuracy",
        "Mixed script detection",
        "Grammar and spelling",
        "Terminology",
        "Mixed language",
        "Style and tone",
        "Formatting and placeholders"
    ]

    for item in checks:
        st.markdown(f"<small>- {item}</small>", unsafe_allow_html=True)

st.divider()

run_button = st.button(
    "Run AI QA Check",
    use_container_width=True,
    type="primary",
    disabled=not uploaded_file
)


if uploaded_file and run_button:
    start_time = time.time()

    st.markdown("---")

    status_text = st.empty()
    progress_bar = st.progress(0)

    lower_name = uploaded_file.name.lower()

    try:
        if lower_name.endswith(".xlsx"):
            output, report_rows, mime_type = process_excel(
                uploaded_file,
                progress_bar,
                status_text
            )

        elif lower_name.endswith(".csv"):
            output, report_rows, mime_type = process_csv(
                uploaded_file,
                progress_bar,
                status_text
            )

        elif lower_name.endswith(".docx"):
            output, report_rows, mime_type = process_docx(
                uploaded_file,
                progress_bar,
                status_text
            )

        else:
            output, report_rows, mime_type = process_text_based(
                uploaded_file,
                progress_bar,
                status_text
            )

        progress_bar.progress(1.0)
        status_text.text("QA complete.")

        processing_time = round(time.time() - start_time, 2)

        if report_rows:
            df = pd.DataFrame(report_rows)

            critical_count = len(df[df["Severity"] == "Critical"])
            major_count = len(df[df["Severity"] == "Major"])
            minor_count = len(df[df["Severity"] == "Minor"])

            languages_found = ", ".join(
                [str(x) for x in df["Language"].dropna().unique() if str(x).strip()]
            )

            st.markdown("### QA Summary")

            c1, c2, c3, c4, c5 = st.columns(5)

            c1.metric("Total Errors", len(df))
            c2.metric("Critical", critical_count)
            c3.metric("Major", major_count)
            c4.metric("Minor", minor_count)
            c5.metric("Seconds", processing_time)

            if languages_found:
                st.info(f"Languages detected: {languages_found}")

            st.markdown("### Errors by Type")

            type_counts = df["Error Type"].value_counts().reset_index()
            type_counts.columns = ["Error Type", "Count"]

            st.dataframe(
                type_counts,
                use_container_width=True,
                hide_index=True
            )

            st.markdown("### Detailed Findings")

            for _, row in df.iterrows():
                severity_value = str(row["Severity"]).lower()

                if severity_value not in ["minor", "major", "critical"]:
                    severity_value = "minor"

                badge = (
                    f'<span class="severity-badge sev-{severity_value}">'
                    f'{row["Severity"]}'
                    f'</span>'
                )

                source_html = ""

                if row.get("Source Text"):
                    source_html = (
                        f'<div class="error-source">'
                        f'Source: {str(row["Source Text"])[:120]}'
                        f'</div>'
                    )

                wrong_part = row["Wrong Part"] or str(row["Translation"])[:80]

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

            st.download_button(
                label="Download Full QA Report",
                data=output.getvalue(),
                file_name="errorsweep_report_" + uploaded_file.name,
                mime=mime_type,
                use_container_width=True,
                type="primary"
            )

        else:
            progress_bar.empty()
            status_text.empty()
            st.success("No errors found. Your file looks clean.")

    except Exception as e:
        st.error(f"Error during processing: {str(e)}")
        st.exception(e)


elif not uploaded_file:
    st.markdown("""
    <div class="empty-state">
        <div style="font-family:'Space Mono',monospace; margin-top:12px; color:#666">
            Upload a file to begin AI QA
        </div>
        <div style="font-size:13px; margin-top:8px; color:#444">
            Supports .xlsx · .csv · .docx · .txt · .xliff · .srt · .json · .xml
        </div>
        <div style="font-size:12px; margin-top:12px; color:#555">
            For Excel/CSV: AI auto-detects source and translation columns,
            or set column names in the sidebar.
        </div>
    </div>
    """, unsafe_allow_html=True)
