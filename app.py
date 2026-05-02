import streamlit as st
import pandas as pd
import io
import json
import os
from openai import OpenAI
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.comments import Comment

# ─── Page Setup ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="ErrorSweep Pro | Strong Mode", layout="wide")

# ─── Core AI Logic ───────────────────────────────────────────────────────────
def ai_qa_segment(text, domain, strictness, client):
    if not text or len(str(text).strip()) < 1:
        return []

    # Stronger prompt focusing on Linguistic nuances
    prompt = f"""Act as a Senior Linguistic Auditor. 
    Analyze this text from the '{domain}' domain with {strictness} strictness.
    
    TEXT TO AUDIT: "{text}"

    CRITICAL CHECKLIST:
    1. Mistranslation: Does it accurately convey the source meaning?
    2. Unicode: Check for normalization errors (NFC/NFD) in Indic scripts.
    3. Grammar/Spelling: Flag any typos or syntax issues.
    4. Terminology: Is it consistent with professional industry standards?

    Respond ONLY in JSON format:
    {{
      "errors": [
        {{
          "error_type": "Specific Type",
          "severity": "Minor/Major/Critical",
          "original": "the exact mistake",
          "suggestion": "your correction",
          "explanation": "why this is a bug"
        }}
      ]
    }}
    If NO errors exist, return {{"errors": []}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-5.5-pro", # Using high-reasoning model
            messages=[{"role": "system", "content": "You are a specialized LQA tool. Output valid JSON."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"} # Force valid JSON
        )
        return json.loads(response.choices[0].message.content).get("errors", [])
    except Exception as e:
        st.sidebar.error(f"API Debug: {e}")
        return []

# ─── Main Application ────────────────────────────────────────────────────────
st.title("🧹 ErrorSweep Pro: Strong Mode")

# API Key - Paste your sk-... key here or set it in Streamlit Secrets
api_key = os.environ.get("OPENAI_API_KEY") or "YOUR_OPENAI_API_KEY_HERE"

with st.sidebar:
    st.header("Settings")
    domain = st.selectbox("Domain", ["Software UI", "Subtitles", "Linguistic Query", "General"])
    strictness = st.select_slider("Strictness", ["Lenient", "Standard", "Strict", "Audit Mode"], value="Strict")
    max_rows = st.number_input("Scan Limit (Rows)", 1, 500, 50)

uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])

if uploaded_file and st.button("🚀 Start Deep Scan"):
    if not api_key or "YOUR" in api_key:
        st.error("Please provide a valid OpenAI API Key.")
        st.stop()

    client = OpenAI(api_key=api_key)
    
    # Load Data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.info(f"Scanning first {min(len(df), max_rows)} rows across all columns...")
    
    results = []
    progress = st.progress(0)
    
    # SCANNING LOGIC: Checks every cell in the row
    for i, row in df.head(max_rows).iterrows():
        for col_name, cell_value in row.items():
            if pd.notna(cell_value) and len(str(cell_value)) > 1:
                errors = ai_qa_segment(str(cell_value), domain, strictness, client)
                for err in errors:
                    err['Location'] = f"Row {i+1}, Col: {col_name}"
                    results.append(err)
        progress.progress((i + 1) / min(len(df), max_rows))

    # Display Findings
    if results:
        st.subheader(f"🚩 Found {len(results)} Issues")
        for error in results:
            with st.expander(f"{error['error_type']} at {error['Location']}"):
                st.write(f"**Issue:** `{error['original']}`")
                st.success(f"**Correction:** {error['suggestion']}")
                st.info(f"**Reason:** {error['explanation']}")
    else:
        st.success("Deep Scan complete. No linguistic bugs detected.")
