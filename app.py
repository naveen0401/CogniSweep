import streamlit as st
import pandas as pd
import io
import json
import os
from google import genai  # Switched to Google GenAI
from openpyxl import load_workbook

# ─── Page Setup ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="ErrorSweep Pro | Gemini Mode", layout="wide")

# ─── Core AI Logic ───────────────────────────────────────────────────────────
def ai_qa_segment(text, domain, strictness, client):
    if not text or len(str(text).strip()) < 1:
        return []

    prompt = f"""Act as a Senior Linguistic Auditor. 
    Analyze this text from the '{domain}' domain with {strictness} strictness.
    TEXT: "{text}"
    Return ONLY a JSON object with an 'errors' list containing error_type, severity, original, suggestion, and explanation."""

    try:
        # Gemini 3 Flash is optimized for fast, accurate linguistic extraction
        response = client.models.generate_content(
            model="gemini-3-flash",
            contents=prompt,
            config={
                'response_mime_type': 'application/json', # Enforces structured JSON
            }
        )
        # Gemini responses are accessed via .text or .parsed if a schema is used
        return json.loads(response.text).get("errors", [])
    except Exception as e:
        st.sidebar.error(f"Gemini API Error: {e}")
        return []

# ─── Main Application ────────────────────────────────────────────────────────
st.title("🧹 ErrorSweep Pro: Gemini Mode")

# 🔑 PASTE YOUR GOOGLE API KEY HERE
api_key = os.environ.get("GEMINI_API_KEY") or "YOUR_GOOGLE_API_KEY_HERE"

with st.sidebar:
    st.header("Settings")
    domain = st.selectbox("Domain", ["Software UI", "Subtitles", "Linguistic Query", "General"])
    strictness = st.select_slider("Strictness", ["Lenient", "Standard", "Strict", "Audit Mode"], value="Strict")
    max_rows = st.number_input("Scan Limit (Rows)", 1, 500, 50)

uploaded_file = st.file_uploader("Upload File", type=["csv", "xlsx"])

if uploaded_file and st.button("🚀 Start Gemini Deep Scan"):
    if not api_key or "YOUR" in api_key:
        st.error("Please provide a valid Google API Key (from AI Studio).")
        st.stop()

    # Initialize Google GenAI client
    client = genai.Client(api_key=api_key)
    
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    results = []
    progress = st.progress(0)
    
    # Deep Scan across all columns for maximum error detection
    for i, row in df.head(max_rows).iterrows():
        for col_name, cell_value in row.items():
            if pd.notna(cell_value) and len(str(cell_value)) > 1:
                errors = ai_qa_segment(str(cell_value), domain, strictness, client)
                for err in errors:
                    err['Location'] = f"Row {i+1}, Col: {col_name}"
                    results.append(err)
        progress.progress((i + 1) / min(len(df), max_rows))

    if results:
        st.subheader(f"🚩 Found {len(results)} Issues")
        for error in results:
            with st.expander(f"{error['error_type']} at {error['Location']}"):
                st.write(f"**Issue:** `{error['original']}`")
                st.success(f"**Correction:** {error['suggestion']}")
                st.info(f"**Reason:** {error['explanation']}")
    else:
        st.success("Gemini Scan complete. Your file is clean!")
