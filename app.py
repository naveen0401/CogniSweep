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

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="ErrorSweep Pro", layout="wide", page_icon="✅")

st.markdown("""
<style>
.title  {text-align:center;font-size:42px;color:#22C55E;font-weight:bold;margin-bottom:4px;}
.subtitle {text-align:center;font-size:16px;color:#9CA3AF;margin-bottom:20px;}
.badge  {display:inline-block;background:#22C55E;color:white;border-radius:12px;
         padding:2px 10px;font-size:12px;margin:2px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">✅ ErrorSweep Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">AI-powered multilingual QA automation — English · Hindi · Telugu</div>', unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/checked--v1.png", width=60)
    st.title("ErrorSweep Pro")

    st.subheader("🌐 Language")
    language = st.selectbox(
        "Select document language",
        ["English", "Hindi (हिंदी)", "Telugu (తెలుగు)"],
        help="This tells the AI which language rules to apply during QA"
    )

    st.subheader("📁 Supported Formats")
    for fmt in [".xlsx", ".csv", ".txt", ".json", ".xml", ".xliff", ".srt", ".docx"]:
        st.markdown(f'<span class="badge">{fmt}</span>', unsafe_allow_html=True)

    st.subheader("📋 Corrections CSV Format")
    st.code("wrong,correct,error_type,severity,status")
    st.caption("Only 'wrong' and 'correct' columns are required.")

    st.divider()
    st.subheader("🤖 AI Settings")
    use_ai = st.checkbox("Enable AI linguistic QA", value=True,
                         help="Uses Claude AI to detect grammar, fluency and mistranslation issues")
    max_ai_calls = st.number_input("Max AI checks per file", min_value=1, max_value=100, value=20)
    ai_max_chars  = st.number_input("Max chars per AI check", min_value=50, max_value=2000, value=500)

    st.divider()
    st.caption("ErrorSweep Pro v2.0 · Powered by Claude AI")

# ─── Constants ────────────────────────────────────────────────────────────────
HIGHLIGHT_FILL = PatternFill(start_color="FFF59D", end_color="FFF59D", fill_type="solid")
HEADER_FILL    = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
HEADER_FONT    = Font(bold=True)
REPORT_SHEETS  = ["Correction Report", "Remaining Errors"]

LANGUAGE_MAP = {
    "English":          "English",
    "Hindi (हिंदी)":    "Hindi",
    "Telugu (తెలుగు)":  "Telugu",
}

# ─── Helper: Load Corrections CSV ────────────────────────────────────────────
def load_corrections(file):
    corrections = pd.read_csv(file)
    if "wrong" not in corrections.columns or "correct" not in corrections.columns:
        st.error("❌ Corrections CSV must contain at least: wrong, correct")
        return None
    corrections["wrong"]   = corrections["wrong"].astype(str)
    corrections["correct"] = corrections["correct"].astype(str)
    return corrections

def get_value(row, key):
    return str(row[key]) if key in row and pd.notna(row[key]) else ""

# ─── Helper: Normalize Unicode ───────────────────────────────────────────────
def normalize_text(text):
    text = str(text)
    for ch in ["\u00A0", "\u200B", "\u200C", "\u200D"]:
        text = text.replace(ch, " " if ch == "\u00A0" else "")
    return text

# ─── Helper: Safe Replace ────────────────────────────────────────────────────
def safe_replace(text, wrong, correct):
    text  = normalize_text(text)
    wrong = normalize_text(wrong)
    pattern = re.compile(re.escape(wrong), re.IGNORECASE)
    matches = pattern.findall(text)
    if not matches:
        return text, 0
    return pattern.sub(correct, text), len(matches)

# ─── AI: Claude Linguistic QA ────────────────────────────────────────────────
def ai_suggest_fix(text, lang):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return text

    if not text or len(text) > ai_max_chars:
        return text

    try:
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = f"""You are a professional linguistic QA specialist for {lang} language content.
Your job is to fix ONLY:
- Spelling mistakes
- Grammar errors
- Punctuation issues
- Spacing/formatting problems
- Fluency issues (unnatural phrasing)
- Mistranslation markers (if you spot text that is clearly in the wrong language)

Rules:
- Do NOT change the meaning of the text
- Do NOT add or remove information
- Do NOT translate the text to another language
- Return ONLY the corrected text, nothing else
- If the text is already correct, return it exactly as is
- Preserve all original formatting, line breaks, and special characters"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"Fix linguistic errors in this {lang} text:\n\n{text}"
                }
            ],
            system=system_prompt
        )
        return message.content[0].text.strip()
    except Exception:
        return text

def apply_ai(text, location, report_rows, ai_state, lang):
    if not use_ai:
        return text
    if ai_state["calls"] >= max_ai_calls:
        return text
    if len(text) > ai_max_chars or not text.strip():
        return text

    ai_state["calls"] += 1
    ai_text = ai_suggest_fix(text, lang)

    if ai_text and ai_text != text:
        report_rows.append({
            "Sheet": "", "Location": location,
            "Before": text, "After": ai_text,
            "Wrong": "AI detected", "Correct": "AI suggestion",
            "Error Type": f"AI Linguistic QA ({lang})",
            "Severity": "Review", "Status": "Needs Review", "Fixed Count": 1
        })
        return ai_text
    return text

# ─── Helper: Style Excel Header ──────────────────────────────────────────────
def style_header(sheet):
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

# ─── Core: Apply Corrections to Text ─────────────────────────────────────────
def apply_corrections_to_text(text, corrections, location, sheet_name="", ai_state=None, lang="English"):
    report_rows = []
    new_text    = normalize_text(text)

    for _, row in corrections.iterrows():
        wrong      = str(row["wrong"])
        correct    = str(row["correct"])
        error_type = get_value(row, "error_type")
        severity   = get_value(row, "severity")
        status     = get_value(row, "status")

        before_value = new_text
        fixed_value, count = safe_replace(new_text, wrong, correct)

        if count > 0:
            new_text = fixed_value
            report_rows.append({
                "Sheet": sheet_name, "Location": location,
                "Before": before_value, "After": new_text,
                "Wrong": wrong, "Correct": correct,
                "Error Type": error_type, "Severity": severity,
                "Status": status, "Fixed Count": count
            })

    if ai_state is not None:
        new_text = apply_ai(new_text, location, report_rows, ai_state, lang)

    return new_text, report_rows

# ─── Processors ──────────────────────────────────────────────────────────────
def process_excel(uploaded_file, corrections, lang):
    wb         = load_workbook(uploaded_file)
    report_rows = []
    ai_state   = {"calls": 0}

    for ws in wb.worksheets:
        if ws.title in REPORT_SHEETS:
            continue
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                original_value = str(cell.value)
                fixed_value, reports = apply_corrections_to_text(
                    original_value, corrections,
                    location=cell.coordinate, sheet_name=ws.title,
                    ai_state=ai_state, lang=lang
                )
                if fixed_value != normalize_text(original_value):
                    cell.value   = fixed_value
                    cell.fill    = HIGHLIGHT_FILL
                    notes = [
                        f"Wrong: {r['Wrong']}\nCorrect: {r['Correct']}\n"
                        f"Error Type: {r['Error Type']}\nSeverity: {r['Severity']}\n"
                        f"Status: {r['Status']}\nFixed Count: {r['Fixed Count']}"
                        for r in reports
                    ]
                    cell.comment = Comment("\n\n".join(notes), "ErrorSweep")
                report_rows.extend(reports)

    for sn in REPORT_SHEETS:
        if sn in wb.sheetnames:
            del wb[sn]

    # Correction Report sheet
    rpt = wb.create_sheet("Correction Report")
    headers = ["Sheet","Location","Before","After","Wrong","Correct","Error Type","Severity","Status","Fixed Count"]
    rpt.append(headers)
    for item in report_rows:
        rpt.append([item.get(h, "") for h in headers])
    style_header(rpt)

    # Remaining Errors sheet
    rem = wb.create_sheet("Remaining Errors")
    rem.append(["Sheet","Location","Remaining Error","Error Type","Severity","Status"])
    for ws in wb.worksheets:
        if ws.title in REPORT_SHEETS:
            continue
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                cell_text = normalize_text(cell.value)
                for _, r in corrections.iterrows():
                    wrong   = str(r["wrong"])
                    pattern = re.compile(re.escape(normalize_text(wrong)), re.IGNORECASE)
                    if pattern.search(cell_text):
                        rem.append([ws.title, cell.coordinate, wrong,
                                    get_value(r,"error_type"), get_value(r,"severity"), "Remaining"])
    style_header(rem)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output, report_rows, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def process_csv(uploaded_file, corrections, lang):
    df          = pd.read_csv(uploaded_file)
    report_rows = []
    ai_state    = {"calls": 0}

    for col in df.columns:
        for index, value in df[col].items():
            if pd.isna(value):
                continue
            fixed_value, reports = apply_corrections_to_text(
                value, corrections,
                location=f"Row {index+2}, Column {col}",
                ai_state=ai_state, lang=lang
            )
            df.at[index, col] = fixed_value
            report_rows.extend(reports)

    output = io.BytesIO()
    output.write(df.to_csv(index=False).encode("utf-8"))
    output.seek(0)
    return output, report_rows, "text/csv"


def process_plain_text(uploaded_file, corrections, mime_type, lang):
    text      = uploaded_file.read().decode("utf-8", errors="ignore")
    ai_state  = {"calls": 0}
    fixed_text, report_rows = apply_corrections_to_text(
        text, corrections, location="File", ai_state=ai_state, lang=lang
    )
    output = io.BytesIO()
    output.write(fixed_text.encode("utf-8"))
    output.seek(0)
    return output, report_rows, mime_type


def process_json(uploaded_file, corrections, lang):
    text     = uploaded_file.read().decode("utf-8", errors="ignore")
    ai_state = {"calls": 0}
    fixed_text, report_rows = apply_corrections_to_text(
        text, corrections, location="JSON File", ai_state=ai_state, lang=lang
    )
    try:
        parsed     = json.loads(fixed_text)
        fixed_text = json.dumps(parsed, indent=2, ensure_ascii=False)
    except Exception:
        pass
    output = io.BytesIO()
    output.write(fixed_text.encode("utf-8"))
    output.seek(0)
    return output, report_rows, "application/json"


def process_docx(uploaded_file, corrections, lang):
    doc         = Document(uploaded_file)
    report_rows = []
    ai_state    = {"calls": 0}

    def fix_paragraph(paragraph, location):
        original = paragraph.text
        if not original.strip():
            return
        fixed, reports = apply_corrections_to_text(
            original, corrections, location=location,
            ai_state=ai_state, lang=lang
        )
        if fixed != normalize_text(original):
            paragraph.clear()
            paragraph.add_run(fixed)
        report_rows.extend(reports)

    for i, p in enumerate(doc.paragraphs, start=1):
        fix_paragraph(p, f"Paragraph {i}")

    for t_idx, table in enumerate(doc.tables, start=1):
        for r_idx, row in enumerate(table.rows, start=1):
            for c_idx, cell in enumerate(row.cells, start=1):
                for p in cell.paragraphs:
                    fix_paragraph(p, f"Table {t_idx}, Row {r_idx}, Cell {c_idx}")

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output, report_rows, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ─── Main UI ──────────────────────────────────────────────────────────────────
st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("📤 Upload Files")
    uploaded_file   = st.file_uploader(
        "Upload your document",
        type=["xlsx","csv","txt","json","xml","xliff","srt","docx"],
        help="The file you want to run QA on"
    )
    correction_file = st.file_uploader(
        "Upload corrections CSV",
        type=["csv"],
        help="CSV with wrong/correct pairs"
    )

with right:
    st.subheader("📦 Output Includes")
    features = [
        "✅ Corrected file download",
        "✅ Before vs After preview",
        "✅ Full correction report",
        "✅ Excel cell highlighting",
        "✅ AI linguistic QA",
        "✅ Hindi & Telugu support",
        "✅ Remaining errors sheet",
    ]
    for f in features:
        st.write(f)

st.divider()

# AI Key warning
if use_ai and not os.environ.get("ANTHROPIC_API_KEY"):
    st.warning("⚠️ AI QA is enabled but ANTHROPIC_API_KEY is not set. "
               "Add it in Streamlit Cloud → Settings → Secrets as: ANTHROPIC_API_KEY = 'your-key'")

run_button = st.button("🚀 Run QA Check", use_container_width=True, type="primary")

if uploaded_file and correction_file and run_button:
    lang        = LANGUAGE_MAP.get(language, "English")
    start_time  = time.time()
    corrections = load_corrections(correction_file)

    if corrections is not None:
        with st.spinner(f"Running QA on your {lang} document..."):
            lower_name = uploaded_file.name.lower()

            if lower_name.endswith(".xlsx"):
                output, report_rows, mime_type = process_excel(uploaded_file, corrections, lang)
            elif lower_name.endswith(".csv"):
                output, report_rows, mime_type = process_csv(uploaded_file, corrections, lang)
            elif lower_name.endswith(".txt"):
                output, report_rows, mime_type = process_plain_text(uploaded_file, corrections, "text/plain", lang)
            elif lower_name.endswith((".xml", ".xliff")):
                output, report_rows, mime_type = process_plain_text(uploaded_file, corrections, "application/xml", lang)
            elif lower_name.endswith(".srt"):
                output, report_rows, mime_type = process_plain_text(uploaded_file, corrections, "text/plain", lang)
            elif lower_name.endswith(".json"):
                output, report_rows, mime_type = process_json(uploaded_file, corrections, lang)
            elif lower_name.endswith(".docx"):
                output, report_rows, mime_type = process_docx(uploaded_file, corrections, lang)
            else:
                st.error("❌ Unsupported file format.")
                st.stop()

        processing_time = round(time.time() - start_time, 2)
        st.success(f"✅ File processed successfully in {processing_time}s")

        if report_rows:
            report_df = pd.DataFrame(report_rows)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Fixes",     int(report_df["Fixed Count"].sum()))
            col2.metric("Changed Items",   len(report_df))
            col3.metric("Language",        lang)
            col4.metric("Time (sec)",      processing_time)

            ai_fixes   = report_df[report_df["Wrong"] == "AI detected"]
            rule_fixes = report_df[report_df["Wrong"] != "AI detected"]

            if not rule_fixes.empty:
                st.subheader("📋 Rule-Based Corrections")
                st.dataframe(rule_fixes.head(50), use_container_width=True)

            if not ai_fixes.empty:
                st.subheader("🤖 AI Linguistic QA Suggestions")
                st.caption("These require human review before accepting")
                st.dataframe(ai_fixes.head(50), use_container_width=True)
        else:
            st.info("ℹ️ No matching errors found.")

        st.download_button(
            label="⬇️ Download Fixed File",
            data=output.getvalue(),
            file_name="fixed_" + uploaded_file.name,
            mime=mime_type,
            use_container_width=True,
            type="primary"
        )

elif uploaded_file and correction_file:
    st.info("📁 Files uploaded. Click **Run QA Check** to process.")
else:
    st.info("👆 Upload your document and corrections CSV to get started.")
