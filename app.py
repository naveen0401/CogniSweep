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

# ─── Page Config & CSS ───────────────────────────────────────────────────────
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
.error-card { background: #0f0f1a; border-left: 3px solid #ff4466; border-radius: 0 8px 8px 0; padding: 16px; margin-bottom: 12px; }
.error-type { font-family: 'Space Mono', monospace; font-size: 11px; color: #8888aa; text-transform: uppercase; }
.error-before { color: #ff6680; font-size: 14px; }
.error-after  { color: #00ff88; font-size: 14px; }
.severity-badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-family: 'Space Mono', monospace; }
.sev-minor { background: rgba(255,170,0,0.15); color: #ffaa00; }
.sev-major { background: rgba(255,68,102,0.15); color: #ff4466; }
.sev-critical { background: rgba(255,0,68,0.2); color: #ff0044; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="hero-title">🧹 ErrorSweep Pro</div><div class="hero-sub">AI-powered Linguistic QA (GPT-5.5 Pro)</div></div>', unsafe_allow_html=True)

# ─── Sidebar Settings ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ QA Settings")
    domain = st.selectbox("Content Domain", ["General", "Software UI", "Subtitles", "Linguistic Query Resolutions"])
    strictness = st.select_slider("QA Strictness", options=["Lenient", "Standard", "Strict", "Very Strict"], value="Standard")
    max_segments = st.number_input("Max segments", min_value=1, max_value=200, value=50)

# ─── Core Logic ──────────────────────────────────────────────────────────────
def ai_qa_segment(text, domain, strictness, client):
    if not text or not text.strip(): return []
    
    prompt = f"Perform linguistic QA on this {domain} text: '{text}'. Strictness: {strictness}. Return ONLY a JSON object with an 'errors' list."
    
    try:
        response = client.chat.completions.create(
            model="gpt-5.5-pro", #
            messages=[{"role": "system", "content": "You are a QA specialist. Output JSON."}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"} #
        )
        return json.loads(response.choices[0].message.content).get("errors", [])
    except Exception as e:
        st.error(f"AI Error: {e}")
        return []

# ─── Main UI & File Upload ───────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload File", type=["xlsx", "csv", "docx", "txt"])

# 🔑 PASTE YOUR KEY HERE
api_key = os.environ.get("OPENAI_API_KEY") or "YOUR_OPENAI_API_KEY_HERE"

if uploaded_file:
    run_button = st.button("🚀 Run AI QA Check", type="primary", use_container_width=True)

    if run_button:
        if not api_key or "YOUR_OPENAI_API_KEY_HERE" in api_key:
            st.error("Please add your OpenAI API Key!")
            st.stop()

        client = OpenAI(api_key=api_key)
        progress_bar = st.progress(0)
        status_text = st.empty()
        report_rows = []

        # Simple Text/CSV Processor logic for brevity
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            total = min(len(df), max_segments)
            for i, row in df.head(total).iterrows():
                status_text.text(f"Checking row {i+1}...")
                progress_bar.progress((i+1)/total)
                text = str(row.iloc[0])
                errors = ai_qa_segment(text, domain, strictness, client)
                for e in errors:
                    e['Location'] = f"Row {i+1}"; e['Original Text'] = text
                    report_rows.append(e)
        
        # Display Results
        if report_rows:
            st.success(f"Found {len(report_rows)} errors!")
            for row in report_rows:
                sev = row.get('severity', 'Minor').lower()
                st.markdown(f"""
                <div class="error-card">
                    <div class="error-type">{row.get('error_type')} <span class="severity-badge sev-{sev}">{sev}</span></div>
                    <div class="error-before">✗ {row.get('original')}</div>
                    <div class="error-after">✓ {row.get('suggestion')}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.balloons()
            st.success("No errors found!")
