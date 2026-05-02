import streamlit as st
import pandas as pd
import io
import time
import json
import os
import re
from openai import OpenAI  # Switched to OpenAI
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
    <div class="hero-sub">Fully AI-powered linguistic QA — Powered by ChatGPT GPT-5.5</div>
    <div class="hero-badge">✦ GPT-5.5 Pro &nbsp;·&nbsp; Auto language detection &nbsp;·&nbsp; Structured JSON output</div>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧹 ErrorSweep Pro")
    st.caption("v4.0 — OpenAI GPT-5.5 Pro")
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
         "E-learning / Education", "Linguistic Query Resolutions"], # Domain added based on your specific job role
        help="Helps ChatGPT apply domain-specific quality rules"
    )

    strictness = st.select_slider(
        "QA Strictness",
        options=["Lenient", "Standard", "Strict", "Very Strict"],
        value="Standard"
    )

    max_segments = st.number_input(
        "Max segments to check", min_value=1, max_value=200, value=50,
        help="Limit AI checks to control API cost"
    )

    st.divider()
    st.caption("💡 Tip: Use 'Strict' for professional subtitling/localization tasks.")

# ─── Constants ────────────────────────────────────────────────────────────────
HIGHLIGHT_FILL = PatternFill(start_color="FFF59D", end_color="FFF59D", fill_type="solid")
HEADER_FILL    = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
HEADER_FONT    = Font(bold=True)
REPORT_SHEETS  = ["ErrorSweep Report"]

# ─── Core AI QA ───────────────────────────────────────────────────────────────
def ai_qa_segment(text, domain, strictness, client):
    # Reduced minimum length to 1 to catch short UI strings (e.g., "Yes", "OK")
    if not text or not text.strip():
        return []

    strictness_guide = {
        "Lenient":     "Flag only critical errors. Ignore minor style issues.",
        "Standard":    "Flag clear errors and notable quality issues.",
        "Strict":      "Flag all errors including minor style, tone, and register.",
        "Very Strict": "Check for absolute precision, including technical normalization issues."
    }

    prompt = f"""Expert linguistic QA for: {domain}.
    
    Strictness Level: {strictness_guide[strictness]}

    ANALYZE THIS TEXT:
    "{text}"

    Instructions:
    1. Identify errors: Mistranslation, Terminology, Grammar, Spelling, Punctuation, Mixed Language, Unicode Normalization issues.
    2. Respond ONLY with a JSON object containing an "errors" array.
    3. If no errors, return: {{"errors": []}}

    Output Schema:
    {{
      "errors": [
        {{
          "language_detected": "Language Name",
          "error_type": "Mistranslation",
          "severity": "Minor|Major|Critical",
          "original": "the wrong part",
          "suggestion": "the correct version",
          "explanation": "why it is wrong"
        }}
      ]
    }}"""

    try:
        # Using GPT-5.5 Pro with Structured Outputs
        response = client.chat.completions.create(
            model="gpt-5.5-pro", 
            messages=[
                {"role": "system", "content": "You are a professional linguistic QA engine. Output strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_output = response.choices[0].message.content
        data = json.loads(raw_output)
        return data.get("errors", [])
    except Exception as e:
        st.error(f"AI API Error: {e}")
        return []


def normalize_text(text):
    # Preserving ZWJ/ZWNJ for Telugu scripts as they are linguistically critical
    return str(text).strip()


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

# (Processor functions remain largely the same, just utilizing the new OpenAI client)
# ... [Keeping process_excel, process_csv, etc. logic as per original]

# ─── Main UI ──────────────────────────────────────────────────────────────────
# ... [Keeping Upload UI logic]

# ─── API KEY CONFIGURATION ────────────────────────────────────────────────────
# Option 1: Read from Streamlit Secrets (Recommended)
# Option 2: Fallback to manual entry for testing
api_key = os.environ.get("OPENAI_API_KEY") or "YOUR_OPENAI_API_KEY_HERE"

if not api_key or "YOUR_OPENAI_API_KEY_HERE" in api_key:
    st.error("⚠️ OpenAI API Key missing! Set OPENAI_API_KEY in Secrets or paste it in the code.")
    st.stop()

run_button = st.button("🚀 Run AI QA Check", use_container_width=True, type="primary")

if uploaded_file and run_button:
    client = OpenAI(api_key=api_key) # Initialize OpenAI
    # ... [Rest of the processing loop]
