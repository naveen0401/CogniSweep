import streamlit as st
import pandas as pd
import io
import os
import re
import json
import time
import hmac
import zipfile
import math
import hashlib
import base64
import textwrap
from datetime import datetime, timezone
import requests
from typing import Any, Dict, List, Tuple, Optional
from html import escape
from urllib.parse import quote

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:
    Fernet = None
    InvalidToken = Exception

from openai import OpenAI as AI
from openpyxl import load_workbook, Workbook
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
# White-label AI QA + translation workflow
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

/* Hide Streamlit public toolbar/menu/footer, including fork/deploy controls where present */
#MainMenu {visibility: hidden; display: none;}
footer {visibility: hidden; display: none;}
header {visibility: hidden; display: none;}
[data-testid="stToolbar"] {visibility: hidden; display: none;}
[data-testid="stDecoration"] {visibility: hidden; display: none;}
[data-testid="stStatusWidget"] {visibility: hidden; display: none;}
[data-testid="stDeployButton"] {visibility: hidden; display: none;}
.stAppDeployButton {visibility: hidden; display: none;}

/* Premium white-label visual system */
:root {
    --es-green: #00ff88;
    --es-cyan: #38bdf8;
    --es-purple: #8b5cf6;
    --es-bg: #080a12;
    --es-card: rgba(16, 19, 34, 0.72);
}
.stApp {
    background:
        radial-gradient(circle at 12% 18%, rgba(0,255,136,0.14), transparent 25%),
        radial-gradient(circle at 86% 14%, rgba(56,189,248,0.12), transparent 28%),
        radial-gradient(circle at 50% 100%, rgba(139,92,246,0.10), transparent 35%),
        #080a12;
}
.hero {
    position: relative;
    overflow: hidden;
    background:
        linear-gradient(135deg, rgba(0,255,136,0.12), rgba(56,189,248,0.08) 42%, rgba(139,92,246,0.10)),
        rgba(12, 15, 26, 0.9);
    box-shadow: 0 28px 80px rgba(0,0,0,0.35);
}
.hero::after {
    content: "";
    position: absolute;
    width: 420px;
    height: 420px;
    right: -150px;
    top: -190px;
    background: radial-gradient(circle, rgba(0,255,136,0.22), transparent 62%);
    filter: blur(4px);
}
.hero-title {
    background: linear-gradient(90deg, #00ff88, #38bdf8, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.glass-card, div[data-testid="stExpander"] {
    background: rgba(16, 19, 34, 0.74) !important;
    border: 1px solid rgba(56,189,248,0.18) !important;
    border-radius: 16px !important;
    box-shadow: 0 18px 44px rgba(0,0,0,0.22);
}
.stButton > button, .stDownloadButton > button {
    border-radius: 14px !important;
    border: 1px solid rgba(0,255,136,0.25) !important;
    background: linear-gradient(90deg, #00cc6a, #0ea5e9) !important;
    color: white !important;
    font-weight: 800 !important;
    letter-spacing: .2px;
    box-shadow: 0 10px 28px rgba(14,165,233,0.20);
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 16px 36px rgba(0,255,136,0.20);
}
[data-testid="stMetric"] {
    background: rgba(16,19,34,.72);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 16px;
    padding: 16px;
}
.es-visual-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin: 18px 0 24px 0;
}
.es-tile {
    background: rgba(16, 19, 34, 0.74);
    border: 1px solid rgba(0,255,136,0.14);
    border-radius: 16px;
    padding: 18px;
}
.es-tile h4 { margin: 0 0 6px 0; color: #e5e7eb; }
.es-tile p { margin: 0; color: #9ca3af; font-size: 13px; }
@media (max-width: 900px) { .es-visual-grid { grid-template-columns: 1fr; } }

/* Stronger visibility + cleaner form UI */
h1, h2, h3, h4, h5, h6, p, li, label, div, span { color: #eef2ff; }
.block-container { padding-top: 1.2rem; padding-bottom: 3rem; }
[data-testid="stMarkdownContainer"] p { color: #d7def7; }
.stCaption, [data-testid="stCaptionContainer"] { color: #9fb0d6 !important; }
.stAlert { border-radius: 16px !important; }
[data-testid="stExpander"] details summary p,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] label { color: #eef2ff !important; font-weight: 700 !important; }
[data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"],
[data-baseweb="select"],
[data-testid="stTextArea"],
[data-testid="stFileUploaderDropzone"] {
    background: rgba(10,14,27,0.92) !important;
    border: 1px solid rgba(56,189,248,0.18) !important;
    border-radius: 16px !important;
}
input, textarea { color: #f8fbff !important; }
[data-baseweb="select"] * { color: #f8fbff !important; }
[data-testid="stCheckbox"] label, [role="radiogroup"] label { color: #e7ecff !important; font-weight: 600 !important; }
.es-page-header-card {
    background: linear-gradient(135deg, rgba(0,255,136,.08), rgba(56,189,248,.06), rgba(139,92,246,.08));
    border: 1px solid rgba(56,189,248,.16);
    border-radius: 20px;
    padding: 18px 20px;
    margin: 10px 0 16px 0;
}
.es-page-header-card h3 { margin: 0; color: #f8fbff; font-size: 24px; }
.es-page-header-card p { margin: 8px 0 0 0; color: #a8b8dc; }
.es-pill-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.es-pill {
    display: inline-flex; align-items: center; gap: 8px; padding: 7px 12px; border-radius: 999px;
    font-size: 12px; font-weight: 700; color: #dff6ff; background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.08);
}
.es-pill.green { color: #90f6c4; border-color: rgba(0,255,136,.18); background: rgba(0,255,136,.08); }
.es-pill.blue { color: #9bddff; border-color: rgba(56,189,248,.18); background: rgba(56,189,248,.08); }
.es-pill.purple { color: #ddc6ff; border-color: rgba(139,92,246,.20); background: rgba(139,92,246,.08); }
.es-subsection-title { font-size: 18px; font-weight: 800; color: #f8fbff; margin: 8px 0 10px 0; }
.es-soft-card {
    background: rgba(16,19,34,.78); border: 1px solid rgba(56,189,248,.14); border-radius: 18px; padding: 16px;
}
.es-soft-card p { margin: 0; color: #aab9db; }

.account-hero {
    background: linear-gradient(135deg, rgba(8,14,26,.92), rgba(17,23,43,.92));
    border: 1px solid rgba(56,189,248,.16);
    border-radius: 22px;
    padding: 26px;
    margin: 8px 0 18px 0;
    box-shadow: 0 22px 50px rgba(0,0,0,.26);
}
.account-hero-grid {
    display: grid;
    grid-template-columns: 120px 1.5fr 1fr;
    gap: 20px;
    align-items: center;
}
.account-avatar {
    width: 96px;
    height: 96px;
    border-radius: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Mono', monospace;
    font-size: 34px;
    font-weight: 700;
    color: white;
    background: linear-gradient(135deg, rgba(0,255,136,.9), rgba(56,189,248,.9));
    box-shadow: 0 16px 30px rgba(14,165,233,.22);
}
.account-title {
    font-size: 30px;
    line-height: 1.1;
    font-weight: 800;
    color: #eef2ff;
    margin: 0;
}
.account-subline {
    color: #9fb0d6;
    font-size: 15px;
    margin-top: 8px;
}
.account-badge-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 14px;
}
.account-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 999px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .15px;
    border: 1px solid rgba(255,255,255,.08);
    background: rgba(255,255,255,.04);
    color: #e8ecfb;
}
.account-pill.plan { background: rgba(0,255,136,.10); color: #8df2c1; border-color: rgba(0,255,136,.20); }
.account-pill.role { background: rgba(56,189,248,.10); color: #8fdcff; border-color: rgba(56,189,248,.20); }
.account-pill.status { background: rgba(250,204,21,.10); color: #fde68a; border-color: rgba(250,204,21,.20); }
.account-pill.security { background: rgba(139,92,246,.10); color: #d8b4fe; border-color: rgba(139,92,246,.20); }
.account-kpi-wrap {
    display: grid;
    grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 12px;
}
.account-kpi {
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 16px;
    padding: 14px;
}
.account-kpi-label { color: #90a3c8; font-size: 12px; text-transform: uppercase; letter-spacing: .8px; }
.account-kpi-value { color: #f8fafc; font-size: 26px; font-weight: 800; margin-top: 4px; }
.account-kpi-sub { color: #8fa0c3; font-size: 12px; margin-top: 2px; }
.account-section-title {
    margin: 6px 0 12px 0;
    font-size: 22px;
    font-weight: 800;
    color: #eef2ff;
}
.account-info-card {
    background: rgba(16, 19, 34, 0.74);
    border: 1px solid rgba(56,189,248,0.16);
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 12px;
    min-height: 100%;
}
.account-info-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 14px 18px;
}
.account-info-item { min-width: 0; }
.account-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: #86a0c8;
}
.account-value {
    font-size: 15px;
    color: #edf2ff;
    font-weight: 600;
    margin-top: 4px;
    word-break: break-word;
}
.account-soft-note {
    background: rgba(56,189,248,.07);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 14px;
    padding: 12px 14px;
    color: #a9bbdd;
    font-size: 13px;
    margin-top: 10px;
}
.account-activity-empty {
    border: 1px dashed rgba(56,189,248,.2);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    color: #97a8c8;
    background: rgba(255,255,255,.02);
}
@media (max-width: 900px) {
    .account-hero-grid { grid-template-columns: 1fr; }
    .account-kpi-wrap, .account-info-grid { grid-template-columns: 1fr; }
    .account-avatar { width: 84px; height: 84px; font-size: 28px; }
}


.workflow-hero-card {
    background: linear-gradient(135deg, rgba(0,255,136,.10), rgba(56,189,248,.07), rgba(139,92,246,.08));
    border: 1px solid rgba(56,189,248,.18);
    border-radius: 22px;
    padding: 22px 24px;
    margin: 12px 0 18px 0;
    box-shadow: 0 18px 48px rgba(0,0,0,.20);
}
.workflow-hero-card h2 { margin: 0; color: #f8fbff; font-size: 28px; font-weight: 850; }
.workflow-hero-card p { margin: 8px 0 0 0; color: #aebce0; font-size: 14px; }
.workflow-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 14px 0 16px 0; }
.workflow-step { background: rgba(16,19,34,.76); border: 1px solid rgba(0,255,136,.13); border-radius: 16px; padding: 15px; }
.workflow-step .num { width: 28px; height: 28px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #00cc6a, #0ea5e9); color: white; font-weight: 900; font-size: 13px; margin-bottom: 8px; }
.workflow-step h4 { margin: 0 0 4px 0; color: #f8fbff; font-size: 15px; }
.workflow-step p { margin: 0; color: #9fb0d6; font-size: 12.5px; }
.simple-status-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; margin: 10px 0 16px 0; }
.simple-status-card { background: rgba(16,19,34,.78); border: 1px solid rgba(56,189,248,.14); border-radius: 14px; padding: 13px 14px; }
.simple-status-card .label { color: #8da2cc; font-size: 11px; text-transform: uppercase; letter-spacing: .7px; }
.simple-status-card .value { color: #f8fbff; font-size: 15px; font-weight: 800; margin-top: 3px; }
.simple-status-card.ready { border-color: rgba(0,255,136,.22); }
.simple-status-card.warn { border-color: rgba(250,204,21,.28); }
.simple-status-card.off { border-color: rgba(248,113,113,.25); }
.simple-advanced-note { background: rgba(56,189,248,.06); border: 1px solid rgba(56,189,248,.14); color: #aab9db; padding: 11px 13px; border-radius: 14px; font-size: 13px; margin: 8px 0; }
@media (max-width: 900px) { .workflow-steps { grid-template-columns: 1fr; } .simple-status-grid { grid-template-columns: 1fr 1fr; } }

</style>
""",
    unsafe_allow_html=True,
)

st.markdown("""
<div class="es-visual-grid">
  <div class="es-tile"><h4>Secure Review</h4><p>Private server-side AI processing with protected credentials.</p></div>
  <div class="es-tile"><h4>Smart Routing</h4><p>Automatically detects QA, translation, source columns, and target areas.</p></div>
  <div class="es-tile"><h4>Client Rule Packs</h4><p>Optional ZIP rules for glossary, DNT, style guide, and instructions.</p></div>
</div>
""", unsafe_allow_html=True)


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
    "instruction",
    "lqa instruction",
    "calculation",
    "error_count",
    "error counts",
    "pull-out",
    "pull_out",
    "summary",
    "dashboard",
    "quality evaluation",
    "quality eval",
    "score card",
]

# Language-specific QA rules are now handled by qa_engine_global_v12.py.
# The Streamlit app shell keeps file extraction/output only.

PLACEHOLDER_PATTERN = re.compile(
    r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|\b\w+_id\b|<[^>]+>)"
)
NUMBER_PATTERN = re.compile(r"\d+(?:[.,:]\d+)*")
URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


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


def managed_ai_allowed() -> bool:
    """Managed API keys are disabled by default to protect owner cost.

    Set ALLOW_MANAGED_AI = "true" in Streamlit Secrets only if you want
    server-side keys to be used. Users can still enter their own keys in
    Control Center for the current browser session.
    """
    value = str(get_secret_value("ALLOW_MANAGED_AI", "false") or "false").strip().lower()
    return value in {"true", "1", "yes", "on"}


def get_user_openai_key() -> str:
    return str(st.session_state.get("es_user_openai_api_key", "") or "").strip()


def get_user_gemini_key() -> str:
    return str(st.session_state.get("es_user_gemini_api_key", "") or "").strip()


def get_openai_client() -> Optional[AI]:
    key = get_user_openai_key()
    if not key and managed_ai_allowed():
        key = get_secret_value("OPENAI_API_KEY") or ""
    if not key:
        return None
    return AI(api_key=key, timeout=60, max_retries=1)


def get_gemini_client():
    key = get_user_gemini_key()
    if not key and managed_ai_allowed():
        key = get_secret_value("GEMINI_API_KEY") or ""
    if not key or genai is None:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None


# ==========================================================
# LOCAL / SELF-HOSTED TRANSLATION ROUTER
# ==========================================================

INDIC_TARGET_NAMES = {
    "assamese", "as", "bengali", "bangla", "bn", "bodo", "brx", "dogri", "doi",
    "gujarati", "gu", "hindi", "hi", "kannada", "kn", "kashmiri", "ks",
    "konkani", "kok", "maithili", "mai", "malayalam", "ml", "manipuri", "mni",
    "marathi", "mr", "nepali", "ne", "odia", "oriya", "or", "punjabi", "pa",
    "sanskrit", "sa", "santali", "sat", "sindhi", "sd", "tamil", "ta",
    "telugu", "te", "urdu", "ur",
}

LIBRE_TARGET_NAMES = {
    "english", "en", "spanish", "es", "french", "fr", "german", "de", "italian", "it",
    "portuguese", "pt", "russian", "ru", "arabic", "ar", "chinese", "zh", "japanese", "ja",
    "korean", "ko", "hindi", "hi",
}

def _lang_key(language: str) -> str:
    value = normalize_text(language or "").strip().lower()
    value = value.replace("_", "-")
    if not value:
        return ""
    return re.split(r"[-,/() ]+", value)[0] if value else ""


def is_indic_target_language(language: str) -> bool:
    value = normalize_text(language or "").strip().lower()
    key = _lang_key(value)
    return key in INDIC_TARGET_NAMES or any(name in value for name in INDIC_TARGET_NAMES if len(name) > 2)


def is_libre_supported_target_name(language: str) -> bool:
    value = normalize_text(language or "").strip().lower()
    key = _lang_key(value)
    return key in LIBRE_TARGET_NAMES or any(name in value for name in LIBRE_TARGET_NAMES if len(name) > 2)


def get_local_translation_config() -> Dict[str, str]:
    """Backward-compatible single-engine configuration.

    Existing deployments can keep using:
        LOCAL_TRANSLATION_ENDPOINT
        LOCAL_TRANSLATION_PROVIDER

    New deployments can use routed engines:
        LIBRETRANSLATE_ENDPOINT = "http://localhost:5000"
        INDICTRANS2_ENDPOINT = "http://localhost:8000/translate"
    """
    endpoint = (
        get_secret_value("LOCAL_TRANSLATION_ENDPOINT")
        or get_secret_value("LIBRETRANSLATE_URL")
        or ""
    )
    provider = str(get_secret_value("LOCAL_TRANSLATION_PROVIDER", "libretranslate") or "libretranslate").strip().lower()
    if not endpoint and str(get_secret_value("ALLOW_PUBLIC_TRANSLATION_FALLBACK", "false") or "false").lower() == "true":
        endpoint = str(get_secret_value("PUBLIC_TRANSLATION_ENDPOINT", "https://libretranslate.com") or "https://libretranslate.com")
        provider = "libretranslate"
    return {
        "endpoint": str(endpoint).strip(),
        "provider": provider,
        "api_key": str(get_secret_value("LOCAL_TRANSLATION_API_KEY", "") or "").strip(),
        "source_language": str(get_secret_value("LOCAL_TRANSLATION_SOURCE_LANGUAGE", "auto") or "auto").strip(),
        "label": "Local translation engine",
        "route": "single",
    }


def get_translation_engine_config(target_language: str = "") -> Dict[str, str]:
    """Select the best self-hosted engine for the selected target language.

    Routing order:
    1. Indian/Indic languages → IndicTrans2 endpoint if configured.
    2. Other supported global languages → LibreTranslate endpoint if configured.
    3. Backward-compatible LOCAL_TRANSLATION_ENDPOINT.
    """
    target_language = normalize_text(target_language or "")

    indic_endpoint = (
        get_secret_value("INDICTRANS2_ENDPOINT")
        or get_secret_value("INDIC_TRANSLATION_ENDPOINT")
        or get_secret_value("LOCAL_INDIC_TRANSLATION_ENDPOINT")
        or ""
    )
    libre_endpoint = (
        get_secret_value("LIBRETRANSLATE_ENDPOINT")
        or get_secret_value("LIBRETRANSLATE_URL")
        or ""
    )

    # If user configured the old LOCAL_TRANSLATION_ENDPOINT as generic, treat it as IndicTrans2-capable.
    local_cfg = get_local_translation_config()
    local_endpoint = local_cfg.get("endpoint", "")
    local_provider = local_cfg.get("provider", "libretranslate")

    if is_indic_target_language(target_language):
        if indic_endpoint:
            return {
                "endpoint": str(indic_endpoint).strip(),
                "provider": "generic",
                "api_key": str(get_secret_value("INDICTRANS2_API_KEY", get_secret_value("LOCAL_TRANSLATION_API_KEY", "")) or "").strip(),
                "source_language": str(get_secret_value("INDICTRANS2_SOURCE_LANGUAGE", get_secret_value("LOCAL_TRANSLATION_SOURCE_LANGUAGE", "English")) or "English").strip(),
                "label": "IndicTrans2",
                "route": "indic",
            }
        if local_endpoint and local_provider == "generic":
            cfg = dict(local_cfg)
            cfg["label"] = "Indic/self-hosted engine"
            cfg["route"] = "indic-local"
            return cfg

    if libre_endpoint:
        return {
            "endpoint": str(libre_endpoint).strip(),
            "provider": "libretranslate",
            "api_key": str(get_secret_value("LIBRETRANSLATE_API_KEY", get_secret_value("LOCAL_TRANSLATION_API_KEY", "")) or "").strip(),
            "source_language": str(get_secret_value("LIBRETRANSLATE_SOURCE_LANGUAGE", get_secret_value("LOCAL_TRANSLATION_SOURCE_LANGUAGE", "auto")) or "auto").strip(),
            "label": "LibreTranslate",
            "route": "libre",
        }

    if local_endpoint:
        # Do not accidentally send French/Spanish/etc. to an IndicTrans2 generic endpoint.
        # Generic fallback for non-Indic targets is allowed only when explicitly enabled
        # for a global worker such as NLLB.
        allow_generic_all = str(get_secret_value("ALLOW_GENERIC_TRANSLATION_FOR_ALL", "false") or "false").lower() == "true"
        if local_provider == "generic" and not is_indic_target_language(target_language) and not allow_generic_all:
            return {"endpoint": "", "provider": "", "api_key": "", "source_language": "auto", "label": "No supported local engine", "route": "none"}
        cfg = dict(local_cfg)
        cfg["label"] = "Local translation engine"
        cfg["route"] = "single"
        return cfg

    return {"endpoint": "", "provider": "", "api_key": "", "source_language": "auto", "label": "No local engine", "route": "none"}


def has_local_translation_engine(target_language: str = "") -> bool:
    return bool(get_translation_engine_config(target_language).get("endpoint"))


@st.cache_data(ttl=120, show_spinner=False)
def local_engine_language_list(endpoint: str, provider: str) -> List[str]:
    """Return supported language names/codes for LibreTranslate-like engines."""
    if not endpoint or provider != "libretranslate":
        return []
    try:
        base = endpoint.rstrip("/")
        if base.endswith("/translate"):
            base = base[: -len("/translate")]
        url = base if base.endswith("/languages") else f"{base}/languages"
        res = requests.get(url, timeout=10)
        if res.status_code >= 400:
            return []
        data = res.json()
        langs = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if item.get("code"):
                        langs.append(str(item.get("code")).lower())
                    if item.get("name"):
                        langs.append(str(item.get("name")).lower())
        return sorted(set(langs))
    except Exception:
        return []


def translation_engine_status(target_language: str = "") -> Dict[str, Any]:
    cfg = get_translation_engine_config(target_language)
    endpoint = cfg.get("endpoint", "")
    provider = cfg.get("provider", "")
    target = normalize_text(target_language or "")
    status = "missing"
    reason = "No self-hosted translation endpoint is configured."
    supported = True

    if endpoint:
        status = "ready"
        reason = f"{cfg.get('label', 'Local engine')} is configured."
        if provider == "libretranslate":
            langs = local_engine_language_list(endpoint, provider)
            key = _lang_key(target)
            if langs and target and key not in langs and target.lower() not in langs:
                supported = False
                status = "unsupported"
                reason = f"LibreTranslate is configured, but '{target_language}' does not appear in its /languages list."
        elif provider == "generic" and target and not is_indic_target_language(target):
            # Generic can still be an NLLB/custom worker, so do not block. Warn only.
            reason = f"{cfg.get('label', 'Generic engine')} is configured. Verify it supports {target_language}."

    return {
        "status": status,
        "supported": supported,
        "reason": reason,
        "config": cfg,
    }


def can_use_local_translation_engine(target_language: str = "") -> bool:
    status = translation_engine_status(target_language)
    return bool(status.get("config", {}).get("endpoint")) and bool(status.get("supported", True))


def _endpoint_health_url(endpoint: str, provider: str) -> str:
    base = (endpoint or "").rstrip("/")
    if not base:
        return ""
    if provider == "libretranslate":
        if base.endswith("/translate"):
            base = base[: -len("/translate")]
        return f"{base}/languages"
    # generic workers such as IndicTrans2 expose /health beside /translate
    if base.endswith("/translate"):
        base = base[: -len("/translate")]
    return f"{base}/health"


def translation_engine_live_preflight(target_language: str) -> Tuple[bool, str]:
    """Confirm the selected local/self-hosted translation engine is reachable now.

    This prevents Pro from silently producing placeholder-only or blank output when
    a local engine is configured in code but not actually running.
    """
    status = translation_engine_status(target_language)
    cfg = status.get("config", {}) or {}
    endpoint = cfg.get("endpoint", "")
    provider = cfg.get("provider", "")
    label = cfg.get("label", "Local engine")

    if not endpoint:
        return False, f"No translation endpoint is configured for {target_language}."
    if not status.get("supported", True):
        return False, status.get("reason", f"Configured engine does not support {target_language}.")

    health_url = _endpoint_health_url(endpoint, provider)
    if not health_url:
        return False, "Could not build engine health URL."

    try:
        res = requests.get(health_url, timeout=12)
        if res.status_code >= 400:
            return False, f"{label} returned HTTP {res.status_code} at {health_url}."
        if provider == "libretranslate":
            data = res.json()
            langs = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        if item.get("code"):
                            langs.append(str(item.get("code")).lower())
                        if item.get("name"):
                            langs.append(str(item.get("name")).lower())
            key = _lang_key(target_language)
            if langs and key not in langs and target_language.strip().lower() not in langs:
                return False, f"LibreTranslate is reachable but does not list target '{target_language}'."
            return True, f"{label} is reachable and supports {target_language}."
        return True, f"{label} is reachable at {health_url}."
    except Exception as exc:
        return False, f"{label} is not reachable at {health_url}: {str(exc)[:220]}"


def missing_translation_segments(segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str]) -> List[Dict[str, Any]]:
    missing = []
    for seg in segments:
        source = normalize_text(seg.get("source") or seg.get("text") or "")
        loc = seg.get("location", "")
        trans = normalize_text(translations_by_loc.get(loc, ""))
        if source and not trans:
            missing.append(seg)
    return missing


# ==========================================================
# TARGET-LANGUAGE SAFETY GUARD
# ==========================================================

INDIC_SCRIPT_RE = re.compile(r"[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F]")
TELUGU_SCRIPT_RE = re.compile(r"[\u0C00-\u0C7F]")
TAMIL_SCRIPT_RE = re.compile(r"[\u0B80-\u0BFF]")
DEVANAGARI_SCRIPT_RE = re.compile(r"[\u0900-\u097F]")
BENGALI_SCRIPT_RE = re.compile(r"[\u0980-\u09FF]")
KANNADA_SCRIPT_RE = re.compile(r"[\u0C80-\u0CFF]")
MALAYALAM_SCRIPT_RE = re.compile(r"[\u0D00-\u0D7F]")
ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
HEBREW_SCRIPT_RE = re.compile(r"[\u0590-\u05FF]")
CJK_SCRIPT_RE = re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]")
CYRILLIC_SCRIPT_RE = re.compile(r"[\u0400-\u04FF]")
GREEK_SCRIPT_RE = re.compile(r"[\u0370-\u03FF]")

LATIN_TARGET_KEYS = {
    "english", "en", "french", "fr", "spanish", "es", "german", "de",
    "italian", "it", "portuguese", "pt", "dutch", "nl", "polish", "pl",
    "turkish", "tr", "vietnamese", "vi", "romanian", "ro", "swedish", "sv",
    "danish", "da", "norwegian", "no", "finnish", "fi", "czech", "cs",
}

def target_language_key(language: str) -> str:
    return _lang_key(normalize_text(language or "").lower())

def looks_like_wrong_script_for_target(text: str, target_language: str) -> bool:
    """Return True when a translation clearly belongs to another script/language.

    This prevents mistakes like reusing Telugu Translation Memory while the user
    selected French. It is intentionally conservative: it only rejects obvious
    script mismatches, not valid brand names or placeholders.
    """
    value = normalize_text(text or "")
    if not value:
        return True
    key = target_language_key(target_language)

    # Latin-language targets should not contain full Indic/Arabic/CJK scripts in normal translations.
    if key in LATIN_TARGET_KEYS:
        return bool(INDIC_SCRIPT_RE.search(value) or ARABIC_SCRIPT_RE.search(value) or HEBREW_SCRIPT_RE.search(value) or CJK_SCRIPT_RE.search(value))

    # Script-specific targets. If the text has a different major script and no expected script, reject it.
    expected = None
    if key in {"telugu", "te", "tel"}:
        expected = TELUGU_SCRIPT_RE
    elif key in {"tamil", "ta"}:
        expected = TAMIL_SCRIPT_RE
    elif key in {"hindi", "hi", "marathi", "mr", "nepali", "ne", "sanskrit", "sa"}:
        expected = DEVANAGARI_SCRIPT_RE
    elif key in {"bengali", "bangla", "bn", "assamese", "as"}:
        expected = BENGALI_SCRIPT_RE
    elif key in {"kannada", "kn"}:
        expected = KANNADA_SCRIPT_RE
    elif key in {"malayalam", "ml"}:
        expected = MALAYALAM_SCRIPT_RE
    elif key in {"arabic", "ar", "urdu", "ur", "persian", "fa", "farsi"}:
        expected = ARABIC_SCRIPT_RE
    elif key in {"hebrew", "he"}:
        expected = HEBREW_SCRIPT_RE
    elif key in {"russian", "ru", "ukrainian", "uk", "bulgarian", "bg"}:
        expected = CYRILLIC_SCRIPT_RE
    elif key in {"greek", "el"}:
        expected = GREEK_SCRIPT_RE

    if expected is not None:
        if expected.search(value):
            return False
        # Bracket-only labels, numbers, placeholders and very short DNT-like tokens may be allowed, but
        # large Latin sentences in an Indic/RTL target are wrong-script leftovers.
        stripped = re.sub(PLACEHOLDER_PATTERN, "", value)
        stripped = re.sub(r"https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+", "", stripped)
        latin_words = re.findall(r"[A-Za-z]{3,}", stripped)
        return len(latin_words) >= 2

    return False

def filter_tm_matches_for_target_language(tm_matches: Dict[str, Dict[str, Any]], target_language: str) -> Tuple[Dict[str, Dict[str, Any]], int]:
    filtered: Dict[str, Dict[str, Any]] = {}
    dropped = 0
    for loc, match in (tm_matches or {}).items():
        trans = match.get("translation", "")
        if looks_like_wrong_script_for_target(trans, target_language):
            dropped += 1
            continue
        filtered[loc] = match
    return filtered, dropped


def render_translation_route_status(target_language: str, openai_client=None, gemini_client=None) -> None:
    """Show a clear route before users run Pro."""
    status = translation_engine_status(target_language)
    cfg = status["config"]

    if openai_client:
        translation_value = "Managed/User API"
        cls = "ready"
        detail = "Primary translation route uses the configured language API."
    elif status["status"] == "ready":
        translation_value = cfg.get("label", "Self-hosted engine")
        cls = "ready"
        detail = status["reason"]
    elif status["status"] == "unsupported":
        translation_value = "Unsupported target"
        cls = "warn"
        detail = status["reason"]
    else:
        translation_value = "Memory / glossary only"
        cls = "warn"
        detail = status["reason"]

    review_value = "Available" if gemini_client else "Rules only"
    html = f"""
    <div class="simple-status-grid">
      <div class="simple-status-card {cls}"><div class="label">Translation route</div><div class="value">{escape(translation_value)}</div></div>
      <div class="simple-status-card ready"><div class="label">Target language</div><div class="value">{escape(target_language or 'Not set')}</div></div>
      <div class="simple-status-card {'ready' if gemini_client else 'warn'}"><div class="label">Review</div><div class="value">{escape(review_value)}</div></div>
      <div class="simple-status-card ready"><div class="label">Memory</div><div class="value">Reuse first</div></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    if detail:
        if cls == "ready":
            st.success(detail)
        else:
            st.warning(detail)


def local_translate_batch_adapter(segments: List[Dict[str, Any]], target_language: str, domain: str) -> List[Dict[str, str]]:
    """Call the routed self-hosted translation engine with protected-token guard."""
    cfg = get_translation_engine_config(target_language)
    protected_segments = protect_segments_for_translation(segments)
    original_by_loc = {str(s.get("location", "")): s for s in segments}
    try:
        from local_translation_engine import self_hosted_translate_batch
        raw = self_hosted_translate_batch(
            segments=protected_segments,
            endpoint=cfg["endpoint"],
            provider=cfg["provider"],
            target_language=target_language,
            source_language=cfg["source_language"],
            domain=domain,
            api_key=cfg["api_key"],
            timeout=180,
        )
        fixed: List[Dict[str, str]] = []
        for item in raw:
            loc = str(item.get("location", ""))
            original_seg = original_by_loc.get(loc, {"source": ""})
            fixed.append({
                "location": loc,
                "translation": restore_translation_item(original_seg, item.get("translation", "")),
            })
        return fixed
    except Exception as exc:
        return [
            {
                "location": s.get("location", ""),
                "translation": "",
                "error": f"Local translation engine failed: {str(exc)[:180]}",
            }
            for s in segments
        ]


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


# ==========================================================
# GLOBAL TRANSLATION SAFETY / PLACEHOLDER GUARD
# ==========================================================

# Protected content must never be translated by any engine.
# This is global, not Telugu-specific. It protects variables, placeholders,
# tags, bullets, URLs, emails, and common units.
# Square-bracketed UI labels like [Log In] are localizable; the brackets should remain,
# but the text inside can be translated unless a client rule/DNT says otherwise.
PROTECTED_INLINE_RE = re.compile(
    r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$[A-Za-z_][\w]*|<[^>]+>|https?://[^\s]+|www\.[^\s]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})"
)
LOCALIZABLE_BRACKET_RE = re.compile(r"\[[^\[\]\n]{1,120}\]")
LEADING_BULLET_RE = re.compile(r"^(\s*[•∙◦▪▫●○\-–—*]\s*)")
COMMON_UNIT_RE = re.compile(r"\b(kcal|mins?|sec(?:onds?)?|hrs?|kg|g|mg|km|m|cm|mm|mb|gb|tb|kb|fps|dpi|px|%|°c|°f)\b", re.I)
PROTECT_MARKER_PREFIX = "ZXPH"
PROTECT_MARKER_SUFFIX = "ZX"


def _find_protected_spans(source: str) -> List[Tuple[int, int, str]]:
    """Return non-overlapping protected spans in source text."""
    source = normalize_text(source or "")
    candidates: List[Tuple[int, int, str]] = []
    for pattern in [PROTECTED_INLINE_RE, COMMON_UNIT_RE]:
        for m in pattern.finditer(source):
            token = m.group(0)
            if token:
                candidates.append((m.start(), m.end(), token))
    bullet = LEADING_BULLET_RE.match(source)
    if bullet:
        candidates.append((bullet.start(1), bullet.end(1), bullet.group(1)))

    # Prefer longer spans and remove overlaps.
    candidates.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    accepted: List[Tuple[int, int, str]] = []
    occupied: List[Tuple[int, int]] = []
    for start, end, token in candidates:
        if any(not (end <= os or start >= oe) for os, oe in occupied):
            continue
        accepted.append((start, end, token))
        occupied.append((start, end))
    accepted.sort(key=lambda x: x[0])
    return accepted


def protect_text_for_translation(source: str) -> Tuple[str, List[str]]:
    """Replace protected tokens with stable ASCII markers before translation."""
    source = normalize_text(source or "")
    spans = _find_protected_spans(source)
    if not spans:
        return source, []

    out = []
    last = 0
    protected: List[str] = []
    for idx, (start, end, token) in enumerate(spans):
        out.append(source[last:start])
        marker = f"{PROTECT_MARKER_PREFIX}{idx}{PROTECT_MARKER_SUFFIX}"
        out.append(marker)
        protected.append(token)
        last = end
    out.append(source[last:])
    return "".join(out), protected


def _marker_regex(index: int) -> re.Pattern:
    # Handles exact marker plus model-distorted variants such as:
    # ZXPH0ZX, ZX PH 0 ZX, _ _ ESPH0 _ _, ESPH0, Z X P H 0 Z X.
    return re.compile(
        rf"(?i)(?:{PROTECT_MARKER_PREFIX}\s*{index}\s*{PROTECT_MARKER_SUFFIX}|"
        rf"Z\s*X\s*P\s*H\s*{index}\s*Z\s*X|"
        rf"E\s*S\s*P\s*H\s*{index}|"
        rf"[_\s]*E\s*S\s*P\s*H\s*{index}[_\s]*|"
        rf"[_\s]*{PROTECT_MARKER_PREFIX}\s*{index}\s*{PROTECT_MARKER_SUFFIX}[_\s]*)"
    )


def restore_protected_text(source: str, translation: Any) -> str:
    """Restore protected source tokens after translation.

    This fixes cases where IndicTrans/other local engines change {{email}} into
    markers like "_ _ ESPH0 _ _". Square-bracketed UI labels are allowed to localize.
    """
    source = normalize_text(source or "")
    translated = normalize_text(translation or "")
    _, protected = protect_text_for_translation(source)
    if not protected:
        # Still fix common bullet encoding issue: ∙ sometimes becomes Â.
        bullet = LEADING_BULLET_RE.match(source)
        if bullet and translated.startswith("Â"):
            return bullet.group(1).strip() + translated[1:]
        return translated

    # Replace all marker/distorted marker forms with exact original protected token.
    for idx, token in enumerate(protected):
        translated = _marker_regex(idx).sub(token, translated)

    # Square-bracketed UI labels are localizable.
    # Example: [Welcome Screen] -> [வரவேற்பு திரை] is valid.
    # We do not restore the source English text inside brackets.
    # If the whole source segment was bracketed and the engine dropped brackets,
    # wrap the localized result back in brackets to preserve UI-label structure.
    source_brackets = LOCALIZABLE_BRACKET_RE.findall(source)
    if source_brackets:
        source_clean = source.strip()
        translated_clean = translated.strip()
        if source_clean in source_brackets and len(source_brackets) == 1:
            if not (translated_clean.startswith("[") and translated_clean.endswith("]")) and translated_clean:
                translated = f"[{translated_clean.strip('[] ')}]"

    # Ensure every placeholder/variable/tag/unit from the source is still present.
    # For placeholders, missing is worse than imperfect position, so append if lost.
    must_keep = []
    must_keep.extend(PROTECTED_INLINE_RE.findall(source))
    # Keep common units only when source has them.
    must_keep.extend([m.group(0) for m in COMMON_UNIT_RE.finditer(source)])
    for token in must_keep:
        if token and token not in translated:
            # Replace any remaining marker-ish token first; otherwise append.
            markerish = re.search(r"(?i)[_\s]*(?:E\s*S\s*P\s*H\s*\d+|Z\s*X\s*P\s*H\s*\d+\s*Z\s*X)[_\s]*", translated)
            if markerish:
                translated = translated[:markerish.start()] + token + translated[markerish.end():]
            else:
                translated = (translated + " " + token).strip()

    # Restore leading bullet/list marker exactly.
    bullet = LEADING_BULLET_RE.match(source)
    if bullet:
        src_bullet = bullet.group(1)
        # Remove common mojibake from bullets.
        translated = re.sub(r"^\s*Â\s*", "", translated)
        if not translated.startswith(src_bullet.strip()):
            translated = src_bullet + translated.lstrip()

    return translated


def protect_segments_for_translation(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    protected_segments: List[Dict[str, Any]] = []
    for seg in segments:
        source = normalize_text(seg.get("source") or seg.get("text") or "")
        protected_source, protected_tokens = protect_text_for_translation(source)
        new_seg = dict(seg)
        new_seg["source"] = protected_source
        new_seg["text"] = protected_source
        new_seg["_original_source"] = source
        new_seg["_protected_tokens"] = protected_tokens
        protected_segments.append(new_seg)
    return protected_segments


def restore_translation_item(original_segment: Dict[str, Any], translation: Any) -> str:
    source = normalize_text(original_segment.get("source") or original_segment.get("text") or "")
    return restore_protected_text(source, translation)


def decode_text_bytes(data: bytes) -> Tuple[str, str]:
    """Decode uploaded text files without destroying Windows/CP1252 punctuation.

    Many client text files contain CP1252 bytes such as NBSP (0xA0), smart quotes,
    and en dash. Decoding those with UTF-8 + errors=ignore removes/changes
    characters and can collapse the visual pattern.
    """
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"




def looks_like_binary(data: bytes) -> bool:
    """Return True when a file is probably binary and should not be decoded as text.

    This prevents unknown/binary uploads (or unsupported spreadsheet formats)
    from being decoded as latin-1 and producing tens of thousands of fake text segments.
    """
    if not data:
        return False
    sample = data[:8192]
    if b"\x00" in sample:
        return True
    text_chars = bytes(range(32, 127)) + b"\n\r\t\b\f"
    non_text = sum(1 for b in sample if b not in text_chars and b < 128)
    return (non_text / max(len(sample), 1)) > 0.30


def is_openpyxl_compatible(data: bytes) -> bool:
    """Detect xlsx-like ZIP workbooks even if the extension is unusual."""
    if not data.startswith(b"PK"):
        return False
    try:
        import zipfile as _zipfile
        with _zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            return "xl/workbook.xml" in names or any(n.startswith("xl/worksheets/") for n in names)
    except Exception:
        return False


def uploaded_file_bytes(uploaded_file) -> bytes:
    try:
        return uploaded_file.getvalue()
    except Exception:
        try:
            pos = uploaded_file.tell()
        except Exception:
            pos = None
        data = uploaded_file.read()
        if pos is not None:
            try:
                uploaded_file.seek(pos)
            except Exception:
                pass
        return data


def max_processable_segments_for_credits(profile: Optional[Dict[str, Any]], workflow: str, rules_zip_used: bool = False, independent_review: bool = False) -> int:
    """How many segments the user's remaining ErrorSweep app credits can cover."""
    rem = remaining_credits(profile)
    overhead = 1 if rules_zip_used else 0
    rem_after_overhead = rem - overhead
    if rem_after_overhead <= 0:
        return 0
    if workflow == "qa":
        return rem_after_overhead * 100

    best = 0
    for n in range(1, 200000, 75):
        cost = calculate_credit_cost("pro", n, rules_zip_used=rules_zip_used, independent_review=independent_review)
        if cost <= rem:
            best = n
        else:
            break
    return best


def maybe_limit_segments_to_available_credits(
    segments: List[Dict[str, Any]],
    profile: Optional[Dict[str, Any]],
    workflow: str,
    rules_zip_used: bool = False,
    independent_review: bool = False,
) -> Tuple[List[Dict[str, Any]], int, str]:
    """Require app credits, but process a partial file if current credits cannot cover the full file."""
    full_count = len(segments)
    full_cost = calculate_credit_cost(workflow, full_count, rules_zip_used=rules_zip_used, independent_review=independent_review)
    ok, msg = credit_preflight(profile, full_cost)
    if ok:
        return segments, full_cost, f"Full file covered: {full_count} segment(s), {full_cost} app credit(s)."

    allowed = max_processable_segments_for_credits(profile, workflow, rules_zip_used=rules_zip_used, independent_review=independent_review)
    if allowed <= 0:
        return [], full_cost, msg

    limited = segments[:allowed]
    limited_cost = calculate_credit_cost(workflow, len(limited), rules_zip_used=rules_zip_used, independent_review=independent_review)
    return limited, limited_cost, (
        f"Not enough credits for full file ({full_count} segments require {full_cost} credits). "
        f"Processing first {len(limited)} segment(s) using available credits ({limited_cost} credit(s)). "
        "Upgrade/add credits for full-file processing."
    )

def is_visually_blank_line(line: str) -> bool:
    return line.replace("\u00A0", " ").strip() == ""


def clean_line_for_ai(line: str) -> str:
    """Clean a line for AI while preserving actual source meaning and spacing."""
    line = line.rstrip("\r\n")
    line = line.replace("\u00A0", " ")
    # collapse only excessive internal whitespace created by NBSP-heavy text files
    line = re.sub(r"[ \t]+", " ", line)
    return normalize_text(line).strip()


def should_skip_text_translation_line(clean_line: str, non_empty_position: int) -> bool:
    """Skip column headers in simple Source/Target text templates."""
    low = clean_line.lower().strip()
    if non_empty_position <= 2 and low in {"source", "target"}:
        return True
    return False


def build_preserved_text_translation(text_original: str, segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str]) -> bytes:
    """Build a translated TXT/SRT-like output while keeping the original line pattern.

    For each translated source line, the original line remains in place and the
    translation is written into the following blank line when available. If the
    next line is not blank, the translation is inserted immediately below.
    This prevents the old CSV-table output from changing the user's template.
    """
    lines = text_original.splitlines(keepends=True)
    if not lines and text_original:
        lines = [text_original]

    by_line_index: Dict[int, str] = {}
    for seg in segments:
        idx = seg.get("line_index")
        loc = seg.get("location", "")
        trans = translations_by_loc.get(loc, "")
        if idx is not None and trans:
            by_line_index[int(idx)] = trans.strip()

    output_lines: List[str] = []
    replaced_blank_indices = set()

    for i, line in enumerate(lines):
        if i in replaced_blank_indices:
            continue

        output_lines.append(line)

        if i not in by_line_index:
            continue

        translation = by_line_index[i]
        line_ending_match = re.search(r"(\r\n|\n|\r)$", line)
        line_ending = line_ending_match.group(1) if line_ending_match else "\n"

        next_index = i + 1
        if next_index < len(lines) and is_visually_blank_line(lines[next_index]):
            next_ending_match = re.search(r"(\r\n|\n|\r)$", lines[next_index])
            next_ending = next_ending_match.group(1) if next_ending_match else line_ending
            output_lines.append(translation + next_ending)
            replaced_blank_indices.add(next_index)
        else:
            output_lines.append(translation + line_ending)

    return "".join(output_lines).encode("utf-8-sig")


def visible_invisibles(text: Any) -> str:
    """Return report-safe text while keeping ZWNJ invisible.

    Earlier versions displayed U+200C as ⟨ZWNJ⟩ in report sheets.
    That was useful for debugging, but it looks noisy for clients.
    This keeps the actual ZWNJ character in suggestions/output while hiding
    the debug label from reports and UI.
    """
    text = str(text) if text is not None else ""
    return (
        text
        .replace("\u200B", "")
        .replace("\u200D", "")
        .replace("\u00A0", " ")
    )


def unlimited_scan(max_segments: int) -> bool:
    """max_segments <= 0 means scan the whole file."""
    try:
        return int(max_segments) <= 0
    except Exception:
        return True


def reached_segment_limit(segments: List[Dict[str, Any]], max_segments: int) -> bool:
    return (not unlimited_scan(max_segments)) and len(segments) >= int(max_segments)


def limit_sequence(items, max_segments: int):
    if unlimited_scan(max_segments):
        return list(items)
    return list(items)[:int(max_segments)]


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
    """
    Detect real content columns, not metadata rows.
    Excel review forms often have rows like Source language* / Target language* before the actual table.
    Those rows must not be treated as Source/Translation headers.
    """
    headers_clean = [normalize_text(h).lower() for h in headers]

    metadata_terms = [
        "source language", "target language", "client", "project id", "date",
        "number of checked words", "checked words", "review date"
    ]

    strong_source_terms = [
        "source text", "source segment", "source string", "source copy", "source"
    ]
    strong_target_terms = [
        "original translation", "translation", "target text", "target segment",
        "translated text", "translated string", "localized", "target"
    ]

    def bad_metadata_header(h: str) -> bool:
        return any(term in h for term in metadata_terms)

    def find_by_hint(hint: str) -> Optional[int]:
        if not hint:
            return None
        hint = hint.lower().strip()
        try:
            idx = int(hint)
            if 1 <= idx <= len(headers):
                return idx - 1
            if 0 <= idx < len(headers):
                return idx
        except ValueError:
            pass
        for i, h in enumerate(headers_clean):
            if h == hint and not bad_metadata_header(h):
                return i
        for i, h in enumerate(headers_clean):
            if hint in h and not bad_metadata_header(h):
                return i
        return None

    src_idx = find_by_hint(source_hint)
    tgt_idx = find_by_hint(target_hint)

    if src_idx is None:
        for term in strong_source_terms:
            for i, h in enumerate(headers_clean):
                if bad_metadata_header(h):
                    continue
                if term == h or term in h:
                    src_idx = i
                    break
            if src_idx is not None:
                break

    if tgt_idx is None:
        for term in strong_target_terms:
            for i, h in enumerate(headers_clean):
                if bad_metadata_header(h):
                    continue
                if term == h or term in h:
                    tgt_idx = i
                    break
            if tgt_idx is not None:
                break

    return src_idx, tgt_idx


def score_header_row(headers: List[str], src_idx: Optional[int], tgt_idx: Optional[int], need_target: bool) -> int:
    joined = " | ".join([normalize_text(h).lower() for h in headers])
    score = 0

    if "source text" in joined:
        score += 100
    if "original translation" in joined:
        score += 120
    if "suggested translation" in joined:
        score += 40
    if "error category" in joined or "error severity" in joined:
        score += 25
    if "item no" in joined or "item no." in joined:
        score += 20

    bad_rows = [
        "source language", "target language", "client", "project id", "date",
        "number of checked words", "quality evaluation score card"
    ]
    if any(term in joined for term in bad_rows):
        score -= 200

    if src_idx is not None:
        score += 20
    if tgt_idx is not None:
        score += 20
    elif need_target:
        score -= 100

    return score


def find_excel_header_row(rows: List[Any], source_hint: str, target_hint: str, need_target: bool = True) -> Tuple[int, List[str], Optional[int], Optional[int]]:
    """
    Find the real content table header. This prevents metadata rows like Source language* / Target language*
    from being mistaken as the actual QA columns.
    """
    max_scan = min(len(rows), 50)
    best = (None, -9999, [], None, None)

    for row_index in range(max_scan):
        headers = [str(cell.value).strip() if cell.value is not None else "" for cell in rows[row_index]]
        if not any(headers):
            continue
        src, tgt = detect_source_target_columns(headers, source_hint, target_hint)
        score = score_header_row(headers, src, tgt, need_target)
        if score > best[1]:
            best = (row_index, score, headers, src, tgt)

    row_index, score, headers, src, tgt = best

    if row_index is not None and src is not None and ((tgt is not None) or not need_target) and score >= 60:
        return row_index, headers, src, tgt

    if source_hint or target_hint:
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


# ==========================================================
# AUTO TASK + LAYOUT DETECTION
# ==========================================================

def infer_task_from_request(request_text: str) -> Optional[str]:
    """Return "qa", "pro" (translation workflow), or None."""
    t = (request_text or "").lower()
    if not t.strip():
        return None
    translate_terms = [
        "translate", "translation", "localize", "localise", "localization",
        "target language", "generate target", "fill target", "prepare translation",
        "tl", "t9n"
    ]
    qa_terms = [
        "qa", "review", "proofread", "proof read", "check", "lqa",
        "linguistic review", "error report", "evaluate", "validation", "verify",
        "quality check"
    ]
    translate_score = sum(1 for k in translate_terms if k in t)
    qa_score = sum(1 for k in qa_terms if k in t)
    if translate_score > qa_score:
        return "pro"
    if qa_score > translate_score:
        return "qa"
    return None


def _bytes_io(uploaded_file):
    return io.BytesIO(uploaded_file.getvalue())


def _nonempty_ratio(values: List[str]) -> float:
    if not values:
        return 0.0
    non_empty = sum(1 for v in values if normalize_text(v))
    return non_empty / max(len(values), 1)


def infer_task_from_file(uploaded_file, source_hint: str = "", target_hint: str = "") -> Tuple[str, str]:
    """
    Heuristic file-level task detector.
    Returns (task, reason), where task is "qa" or "pro".
    """
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".xlsx"):
            wb = load_workbook(_bytes_io(uploaded_file), data_only=False)
            for ws in wb.worksheets:
                if should_skip_sheet(ws.title, True):
                    continue
                rows = list(ws.iter_rows(values_only=False))
                if not rows:
                    continue
                header_idx, headers, src_idx, tgt_idx = find_excel_header_row(rows, source_hint, target_hint, need_target=False)
                if src_idx is not None:
                    if tgt_idx is None:
                        return "pro", f"Detected source column in Excel sheet '{ws.title}' but no target column."
                    target_values = []
                    for row in rows[header_idx + 1: header_idx + 101]:
                        if len(row) <= max(src_idx, tgt_idx):
                            continue
                        target_values.append(normalize_text(row[tgt_idx].value or ""))
                    if _nonempty_ratio(target_values) >= 0.20:
                        return "qa", f"Detected populated source + target columns in Excel sheet '{ws.title}'."
                    return "pro", f"Detected source column with mostly empty target column in Excel sheet '{ws.title}'."
            return "pro", "No reliable target translations found in Excel."

        if name.endswith(".csv"):
            df = pd.read_csv(_bytes_io(uploaded_file))
            src_idx, tgt_idx = detect_source_target_columns(list(df.columns), source_hint, target_hint)
            if src_idx is not None:
                if tgt_idx is None:
                    return "pro", "Detected source column in CSV but no target column."
                tgt_col = df.columns[tgt_idx]
                sample = [normalize_text(x) for x in df[tgt_col].head(100).fillna("").tolist()]
                if _nonempty_ratio(sample) >= 0.20:
                    return "qa", "Detected populated source + target columns in CSV."
                return "pro", "Detected source column with mostly empty target column in CSV."
            return "pro", "No source/target CSV columns detected."

        if name.endswith(".docx"):
            doc = Document(_bytes_io(uploaded_file))
            for table_idx, table in enumerate(doc.tables, start=1):
                header_idx, headers, src_idx, tgt_idx = find_docx_table_header(table, source_hint, target_hint, need_target=False)
                if src_idx is not None:
                    if tgt_idx is None:
                        return "pro", f"Detected source column in DOCX table {table_idx} but no target column."
                    vals = []
                    for row in table.rows[header_idx + 1: header_idx + 101]:
                        if len(row.cells) <= max(src_idx, tgt_idx):
                            continue
                        vals.append(get_docx_cell_text(row.cells[tgt_idx]))
                    if _nonempty_ratio(vals) >= 0.20:
                        return "qa", f"Detected populated source + target columns in DOCX table {table_idx}."
                    return "pro", f"Detected source column with mostly blank target column in DOCX table {table_idx}."
            paras = [normalize_text(p.text) for p in doc.paragraphs if normalize_text(p.text)]
            if len(paras) >= 2 and paras[0].lower() in {"source", "source text"} and paras[1].lower() in {"target", "translation", "original translation"}:
                return "pro", "Detected Source/Target text template in DOCX."
            return "pro", "DOCX appears source-only."

        raw = uploaded_file.getvalue()
        txt, _ = decode_text_bytes(raw)
        clean_lines = [clean_line_for_ai(x) for x in txt.splitlines()]
        nonempty = [x for x in clean_lines if x]
        if len(nonempty) >= 2 and nonempty[0].lower() in {"source", "source text"} and nonempty[1].lower() in {"target", "translation", "original translation"}:
            return "pro", "Detected Source/Target line-template."
        tab_pairs = 0
        for line in nonempty[:100]:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                tab_pairs += 1
        if tab_pairs >= 3:
            return "qa", "Detected tab-separated source/target pairs."
        return "pro", "Text file appears source-only."
    except Exception as e:
        return "pro", f"Auto-detection fallback selected translation because layout detection failed: {e}"


# ==========================================================
# DOCX TABLE HELPERS
# ==========================================================

def get_docx_cell_text(cell) -> str:
    return "\n".join(p.text for p in cell.paragraphs).strip()


def set_docx_cell_text(cell, text: str) -> None:
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.text = ""
    if cell.paragraphs:
        cell.paragraphs[0].add_run(text)
    else:
        cell.add_paragraph(text)


def set_docx_paragraph_text(paragraph, text: str) -> None:
    for run in paragraph.runs:
        run.text = ""
    paragraph.add_run(text)


def find_docx_table_header(table, source_hint: str, target_hint: str, need_target: bool = True):
    max_scan = min(len(table.rows), 30)
    best = (None, -9999, [], None, None)
    for row_idx in range(max_scan):
        headers = [get_docx_cell_text(cell) for cell in table.rows[row_idx].cells]
        if not any(headers):
            continue
        src, tgt = detect_source_target_columns(headers, source_hint, target_hint)
        score = score_header_row(headers, src, tgt, need_target)
        joined = " ".join(str(h).lower() for h in headers)
        if "source text" in joined:
            score += 120
        if "original translation" in joined or "translation" in joined:
            score += 80
        if score > best[1]:
            best = (row_idx, score, headers, src, tgt)
    row_idx, score, headers, src, tgt = best
    if row_idx is not None and src is not None and ((tgt is not None) or not need_target) and score >= 40:
        return row_idx, headers, src, tgt
    return 0, [], None, None


def is_valid_docx_source(text: str) -> bool:
    t = normalize_text(text)
    if len(t) < 2:
        return False
    if t.lower() in {"source", "target", "source text", "original translation", "translation", "target text"}:
        return False
    return True


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
            tgt_name = headers[tgt_idx] if tgt_idx is not None and tgt_idx < len(headers) else "AI Translation"
            logs.append(f"{ws.title}: column mode [{src_name}] -> [{tgt_name}]")

            # For Pro, create output translation column if target column is missing.
            output_col_idx = tgt_idx
            if mode == "pro" and output_col_idx is None:
                output_col_idx = ws.max_column
                ws.cell(row=header_idx + 1, column=output_col_idx + 1).value = "AI Translation"
                logs.append(f"{ws.title}: created output column [AI Translation]")

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
                if reached_segment_limit(segments, max_segments):
                    return wb, segments, cell_map, translation_col_map, logs

        elif deep_scan:
            logs.append(f"{ws.title}: no source/target columns found; deep-scan text cells")
            for row in rows:
                for cell in row:
                    if getattr(cell, "data_type", None) == "f":
                        continue
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
                        if reached_segment_limit(segments, max_segments):
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
        tgt_col = df.columns[tgt_idx] if tgt_idx is not None else "AI Translation"
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
            if reached_segment_limit(segments, max_segments):
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
                    if reached_segment_limit(segments, max_segments):
                        return df, segments, logs
    else:
        logs.append("CSV: no usable columns found")

    return df, segments, logs


def extract_text_segments(uploaded_file, mode: str, max_segments: int):
    data = uploaded_file.getvalue()
    lower_name = uploaded_file.name.lower()

    # .xlz is often a compressed XLIFF package, not a plain text file.
    if lower_name.endswith(".xlz"):
        return extract_xlz_segments_from_zip(data, mode, max_segments)

    text_like_exts = (
        ".txt", ".srt", ".xml", ".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".json", ".po",
        ".properties", ".strings", ".html", ".htm", ".md", ".yml", ".yaml", ".csv"
    )
    if looks_like_binary(data) and not lower_name.endswith(text_like_exts):
        return "", [], [
            "Unsupported or binary file detected. ErrorSweep could not safely extract readable text. "
            "If this is an Excel workbook with a non-standard extension, rename it to .xlsx and retry."
        ]

    text, encoding_used = decode_text_bytes(data)

    # Basic XLIFF/XML/XLZ pair extraction. These formats should not be converted into
    # line-pair text output; they are treated as structured source/target pairs.
    if lower_name.endswith((".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".xml")):
        segments, xliff_logs = extract_xliff_pairs_from_xml_text(
            text,
            mode=mode,
            max_segments=max_segments,
            source_label=uploaded_file.name,
        )
        if segments:
            return text, segments, [f"{msg} (decoded as {encoding_used})" for msg in xliff_logs]

    raw_lines = text.splitlines(keepends=True)
    clean_lines = [clean_line_for_ai(line) for line in raw_lines]

    # Detect tab-separated bilingual pairs first.
    segments = []
    for line_index, clean in enumerate(clean_lines):
        if not clean or len(clean) <= 2:
            continue
        parts = clean.split("\t")
        if len(parts) >= 2 and len(parts[0].strip()) > 1 and len(parts[1].strip()) > 1:
            segments.append({
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {line_index + 1}",
                "line_index": line_index,
                "source": parts[0].strip(),
                "translation": parts[1].strip(),
                "text": parts[1].strip() if mode == "qa" else parts[0].strip(),
                "mode": "bilingual",
            })
            if reached_segment_limit(segments, max_segments):
                break

    non_empty_count = sum(1 for x in clean_lines if x.strip())
    if segments and len(segments) >= max(1, min(5, non_empty_count)):
        return text, segments, [f"Text: detected tab-separated source/translation pairs (decoded as {encoding_used})"]

    # Line-based text template mode. This preserves the user's line pattern.
    # Example:
    #   Source
    #   Target
    #   English source line
    #   [blank target line]
    # becomes:
    #   Source
    #   Target
    #   English source line
    #   Telugu translation
    segments = []
    non_empty_position = 0
    for line_index, clean in enumerate(clean_lines):
        if not clean:
            continue
        non_empty_position += 1
        if len(clean) <= 2:
            continue
        if should_skip_text_translation_line(clean, non_empty_position):
            continue

        if mode == "pro":
            seg = {
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {line_index + 1}",
                "line_index": line_index,
                "source": clean,
                "translation": "",
                "text": clean,
                "mode": "source_only",
            }
        else:
            seg = {
                "id": len(segments) + 1,
                "file_type": "text",
                "sheet": "File",
                "location": f"Line {line_index + 1}",
                "line_index": line_index,
                "source": "",
                "translation": clean,
                "text": clean,
                "mode": "monolingual",
            }
        segments.append(seg)
        if reached_segment_limit(segments, max_segments):
            break

    return text, segments, [f"Text: pattern-preserving line mode (decoded as {encoding_used})"]


def extract_docx_segments(uploaded_file, mode: str, max_segments: int, source_hint: str = "", target_hint: str = ""):
    """Auto DOCX extractor: tables first, Source/Target template second, paragraph fallback third."""
    doc = Document(uploaded_file)
    segments: List[Dict[str, Any]] = []
    para_map: Dict[str, Dict[str, Any]] = {}
    logs: List[str] = []

    for table_idx, table in enumerate(doc.tables, start=1):
        header_idx, headers, src_idx, tgt_idx = find_docx_table_header(table, source_hint, target_hint, need_target=(mode == "qa"))
        if src_idx is None or (mode == "qa" and tgt_idx is None):
            continue
        src_name = headers[src_idx] if src_idx < len(headers) else "Source Text"
        tgt_name = headers[tgt_idx] if tgt_idx is not None and tgt_idx < len(headers) else "Original Translation"
        logs.append(f"DOCX table {table_idx}: column mode [{src_name}] -> [{tgt_name}]")

        for row_idx in range(header_idx + 1, len(table.rows)):
            row = table.rows[row_idx]
            if len(row.cells) <= src_idx:
                continue
            source_text = normalize_text(get_docx_cell_text(row.cells[src_idx]))
            if not is_valid_docx_source(source_text):
                continue
            translation_text = ""
            target_cell = None
            if tgt_idx is not None and len(row.cells) > tgt_idx:
                target_cell = row.cells[tgt_idx]
                translation_text = normalize_text(get_docx_cell_text(target_cell))
            if mode == "qa" and not translation_text:
                continue
            loc = f"Table {table_idx}, Row {row_idx + 1}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "docx",
                "sheet": f"Table {table_idx}",
                "location": loc,
                "row": row_idx + 1,
                "source": source_text,
                "translation": translation_text,
                "text": translation_text if mode == "qa" else source_text,
                "mode": "bilingual" if translation_text else "source_only",
                "source_header": src_name,
                "target_header": tgt_name,
            })
            if target_cell is not None:
                para_map[loc] = {"kind": "cell", "cell": target_cell}
            if reached_segment_limit(segments, max_segments):
                return doc, segments, para_map, logs

    if segments:
        return doc, segments, para_map, logs

    paras = list(doc.paragraphs)
    clean_paras = [normalize_text(p.text) for p in paras]
    nonempty = [x for x in clean_paras if x]
    if len(nonempty) >= 2 and nonempty[0].lower() in {"source", "source text"} and nonempty[1].lower() in {"target", "translation", "original translation"}:
        logs.append("DOCX: Source/Target paragraph-template mode")
        for i, p in enumerate(paras):
            text = normalize_text(p.text)
            if not is_valid_docx_source(text):
                continue
            if text.lower() in {"source", "source text", "target", "translation", "original translation"}:
                continue
            loc = f"Paragraph {i + 1}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "docx",
                "sheet": "Document",
                "location": loc,
                "source": text if mode == "pro" else "",
                "translation": "" if mode == "pro" else text,
                "text": text,
                "mode": "source_only" if mode == "pro" else "monolingual",
            })
            para_map[loc] = {"kind": "paragraph_append", "paragraph": p}
            if reached_segment_limit(segments, max_segments):
                break
        return doc, segments, para_map, logs

    logs.append("DOCX: paragraph fallback mode")
    for i, p in enumerate(paras, start=1):
        text = normalize_text(p.text)
        if is_valid_docx_source(text):
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
            para_map[seg["location"]] = {"kind": "paragraph_append", "paragraph": p}
            if reached_segment_limit(segments, max_segments):
                break
    return doc, segments, para_map, logs


def write_docx_translation_target(target_info: Any, translation: str) -> None:
    if target_info is None:
        return
    if hasattr(target_info, "add_run"):
        target_info.add_run("\n" + translation)
        return
    kind = target_info.get("kind") if isinstance(target_info, dict) else None
    if kind == "cell":
        set_docx_cell_text(target_info["cell"], translation)
    elif kind == "paragraph":
        set_docx_paragraph_text(target_info["paragraph"], translation)
    elif kind == "paragraph_append":
        target_info["paragraph"].add_run("\n" + translation)


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




def _previous_non_space_index(text: str, index: int) -> Optional[int]:
    for j in range(index - 1, -1, -1):
        if not text[j].isspace():
            return j
    return None


def _next_non_space_index(text: str, index: int) -> Optional[int]:
    for j in range(index + 1, len(text)):
        if not text[j].isspace():
            return j
    return None


def _is_measurement_quote(text: str, index: int) -> bool:
    """Treat inch/foot marks as measurements, not quotation marks.

    Examples that must NOT be flagged:
        0.1" Thick Shim
        2.31" Outer Diameter Button Plug
        1/2" Thread Adapter
        13/16"-16 Straight Adapter

    Localization files often use the straight double quote (") as an inch mark.
    A simple odd quote-count rule creates thousands of false positives for these.
    """
    prev_idx = _previous_non_space_index(text, index)
    if prev_idx is None:
        return False

    prev_char = text[prev_idx]
    if prev_char.isdigit():
        return True

    # Cases like 1⁄2" or 1/2" are already covered because previous char is digit,
    # but keep this for unicode fraction symbols such as ½".
    if prev_char in "¼½¾⅛⅜⅝⅞":
        return True

    return False


def _is_contraction_or_apostrophe(text: str, index: int) -> bool:
    """Ignore apostrophes inside words, e.g. Let's, don't, user’s."""
    prev_idx = _previous_non_space_index(text, index)
    next_idx = _next_non_space_index(text, index)
    if prev_idx is None or next_idx is None:
        return False
    return text[prev_idx].isalpha() and text[next_idx].isalpha()


def _real_quote_counts(text: str) -> Dict[str, int]:
    """Count only real quotation marks, excluding measurements and apostrophes."""
    text = text or ""
    double_quotes = {'"', '“', '”', '„', '«', '»'}
    single_quotes = {"'", '‘', '’', '‚'}
    counts = {"double": 0, "single": 0}

    for i, ch in enumerate(text):
        if ch in double_quotes:
            if _is_measurement_quote(text, i):
                continue
            counts["double"] += 1
        elif ch in single_quotes:
            if _is_measurement_quote(text, i) or _is_contraction_or_apostrophe(text, i):
                continue
            counts["single"] += 1
    return counts


def suggest_balanced_quotes(text: str, source_text: str = "") -> str:
    """Return a safer quote-balanced suggestion, or empty string if no clear fix is available.

    This function is intentionally conservative:
    - It ignores inch/foot measurements like 0.1" and 1/2".
    - It ignores apostrophes in words like don't / Let's.
    - If the target follows the source quote pattern, it does not flag.
    """
    t = text.strip()
    s = (source_text or "").strip()
    if not t:
        return ""

    target_counts = _real_quote_counts(t)
    source_counts = _real_quote_counts(s)

    # If target has no real quote imbalance, no issue.
    target_double_odd = target_counts["double"] % 2 != 0
    target_single_odd = target_counts["single"] % 2 != 0
    if not target_double_odd and not target_single_odd:
        return ""

    # If the source has the same real-quote count, the target is following source pattern.
    # This avoids false positives where the source intentionally contains one symbol.
    if source_counts == target_counts:
        return ""

    # Mixed smart/straight pairs.
    if t.startswith("“") and t.endswith('"'):
        return t[:-1] + "”"
    if t.startswith('"') and t.endswith("”"):
        return '“' + t[1:]
    if t.startswith("‘") and t.endswith("'"):
        return t[:-1] + "’"
    if t.startswith("'") and t.endswith("’"):
        return "‘" + t[1:]

    # Add a closing quote only for real quote imbalance.
    if target_double_odd and source_counts["double"] != target_counts["double"]:
        # Prefer smart closing quote if the text starts with a smart opening quote.
        if "“" in t and "”" not in t:
            return t + "”"
        return t + '"'

    if target_single_odd and source_counts["single"] != target_counts["single"]:
        if "‘" in t and "’" not in t:
            return t + "’"
        return t + "'"

    return ""

def has_latin_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text or ""))


def is_low_value_ai_style_issue(row: Dict[str, Any], include_style: bool) -> bool:
    """Drop subjective AI suggestions that look like preference, not true QA errors."""
    if row.get("Check Source") != "AI QA":
        return False

    if str(row.get("Error Type", "")).lower() == "api warning":
        return False

    error_type = str(row.get("Error Type", "")).strip().lower()
    explanation = str(row.get("Explanation", "")).strip().lower()
    wrong = str(row.get("Wrong Part", "")).strip()
    suggestion = str(row.get("Suggestion", "")).strip()
    translation = str(row.get("Translation", "")).strip()
    rule_source = str(row.get("Rule Source", "")).strip().lower()

    if not suggestion:
        return True
    if suggestion == wrong or suggestion == translation:
        return True

    subjective_types = {
        "style", "style & tone", "readability", "fluency", "fluency/readability",
        "terminology", "ai qa"
    }
    if not include_style and error_type in subjective_types and rule_source in {"", "ai"}:
        return True

    subjective_phrases = [
        "more natural", "available", "preferred", "prefer", "better", "alternative",
        "context", "style", "tone", "readability", "fluent", "idiomatic",
        "could be", "would be", "native speakers", "native-language equivalent"
    ]
    if not include_style and rule_source in {"", "ai"} and any(p in explanation for p in subjective_phrases):
        if not (has_latin_letters(wrong) and wrong in translation):
            return True

    objective_types = {"grammar", "spelling", "mixed script", "mixed language"}
    if error_type in objective_types and wrong and wrong not in translation:
        return True

    return False


def post_filter_report_rows(rows: List[Dict[str, Any]], include_style: bool) -> Tuple[List[Dict[str, Any]], int]:
    filtered = []
    dropped = 0
    seen = set()
    for row in rows:
        if is_low_value_ai_style_issue(row, include_style):
            dropped += 1
            continue
        key = (
            row.get("Sheet", ""), row.get("Location", ""), row.get("Error Type", ""),
            row.get("Wrong Part", ""), row.get("Suggestion", "")
        )
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        filtered.append(row)
    return filtered, dropped




# ==========================================================
# QUALITY GATE / FALSE-POSITIVE CONTROL
# ==========================================================

CONFIRMED_ERROR_TYPES = {
    "Placeholder", "Number", "DNT", "Glossary", "Translation Memory",
    "URL", "Email", "SKU", "Tag", "Unicode Hygiene", "Encoding",
}
CONFIRMED_FORMAT_TYPES = {"Spacing", "Formatting", "Punctuation"}
REVIEW_TYPES = {
    "Grammar", "Spelling", "Style", "Readability", "Accuracy",
    "Terminology", "Mixed Script", "Locale Convention", "Independent Review",
    "Offline QA Coverage", "Language Profile", "Rule Warning", "API Warning",
}


def classify_quality_gate(row: Dict[str, Any]) -> Tuple[str, str, int]:
    """Classify every finding into an action-safe gate status.

    Goal:
    - Confirmed Error = objective, evidence-backed issue.
    - Needs Review = plausible linguistic/style/accuracy issue, but not safe to call definite.
    - System Warning = operational issue, not translation quality.
    """
    error_type = str(row.get("Error Type", "") or "").strip()
    severity = str(row.get("Severity", "") or "").strip()
    confidence = str(row.get("Confidence", "") or "").strip()
    check_source = str(row.get("Check Source", "") or "").strip()
    rule_source = str(row.get("Rule Source", "") or "").strip()

    if "warning" in error_type.lower() or "api" in error_type.lower():
        return "System Warning", "Check configuration or retry.", 0

    # Strong deterministic / client-rule evidence.
    if error_type in CONFIRMED_ERROR_TYPES:
        return "Confirmed Error", "Fix before delivery.", 100

    if check_source in {"Company Rules", "Secure Translation Memory", "Rule Engine"} and confidence == "High":
        if error_type in {"DNT", "Glossary", "Placeholder", "Number", "Formatting", "Spacing", "Punctuation", "Mixed Script"}:
            return "Confirmed Error", "Fix before delivery.", 90

    # Formatting is only confirmed when high-confidence or critical/major objective.
    if error_type in CONFIRMED_FORMAT_TYPES and confidence in {"High", ""}:
        return "Confirmed Error", "Fix or confirm exception.", 70

    # Client corrections are stronger than generic linguistic hints.
    if "Correction History" in rule_source or "Client" in rule_source:
        return "Confirmed Error", "Apply client-approved correction.", 85

    # Linguistic issues are not always safe offline or model-only; require review unless backed by client rules.
    if error_type in REVIEW_TYPES or error_type in {"AI QA", "Client Rule"}:
        if confidence == "High" and severity in {"Critical", "Major"} and ("Client" in rule_source or check_source == "Company Rules"):
            return "Confirmed Error", "Fix before delivery.", 85
        return "Needs Review", "Human reviewer should verify.", 35

    if severity in {"Critical", "Major"} and confidence == "High":
        return "Confirmed Error", "Fix before delivery.", 75

    return "Needs Review", "Human reviewer should verify.", 25


def apply_quality_gate(issue_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add Quality Gate columns to report rows."""
    enriched: List[Dict[str, Any]] = []
    for row in issue_rows:
        new_row = dict(row)
        gate, action, score_impact = classify_quality_gate(new_row)
        new_row["Quality Gate"] = gate
        new_row["Action Required"] = action
        new_row["Score Impact"] = score_impact
        enriched.append(new_row)
    # High-confidence deterministic issues first.
    order = {"Confirmed Error": 0, "Needs Review": 1, "System Warning": 2}
    severity_order = {"Critical": 0, "Major": 1, "Minor": 2, "Review": 3}
    enriched.sort(key=lambda r: (
        order.get(str(r.get("Quality Gate", "")), 9),
        severity_order.get(str(r.get("Severity", "")), 9),
        -int(r.get("Score Impact", 0) or 0),
        str(r.get("Location", "")),
    ))
    return enriched


def quality_gate_summary(issue_rows: List[Dict[str, Any]], status_rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    confirmed = sum(1 for r in issue_rows if r.get("Quality Gate") == "Confirmed Error")
    review = sum(1 for r in issue_rows if r.get("Quality Gate") == "Needs Review")
    warning = sum(1 for r in issue_rows if r.get("Quality Gate") == "System Warning")
    segments = len(status_rows or [])
    blocked_segments = sum(1 for r in (status_rows or []) if r.get("Review Status") == "Blocked")
    review_segments = sum(1 for r in (status_rows or []) if r.get("Review Status") == "Needs Review")
    passed_segments = sum(1 for r in (status_rows or []) if r.get("Review Status") == "Pass")

    penalty = min(100, confirmed * 5 + review * 1)
    score = max(0, 100 - penalty)
    if confirmed:
        decision = "Blocked"
    elif review:
        decision = "Needs Human Review"
    else:
        decision = "Pass"

    return {
        "Quality Score": score,
        "Gate Decision": decision,
        "Confirmed Errors": confirmed,
        "Needs Review": review,
        "System Warnings": warning,
        "Segments": segments,
        "Blocked Segments": blocked_segments,
        "Review Segments": review_segments,
        "Passed Segments": passed_segments,
    }


def render_quality_gate_summary(issue_rows: List[Dict[str, Any]], status_rows: Optional[List[Dict[str, Any]]] = None) -> None:
    summary = quality_gate_summary(issue_rows, status_rows)
    st.markdown("### Quality Gate")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gate Decision", summary["Gate Decision"])
    c2.metric("Quality Score", summary["Quality Score"])
    c3.metric("Confirmed Errors", summary["Confirmed Errors"])
    c4.metric("Needs Review", summary["Needs Review"])
    if summary["Gate Decision"] == "Blocked":
        st.error("Quality gate blocked this file because confirmed errors were found.")
    elif summary["Gate Decision"] == "Needs Human Review":
        st.warning("No blocker-only decision: possible linguistic/style/accuracy items need human review.")
    else:
        st.success("Quality gate passed. No confirmed errors found.")



# ==========================================================
# SOURCE-DRIVEN FORMAT QA HELPERS
# ==========================================================

TERMINAL_PUNCT_CLASSES = {
    "period": {".", "。", "．", "｡", "।", "॥"},
    "question": {"?", "？", "¿"},
    "exclamation": {"!", "！", "¡"},
    "colon": {":", "："},
    "semicolon": {";", "；"},
    "ellipsis": {"…"},
}

CLOSING_WRAPPERS = set(')]}›»”’"\'')
OPENING_WRAPPERS = set('([{‹«“‘"\'')
BRACKET_PAIRS = [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">")]


def _trim_for_terminal(text: str) -> str:
    """Remove trailing spaces and closing quotes/brackets for terminal punctuation checks.

    Example: source ends with ." or .] should still be treated as ending with a period.
    Measurement inch marks are handled separately by _is_measurement_quote.
    """
    t = normalize_text(text).strip()
    while t and t[-1] in CLOSING_WRAPPERS:
        # Do not strip an inch mark after a number, e.g. 0.1"
        if t[-1] in {'"', '”'} and _is_measurement_quote(t, len(t) - 1):
            break
        t = t[:-1].rstrip()
    return t


def terminal_punctuation_class(text: str) -> str:
    """Return the terminal punctuation class, or empty string.

    This is source-driven: if source has no terminal punctuation, ErrorSweep does not demand one in target.
    """
    t = _trim_for_terminal(text)
    if not t:
        return ""
    if t.endswith("...") or t.endswith("…"):
        return "ellipsis"
    last = t[-1]
    for cls, chars in TERMINAL_PUNCT_CLASSES.items():
        if last in chars:
            return cls
    return ""


def has_script_range(text: str, start: str, end: str) -> bool:
    return any(start <= ch <= end for ch in text or "")


def preferred_terminal_for_target(source_cls: str, target_text: str) -> str:
    """Choose a reasonable localized equivalent for the target.

    Only used when source already has terminal punctuation.
    """
    if source_cls == "period":
        # Devanagari languages often use danda as sentence terminator.
        if has_script_range(target_text, "\u0900", "\u097F"):
            return "।"
        if has_script_range(target_text, "\u4E00", "\u9FFF"):
            return "。"
        return "."
    if source_cls == "question":
        return "?"
    if source_cls == "exclamation":
        return "!"
    if source_cls == "colon":
        return ":"
    if source_cls == "semicolon":
        return ";"
    if source_cls == "ellipsis":
        return "…"
    return ""


def replace_or_append_terminal(target: str, source_cls: str) -> str:
    """Suggest target with source-equivalent terminal punctuation.

    We append when target lacks terminal punctuation. If target has a different terminal class,
    we replace only the last terminal punctuation. We never use this when source has no terminal punctuation.
    """
    t = target.strip()
    preferred = preferred_terminal_for_target(source_cls, t)
    if not preferred:
        return t
    current_cls = terminal_punctuation_class(t)
    if not current_cls:
        return t + preferred
    # Replace last terminal punctuation after stripping closing wrappers is too complex to do perfectly,
    # so keep conservative: only append/replace if last visible char is a terminal mark.
    tt = _trim_for_terminal(t)
    if tt and terminal_punctuation_class(tt):
        idx = t.rfind(tt[-1])
        if idx >= 0:
            return t[:idx] + preferred + t[idx + 1:]
    return t + preferred


def leading_list_marker(text: str) -> Tuple[str, str]:
    """Return (marker_type, marker_text) for bullet/numbered-list starts.

    This is source-driven: target is only required to have a list marker when source has one.
    """
    t = normalize_text(text).lstrip()
    if not t:
        return "", ""
    m = re.match(r"^([•∙◦▪▫‣⁃])\s*", t)
    if m:
        return "bullet", m.group(1)
    m = re.match(r"^([\-*])\s+", t)
    if m:
        return "bullet", m.group(1)
    m = re.match(r"^(\d+[\.)])\s+", t)
    if m:
        return "numbered", m.group(1)
    m = re.match(r"^([A-Za-z][\.)])\s+", t)
    if m:
        return "lettered", m.group(1)
    return "", ""


def bracket_wrapper(text: str) -> Tuple[str, str]:
    """Detect if the whole source segment is wrapped in matching brackets.

    Example: [Welcome Screen] should normally remain bracketed in target.
    """
    t = normalize_text(text).strip()
    if len(t) < 2:
        return "", ""
    for left, right in BRACKET_PAIRS:
        if t.startswith(left) and t.endswith(right):
            return left, right
    return "", ""


def ensure_bracket_wrapper(target: str, left: str, right: str) -> str:
    t = normalize_text(target).strip()
    stripped = t.strip("".join([l + r for l, r in BRACKET_PAIRS]))
    return f"{left}{stripped}{right}"


def extract_urls(text: str) -> List[str]:
    return URL_PATTERN.findall(text or "")


def extract_emails(text: str) -> List[str]:
    return EMAIL_PATTERN.findall(text or "")


def source_driven_format_checks(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Conservative source-vs-target formatting checks.

    Golden rule: only enforce source formatting if the source actually has that formatting.
    If source has no ending period, ErrorSweep will not demand a period in target.
    """
    rows: List[Dict[str, Any]] = []
    source = normalize_text(segment.get("source", ""))
    target = normalize_text(segment.get("translation", "") or segment.get("text", ""))
    if not source or not target:
        return rows

    src_cls = terminal_punctuation_class(source)
    tgt_cls = terminal_punctuation_class(target)
    if src_cls and tgt_cls != src_cls:
        suggestion = replace_or_append_terminal(target, src_cls)
        rows.append(make_report_row(
            segment,
            "Punctuation",
            "Minor",
            "missing or different ending punctuation",
            visible_invisibles(suggestion),
            f"Source ends with {src_cls} punctuation; target should preserve an equivalent. If source has no ending punctuation, this rule does not run.",
            "Rule Engine",
            "Source-driven format rules",
            "High",
        ))

    src_marker_type, src_marker = leading_list_marker(source)
    tgt_marker_type, _ = leading_list_marker(target)
    if src_marker_type and tgt_marker_type != src_marker_type:
        rows.append(make_report_row(
            segment,
            "Formatting",
            "Minor",
            f"missing {src_marker_type} list marker",
            src_marker + " " + target.lstrip(),
            "Source begins with a list/bullet marker, but target does not preserve an equivalent marker.",
            "Rule Engine",
            "Source-driven format rules",
            "High",
        ))

    left, right = bracket_wrapper(source)
    if left and right and not (target.strip().startswith(left) and target.strip().endswith(right)):
        rows.append(make_report_row(
            segment,
            "Formatting",
            "Minor",
            f"missing wrapper {left}{right}",
            ensure_bracket_wrapper(target, left, right),
            "Source segment is wrapped in brackets; target should preserve the same wrapper unless client rules say otherwise.",
            "Rule Engine",
            "Source-driven format rules",
            "Medium",
        ))

    # Ellipsis only if source has ellipsis. Do not invent ellipsis when source does not have it.
    source_has_ellipsis = source.strip().endswith("...") or source.strip().endswith("…")
    target_has_ellipsis = target.strip().endswith("...") or target.strip().endswith("…")
    if source_has_ellipsis and not target_has_ellipsis:
        rows.append(make_report_row(
            segment,
            "Punctuation",
            "Minor",
            "missing ellipsis",
            target.strip() + "…",
            "Source ends with an ellipsis; target should preserve an equivalent ellipsis.",
            "Rule Engine",
            "Source-driven format rules",
            "High",
        ))

    # URLs/emails must be preserved exactly if present in source.
    src_urls = extract_urls(source)
    for url in src_urls:
        if url not in target:
            rows.append(make_report_row(
                segment, "URL", "Major", url, f"Keep URL unchanged: {url}",
                "URL from source is missing or changed in target.", "Rule Engine", "Source-driven format rules", "High"
            ))
    src_emails = extract_emails(source)
    for email in src_emails:
        if email not in target:
            rows.append(make_report_row(
                segment, "Email", "Major", email, f"Keep email unchanged: {email}",
                "Email address from source is missing or changed in target.", "Rule Engine", "Source-driven format rules", "High"
            ))

    return rows

def deterministic_checks(segment: Dict[str, Any], rules: Dict[str, Any], enable_zwnj: bool = True) -> List[Dict[str, Any]]:
    """Modular QA Engine v2 wrapper.

    This keeps the existing app shell and file extraction/output logic unchanged,
    but delegates offline QA to qa_engine_v2.py. If the external module is missing,
    the app returns a safe warning row instead of crashing.
    """
    try:
        from qa_engine_global_v14 import deterministic_checks_v2
        return deterministic_checks_v2(
            segment=segment,
            rules=rules,
            target_language=st.session_state.get("es_target_language", "Auto-detect"),
            domain=st.session_state.get("es_domain", "Auto-detect"),
            enable_zwnj=enable_zwnj,
            enable_language_tool=bool(st.session_state.get("es_enable_languagetool", False)),
            language_tool_mode=str(st.session_state.get("es_languagetool_mode", "public")).lower(),
            language_tool_max_chars=int(st.session_state.get("es_languagetool_max_chars", 1200)),
        )
    except Exception as exc:
        return [{
            "Sheet": segment.get("sheet", ""),
            "Location": segment.get("location", ""),
            "Mode": segment.get("mode", ""),
            "Source Text": truncate(segment.get("source", ""), 400),
            "Translation": truncate(segment.get("translation", segment.get("text", "")), 400),
            "Error Type": "Rule Engine Warning",
            "Severity": "Review",
            "Wrong Part": "QA Engine v2",
            "Suggestion": "Check qa_engine_global_v12.py is present in GitHub and deployment.",
            "Explanation": f"Modular rule engine could not run: {str(exc)[:180]}",
            "Check Source": "Rule Engine",
            "Rule Source": "System",
            "Confidence": "Low",
        }]



# ==========================================================
# AI SERVICE CALLS
# ==========================================================

def openai_json(client: AI, model: str, instructions: str, prompt: str, max_output_tokens: int = 3000) -> List[Dict[str, Any]]:
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
    client: AI,
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

    if include_style:
        style_policy = (
            "Style and terminology suggestions are allowed, but only when they are clearly better, "
            "supported by context, and not merely a personal preference."
        )
    else:
        style_policy = (
            "Do NOT flag subjective style, wording, or terminology preferences unless a company rule, glossary, "
            "DNT list, placeholder rule, or clear source meaning proves it is wrong. "
            "Do NOT flag acceptable target-language loanwords, brand terms, approved transliterations, or product names as errors unless uploaded client rules say otherwise."
        )

    instructions = (
        "You are ErrorSweep, a strict but conservative linguistic QA engine for localization. "
        "Your job is to find actual QA defects, not to rewrite acceptable translations. "
        "Return only valid JSON. No markdown. Do not invent issues."
    )

    prompt = f"""
Domain: {domain}
Strictness: {STRICTNESS_GUIDE[strictness]}
Style policy: {style_policy}

Review the following segments for real QA errors.

{chr(10).join(numbered_parts)}

Important rules:
- Output an error only when there is clear evidence in the source, translation, or company rules.
- Do not suggest a different phrase only because it sounds more natural.
- Do not change a valid translation into a different meaning.
- Source-driven formatting policy: preserve source formatting only when the source actually has that formatting.
- If the source does NOT end with a period/question/exclamation/colon/semicolon/ellipsis, do NOT demand that punctuation in the target.
- If the source has measurement inch/foot symbols like 0.1", 1/2", or 13/16", treat them as measurement marks, not quotation marks.
- Preserve placeholders, variables, HTML/XML tags, URLs, emails, numbers, and DNT terms exactly.
- Preserve list/bullet markers only when the source has a list/bullet marker.
- Preserve bracket wrappers like [Label] only when the source is bracket-wrapped.
- Do not flag transliterated UI/product terms in the target script unless company rules require another term.
- Mixed script is an error when Roman/Latin words appear inside target-language text unexpectedly, for example romanized words inside a non-Latin target language.
- If the issue is grammar/spelling/mixed script, "wrong_part" must be an exact visible fragment from the translation.
- "suggestion" must be a concrete correction. Prefer a full corrected translation when possible.
- If you are unsure, omit the error.

Check only these categories:
- Accuracy: source meaning changed, omitted, or added.
- Grammar: real grammar mistake in target language.
- Spelling: real spelling or typo issue.
- Mixed Script: unexpected Latin/Roman script in target-language text.
- Formatting: issue not already covered by deterministic rules.
- Client Rule: clear violation of uploaded company rules.
- Terminology: only if supported by glossary/DNT/client rule or clearly wrong for the domain.

Return ONLY this JSON array:
[
  {{
    "location": "exact location from input",
    "language_detected": "detected language or Unknown",
    "error_type": "Accuracy|Grammar|Spelling|Mixed Script|Terminology|Formatting|Client Rule",
    "severity": "Minor|Major|Critical",
    "wrong_part": "exact wrong fragment from translation, or concise description for Accuracy only",
    "suggestion": "corrected target text or exact replacement",
    "explanation": "brief evidence-based reason",
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
            "wrong_part": "AI service call failed",
            "suggestion": "Retry with fewer segments or check API key/settings.",
            "explanation": str(e)[:250],
            "rule_source": "System",
            "confidence": "Low",
        }]

    rows = []
    loc_to_seg = {s.get("location", ""): s for s in segments}
    allowed_types = {"Accuracy", "Grammar", "Spelling", "Mixed Script", "Terminology", "Formatting", "Client Rule", "API Warning"}
    for err in raw:
        loc = err.get("location", "")
        seg = loc_to_seg.get(loc, {})
        error_type = err.get("error_type", "AI QA")
        if error_type not in allowed_types:
            error_type = "AI QA"
        rows.append(make_report_row(
            seg,
            error_type,
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
    client: AI,
    model: str,
    segments: List[Dict[str, Any]],
    target_language: str,
    domain: str,
    rules: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Translate with strict protected-token preservation.

    This protects global placeholders such as {{email}}, URLs, tags,
    bullets, and units before sending text to the model, then restores them.
    Square-bracketed UI labels like [Log In] may be localized; only their bracket structure is checked.
    """
    if not segments:
        return []
    protected_segments = protect_segments_for_translation(segments)
    original_by_loc = {str(s.get("location", "")): s for s in segments}

    parts = []
    expected_locations = []
    for i, seg in enumerate(protected_segments, start=1):
        loc = seg.get("location", "")
        expected_locations.append(loc)
        relevant = retrieve_relevant_rules(seg, rules, 1200) if rules else ""
        parts.append(
            f"[Segment {i}]\n"
            f"Location: {loc}\n"
            f"Source: {seg.get('source') or seg.get('text','')}\n"
            f"Protected tokens: {json.dumps(seg.get('_protected_tokens', []), ensure_ascii=False)}\n"
            f"Relevant Company Rules:\n{relevant if relevant else '(none)'}"
        )

    instructions = (
        "You are a professional localization translator. Return only valid JSON. "
        "Never translate, alter, remove, or reorder protected tokens such as ZXPH0ZX, placeholders, variables, tags, URLs, emails, units, or bullets. Square-bracketed UI labels may be localized; keep bracket delimiters where source uses them. "
        "Preserve placeholders, numbers, tags, punctuation intent, and product terms."
    )
    prompt = f"""
Translate these segments into {target_language}.
Domain: {domain}

Critical rules:
- Return exactly one item per input location.
- Keep marker tokens like ZXPH0ZX unchanged. They will be restored by the app.
- Square-bracketed UI labels may be localized. Keep the square brackets when they are used as UI-label delimiters.
- Keep DNT terms unchanged. Follow glossary terms.
- Do not return blank translation for non-empty source.

Expected locations:
{json.dumps(expected_locations, ensure_ascii=False)}

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
        raw = openai_json(client, model, instructions, prompt, max_output_tokens=6000)
    except Exception as e:
        return [{"location": "API", "translation": "", "error": str(e)}]

    out = []
    for item in raw:
        loc = str(item.get("location", ""))
        if loc not in original_by_loc:
            continue
        restored = restore_translation_item(original_by_loc[loc], item.get("translation", ""))
        out.append({"location": loc, "translation": restored})
    return out


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
Review AI translations into {target_language}.
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
            "error_type": "Review Service Warning",
            "severity": "Review",
            "wrong_part": "Independent review failed",
            "suggestion": "Retry with fewer segments or contact the administrator.",
            "explanation": str(e)[:250],
            "confidence": "Low",
        }]


# ==========================================================
# SEGMENT COVERAGE / FULL-FILE STATUS REPORT
# ==========================================================

def highest_severity(rows: List[Dict[str, Any]]) -> str:
    order = {"Critical": 4, "Major": 3, "Minor": 2, "Review": 1, "Pass": 0}
    if not rows:
        return "Pass"
    return max((str(r.get("Severity", "Review")) for r in rows), key=lambda x: order.get(x, 1))


def build_segment_status_rows(segments: List[Dict[str, Any]], issue_rows: List[Dict[str, Any]], checked_by: str = "Rules + AI") -> List[Dict[str, Any]]:
    """Build one status row for every extracted segment so users can see full-file coverage."""
    issues_by_loc: Dict[str, List[Dict[str, Any]]] = {}
    for row in issue_rows:
        loc = str(row.get("Location", ""))
        if loc:
            issues_by_loc.setdefault(loc, []).append(row)

    status_rows: List[Dict[str, Any]] = []
    for seg in segments:
        loc = str(seg.get("location", ""))
        rows = issues_by_loc.get(loc, [])
        issue_count = len(rows)
        confirmed = sum(1 for r in rows if r.get("Quality Gate") == "Confirmed Error")
        needs_review = sum(1 for r in rows if r.get("Quality Gate") == "Needs Review")
        if confirmed:
            status = "Blocked"
        elif needs_review or issue_count:
            status = "Needs Review"
        else:
            status = "Pass"
        severity = highest_severity(rows)
        error_types = "; ".join(sorted({str(r.get("Error Type", "")) for r in rows if r.get("Error Type")}))
        gate_types = "; ".join(sorted({str(r.get("Quality Gate", "")) for r in rows if r.get("Quality Gate")}))
        suggestions = " | ".join(dict.fromkeys(str(r.get("Suggestion", "")) for r in rows if str(r.get("Suggestion", "")).strip()))
        explanations = " | ".join(dict.fromkeys(str(r.get("Explanation", "")) for r in rows if str(r.get("Explanation", "")).strip()))

        status_rows.append({
            "Sheet": seg.get("sheet", ""),
            "Location": loc,
            "Mode": seg.get("mode", ""),
            "Source Text": truncate(seg.get("source", ""), 500),
            "Translation": truncate(seg.get("translation", seg.get("text", "")), 500),
            "Review Status": status,
            "Issue Count": issue_count,
            "Confirmed Error Count": confirmed,
            "Needs Review Count": needs_review,
            "Highest Severity": severity,
            "Quality Gate Types": gate_types,
            "Error Types": error_types,
            "Suggestion Summary": truncate(suggestions, 800) if suggestions else "No change suggested",
            "Explanation Summary": truncate(explanations, 800) if explanations else "Checked; no issue found",
            "Checked By": checked_by,
        })
    return status_rows

def merge_issue_and_status_csv(issue_rows: List[Dict[str, Any]], status_rows: List[Dict[str, Any]]) -> bytes:
    """For non-Excel files, return one CSV that includes all checked segments and issue details."""
    status_df = pd.DataFrame(status_rows)
    issue_df = pd.DataFrame(issue_rows)
    output = io.StringIO()
    output.write("ALL SEGMENT REVIEW\n")
    status_df.to_csv(output, index=False)
    output.write("\nISSUE DETAILS\n")
    issue_df.to_csv(output, index=False)
    return output.getvalue().encode("utf-8-sig")


# ==========================================================
# OUTPUT BUILDERS
# ==========================================================

def safe_report_cell_value(value: Any) -> Any:
    """Write report text safely. If a value starts with =/+/-/@, Excel may treat it as a formula."""
    if value is None:
        return ""
    if isinstance(value, str):
        if value.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    return value


def add_report_sheet_to_workbook(wb, sheet_name: str, report_rows: List[Dict[str, Any]], headers: List[str]):
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)
    ws.append(headers)
    for row in report_rows:
        ws.append([safe_report_cell_value(row.get(h, "")) for h in headers])
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


def dataframe_to_xlsx_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    """Create an Excel workbook from multiple DataFrames."""
    wb = Workbook()
    # Remove default sheet after creating our own sheets.
    default = wb.active
    wb.remove(default)

    for sheet_name, df in sheets.items():
        safe_name = str(sheet_name)[:31] or "Sheet"
        ws = wb.create_sheet(safe_name)
        if df is None or df.empty:
            ws.append(["Status"])
            ws.append(["No rows available"])
        else:
            ws.append([str(c) for c in df.columns])
            for _, row in df.iterrows():
                ws.append([safe_report_cell_value(row.get(c, "")) for c in df.columns])
        style_header(ws)
        for col in ws.columns:
            col_letter = col[0].column_letter
            max_len = 12
            for cell in col[:200]:
                val = str(cell.value or "")
                max_len = max(max_len, min(len(val) + 2, 70))
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.column_dimensions[col_letter].width = max_len

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def build_excel_report_bytes(
    issue_rows: List[Dict[str, Any]],
    status_rows: List[Dict[str, Any]],
    extraction_logs: Optional[List[str]] = None,
    translation_rows: Optional[List[Dict[str, Any]]] = None,
    title: str = "ErrorSweep Report",
) -> bytes:
    """Always return an Excel report, regardless of input file format."""
    extraction_logs = extraction_logs or []
    sheets: Dict[str, pd.DataFrame] = {}
    qsum = quality_gate_summary(issue_rows, status_rows)
    sheets["Summary"] = pd.DataFrame([
        {"Metric": "Report", "Value": title},
        {"Metric": "Quality Score", "Value": qsum["Quality Score"]},
        {"Metric": "Gate Decision", "Value": qsum["Gate Decision"]},
        {"Metric": "Segments checked", "Value": len(status_rows)},
        {"Metric": "Issues found", "Value": len(issue_rows)},
        {"Metric": "Confirmed Errors", "Value": qsum["Confirmed Errors"]},
        {"Metric": "Needs Review", "Value": qsum["Needs Review"]},
        {"Metric": "System Warnings", "Value": qsum["System Warnings"]},
        {"Metric": "Generated at", "Value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
    ])
    sheets["All Segment Review"] = pd.DataFrame(status_rows)
    sheets["Issue Details"] = pd.DataFrame(issue_rows)
    if translation_rows is not None:
        sheets["Translations"] = pd.DataFrame(translation_rows)
    sheets["Extraction Log"] = pd.DataFrame([{"Log": x} for x in extraction_logs] or [{"Log": "No extraction log."}])
    return dataframe_to_xlsx_bytes(sheets)


def extract_pdf_segments(uploaded_file, mode: str, max_segments: int):
    """Extract readable lines from PDFs. Output/report is Excel; source PDF is not rewritten."""
    logs = []
    if PdfReader is None:
        return [], ["PDF support package is unavailable. Add pypdf to requirements.txt."]
    try:
        reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
        lines = []
        for page_index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            for line_no, line in enumerate(text.splitlines(), start=1):
                clean = clean_line_for_ai(line)
                if clean and len(clean) > 2:
                    lines.append((page_index, line_no, clean))
        segments = []
        for page_index, line_no, clean in limit_sequence(lines, max_segments):
            loc = f"Page {page_index}, Line {line_no}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "pdf",
                "sheet": "PDF",
                "location": loc,
                "source": clean if mode == "pro" else "",
                "translation": clean if mode == "qa" else "",
                "text": clean,
                "mode": "source_only" if mode == "pro" else "monolingual",
            })
        logs.append(f"PDF: extracted {len(segments)} text segment(s).")
        if not segments:
            logs.append("PDF appears image-based or has no extractable text. OCR is not enabled in this MVP.")
        return segments, logs
    except Exception as exc:
        return [], [f"Could not read PDF: {exc}"]




# ==========================================================
# SAME-FORMAT PRO TRANSLATION BUILDERS
# ==========================================================

def extract_json_pro_segments(uploaded_file, max_segments: int):
    """Extract string values from JSON and keep paths so translated output remains JSON."""
    data = uploaded_file.getvalue()
    raw_text, encoding_used = decode_text_bytes(data)
    logs = [f"JSON: decoded as {encoding_used}"]
    try:
        obj = json.loads(raw_text)
    except Exception as exc:
        # Fallback: treat as text-like if JSON cannot be parsed.
        logs.append(f"JSON parse failed; falling back to text mode: {exc}")
        text_original, segments, text_logs = extract_text_segments(uploaded_file, "pro", max_segments)
        return obj if False else None, segments, {}, logs + text_logs

    segments: List[Dict[str, Any]] = []
    path_map: Dict[str, List[Any]] = {}

    def walk(node: Any, path: List[Any]) -> None:
        if reached_segment_limit(segments, max_segments):
            return
        if isinstance(node, dict):
            for k, v in node.items():
                # Avoid translating keys; only translate string values.
                walk(v, path + [k])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [i])
        elif isinstance(node, str):
            clean = clean_line_for_ai(node)
            if clean and len(clean) > 1:
                loc = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in path)
                seg = {
                    "id": len(segments) + 1,
                    "file_type": "json",
                    "sheet": "JSON",
                    "location": loc,
                    "source": clean,
                    "translation": "",
                    "text": clean,
                    "mode": "source_only",
                }
                segments.append(seg)
                path_map[loc] = path

    walk(obj, [])
    logs.append(f"JSON: extracted {len(segments)} string value segment(s).")
    return obj, segments, path_map, logs


def set_json_path(obj: Any, path: List[Any], value: str) -> None:
    cur = obj
    for p in path[:-1]:
        cur = cur[p]
    if path:
        cur[path[-1]] = value


def build_translated_json_bytes(obj: Any, path_map: Dict[str, List[Any]], translations_by_loc: Dict[str, str]) -> bytes:
    for loc, path in path_map.items():
        trans = translations_by_loc.get(loc, "")
        if trans:
            set_json_path(obj, path, trans)
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


def extract_srt_pro_segments(uploaded_file, max_segments: int):
    """Extract subtitle text lines while preserving SRT cue numbers and timecodes."""
    raw_text, encoding_used = decode_text_bytes(uploaded_file.getvalue())
    lines = raw_text.splitlines()
    segments: List[Dict[str, Any]] = []
    line_map: Dict[str, List[int]] = {}
    i = 0
    cue_number = 0
    timestamp_re = re.compile(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}")
    while i < len(lines):
        # Optional cue index
        if not lines[i].strip():
            i += 1
            continue
        if i + 1 < len(lines) and timestamp_re.search(lines[i + 1]):
            cue_number += 1
            time_idx = i + 1
            text_start = i + 2
        elif timestamp_re.search(lines[i]):
            cue_number += 1
            time_idx = i
            text_start = i + 1
        else:
            i += 1
            continue
        text_indices = []
        j = text_start
        while j < len(lines) and lines[j].strip():
            text_indices.append(j)
            j += 1
        cue_text = "\n".join(lines[idx] for idx in text_indices).strip()
        if cue_text and len(cue_text) > 1:
            loc = f"Cue {cue_number}"
            segments.append({
                "id": len(segments) + 1,
                "file_type": "srt",
                "sheet": "SRT",
                "location": loc,
                "source": cue_text,
                "translation": "",
                "text": cue_text,
                "mode": "source_only",
            })
            line_map[loc] = text_indices
            if reached_segment_limit(segments, max_segments):
                break
        i = max(j + 1, i + 1)
    return raw_text, segments, line_map, [f"SRT: extracted {len(segments)} cue segment(s) (decoded as {encoding_used})."]


def build_translated_srt_bytes(raw_text: str, line_map: Dict[str, List[int]], translations_by_loc: Dict[str, str]) -> bytes:
    lines = raw_text.splitlines()
    for loc, indices in line_map.items():
        trans = translations_by_loc.get(loc, "")
        if not trans or not indices:
            continue
        trans_lines = trans.splitlines() or [trans]
        # Replace first original subtitle text line with full translation, blank the rest.
        lines[indices[0]] = trans_lines[0]
        insert_extra = trans_lines[1:]
        for idx in indices[1:]:
            lines[idx] = ""
        if insert_extra:
            # Insert extra translation lines immediately after first text line.
            first = indices[0]
            lines = lines[:first + 1] + insert_extra + lines[first + 1:]
    return ("\n".join(lines) + "\n").encode("utf-8-sig")


def xml_local_name(tag: str) -> str:
    return str(tag).split("}")[-1].lower()


def make_xml_target_tag(source_tag: str) -> str:
    if "}" in source_tag:
        ns = source_tag.split("}")[0].strip("{")
        return "{" + ns + "}target"
    return "target"


def extract_xml_xliff_pro_segments(uploaded_file, max_segments: int):
    """Extract XLIFF/XML/XLZ <source>/<target> pairs and preserve XML output."""
    import xml.etree.ElementTree as ET
    raw_text, encoding_used = decode_text_bytes(uploaded_file.getvalue())
    logs = [f"XML/XLIFF: decoded as {encoding_used}"]
    try:
        tree = ET.ElementTree(ET.fromstring(raw_text))
    except Exception as exc:
        logs.append(f"XML parse failed; falling back to text mode: {exc}")
        text_original, segments, text_logs = extract_text_segments(uploaded_file, "pro", max_segments)
        return None, segments, {}, logs + text_logs

    root = tree.getroot()
    segments: List[Dict[str, Any]] = []
    target_map: Dict[str, Any] = {}

    for parent in root.iter():
        children = list(parent)
        if not children:
            continue
        src_el = None
        tgt_el = None
        for child in children:
            lname = xml_local_name(child.tag)
            if lname == "source" and src_el is None:
                src_el = child
            elif lname == "target" and tgt_el is None:
                tgt_el = child
        if src_el is None:
            continue
        src_text = clean_line_for_ai("".join(src_el.itertext()))
        if not src_text:
            continue
        if tgt_el is None:
            tgt_el = ET.Element(make_xml_target_tag(src_el.tag))
            try:
                insert_at = children.index(src_el) + 1
                parent.insert(insert_at, tgt_el)
            except Exception:
                parent.append(tgt_el)
        loc = f"XML Segment {len(segments) + 1}"
        segments.append({
            "id": len(segments) + 1,
            "file_type": "xml",
            "sheet": "XML",
            "location": loc,
            "source": src_text,
            "translation": clean_line_for_ai("".join(tgt_el.itertext())) if tgt_el is not None else "",
            "text": src_text,
            "mode": "source_only",
        })
        target_map[loc] = tgt_el
        if reached_segment_limit(segments, max_segments):
            break
    logs.append(f"XML/XLIFF: extracted {len(segments)} source/target segment(s).")
    return tree, segments, target_map, logs


def build_translated_xml_bytes(tree: Any, target_map: Dict[str, Any], translations_by_loc: Dict[str, str]) -> bytes:
    for loc, target_el in target_map.items():
        trans = translations_by_loc.get(loc, "")
        if trans:
            # Replace text content while preserving attributes and tag.
            target_el.text = trans
    output = io.BytesIO()
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output.getvalue()




def extract_xliff_pairs_from_xml_text(raw_text: str, mode: str, max_segments: int, source_label: str = "File") -> Tuple[List[Dict[str, Any]], List[str]]:
    """Extract source/target pairs from XLIFF/XML/XLZ text.

    This works for plain .xliff/.xlf/.xml files and for .xlz packages after the
    XLIFF file is extracted from the ZIP. It supports namespaces and common
    XLIFF structures where <source> and <target> are siblings.
    """
    import xml.etree.ElementTree as ET
    logs: List[str] = []
    segments: List[Dict[str, Any]] = []

    try:
        root = ET.fromstring(raw_text)
    except Exception as exc:
        return [], [f"{source_label}: XML/XLIFF parse failed: {exc}"]

    for parent in root.iter():
        children = list(parent)
        if not children:
            continue

        src_el = None
        tgt_el = None
        for child in children:
            lname = xml_local_name(child.tag)
            if lname == "source" and src_el is None:
                src_el = child
            elif lname == "target" and tgt_el is None:
                tgt_el = child

        if src_el is None:
            continue

        src_text = clean_line_for_ai("".join(src_el.itertext()))
        tgt_text = clean_line_for_ai("".join(tgt_el.itertext())) if tgt_el is not None else ""

        if not src_text:
            continue
        if mode == "qa" and not tgt_text:
            continue

        loc = f"{source_label} Segment {len(segments) + 1}"
        segments.append({
            "id": len(segments) + 1,
            "file_type": "xliff",
            "sheet": source_label,
            "location": loc,
            "source": src_text,
            "translation": tgt_text,
            "text": tgt_text if mode == "qa" else src_text,
            "mode": "bilingual" if tgt_text else "source_only",
        })

        if reached_segment_limit(segments, max_segments):
            break

    logs.append(f"{source_label}: extracted {len(segments)} source/target segment(s).")
    return segments, logs


def extract_xlz_segments_from_zip(data: bytes, mode: str, max_segments: int) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    """Extract XLIFF/XML/XLZ segments from compressed .xlz / zipped localization packages.

    Many CAT/TMS systems export .xlz as a ZIP package that contains .xlf/.xliff
    files. Treating .xlz as latin-1 text produces fake binary segments; this
    function opens the ZIP and extracts the actual XLIFF/XML/XLZ content safely.
    """
    logs: List[str] = []
    all_segments: List[Dict[str, Any]] = []

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            candidate_names = [
                n for n in zf.namelist()
                if n.lower().endswith((".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".xml"))
                and not n.startswith("__MACOSX/")
            ]

            if not candidate_names:
                logs.append("XLZ package opened, but no .xlf/.xliff/.xml file was found inside.")
                return "", [], logs

            logs.append(f"XLZ package detected. Found {len(candidate_names)} XLIFF/XML/XLZ file(s) inside.")

            for inner_name in candidate_names:
                if reached_segment_limit(all_segments, max_segments):
                    break

                try:
                    inner_data = zf.read(inner_name)
                    inner_text, encoding_used = decode_text_bytes(inner_data)
                except Exception as exc:
                    logs.append(f"{inner_name}: could not read/decode file: {exc}")
                    continue

                remaining_limit = 0 if unlimited_scan(max_segments) else max(0, int(max_segments) - len(all_segments))
                segs, seg_logs = extract_xliff_pairs_from_xml_text(
                    inner_text,
                    mode=mode,
                    max_segments=remaining_limit,
                    source_label=inner_name,
                )
                logs.extend([f"{msg} (decoded as {encoding_used})" for msg in seg_logs])

                for seg in segs:
                    seg["id"] = len(all_segments) + 1
                    all_segments.append(seg)
                    if reached_segment_limit(all_segments, max_segments):
                        break

    except Exception as exc:
        logs.append(f"Could not open XLZ package: {exc}")
        return "", [], logs

    return "", all_segments, logs


def extract_xlz_pro_segments(uploaded_file, max_segments: int):
    """Extract XLIFF/XML/XLZ segments from an .xlz package for Pro translation.

    Returns a package object that can later be rebuilt as .xlz with translated
    <target> nodes filled in.
    """
    import xml.etree.ElementTree as ET
    data = uploaded_file.getvalue()
    logs: List[str] = []
    segments: List[Dict[str, Any]] = []
    target_map: Dict[str, Any] = {}
    package = {
        "entries": {},
        "trees": {},
        "xml_names": set(),
        "original_name": uploaded_file.name,
    }

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                package["entries"][info.filename] = zf.read(info.filename)

            candidate_names = [
                n for n in zf.namelist()
                if n.lower().endswith((".xliff", ".xlf", ".sdlxliff", ".mqxliff", ".xml"))
                and not n.startswith("__MACOSX/")
            ]

            if not candidate_names:
                logs.append("XLZ package opened, but no .xlf/.xliff/.xml file was found inside.")
                return None, [], {}, logs

            logs.append(f"XLZ package detected. Found {len(candidate_names)} XLIFF/XML/XLZ file(s) inside.")

            for inner_name in candidate_names:
                if reached_segment_limit(segments, max_segments):
                    break

                raw_text, encoding_used = decode_text_bytes(package["entries"][inner_name])
                try:
                    tree = ET.ElementTree(ET.fromstring(raw_text))
                except Exception as exc:
                    logs.append(f"{inner_name}: XML parse failed: {exc}")
                    continue

                package["trees"][inner_name] = tree
                package["xml_names"].add(inner_name)
                root = tree.getroot()

                for parent in root.iter():
                    if reached_segment_limit(segments, max_segments):
                        break
                    children = list(parent)
                    if not children:
                        continue
                    src_el = None
                    tgt_el = None
                    for child in children:
                        lname = xml_local_name(child.tag)
                        if lname == "source" and src_el is None:
                            src_el = child
                        elif lname == "target" and tgt_el is None:
                            tgt_el = child
                    if src_el is None:
                        continue
                    src_text = clean_line_for_ai("".join(src_el.itertext()))
                    if not src_text:
                        continue
                    if tgt_el is None:
                        tgt_el = ET.Element(make_xml_target_tag(src_el.tag))
                        try:
                            insert_at = children.index(src_el) + 1
                            parent.insert(insert_at, tgt_el)
                        except Exception:
                            parent.append(tgt_el)
                    loc = f"{inner_name} Segment {len(segments) + 1}"
                    segments.append({
                        "id": len(segments) + 1,
                        "file_type": "xlz",
                        "sheet": inner_name,
                        "location": loc,
                        "source": src_text,
                        "translation": clean_line_for_ai("".join(tgt_el.itertext())) if tgt_el is not None else "",
                        "text": src_text,
                        "mode": "source_only",
                    })
                    target_map[loc] = (inner_name, tgt_el)

                logs.append(f"{inner_name}: extracted segments (decoded as {encoding_used}).")

    except Exception as exc:
        logs.append(f"Could not open XLZ package: {exc}")
        return None, [], {}, logs

    logs.append(f"XLZ: extracted {len(segments)} source segment(s) for translation.")
    return package, segments, target_map, logs


def build_translated_xlz_bytes(package: Dict[str, Any], target_map: Dict[str, Any], translations_by_loc: Dict[str, str]) -> bytes:
    """Rebuild an .xlz ZIP package with translated <target> elements filled in."""
    import zipfile as _zipfile
    for loc, target_info in target_map.items():
        if loc not in translations_by_loc:
            continue
        _inner_name, target_el = target_info
        trans = translations_by_loc.get(loc, "")
        if trans:
            target_el.text = trans

    output = io.BytesIO()
    with _zipfile.ZipFile(output, "w", compression=_zipfile.ZIP_DEFLATED) as zf:
        for name, original_bytes in package.get("entries", {}).items():
            if name in package.get("xml_names", set()) and name in package.get("trees", {}):
                xml_out = io.BytesIO()
                package["trees"][name].write(xml_out, encoding="utf-8", xml_declaration=True)
                zf.writestr(name, xml_out.getvalue())
            else:
                zf.writestr(name, original_bytes)
    output.seek(0)
    return output.getvalue()

def is_text_like_extension(file_name: str) -> bool:
    lower = file_name.lower()
    return lower.endswith((
        ".txt", ".srt", ".md", ".markdown", ".po", ".pot", ".properties", ".strings", ".resx",
        ".html", ".htm", ".yaml", ".yml", ".ini", ".log"
    ))


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

    if "Quality Gate" in df.columns:
        st.markdown("#### Quality Gate Breakdown")
        gate_df = df["Quality Gate"].value_counts().reset_index()
        gate_df.columns = ["Quality Gate", "Count"]
        st.dataframe(gate_df, use_container_width=True, hide_index=True)

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
# SUPABASE AUTH + CREDITS + USAGE LOGS
# ==========================================================

SUPABASE_TIMEOUT = 25
DEFAULT_TRIAL_CREDITS = 25
PLAN_CREDITS = {
    "trial": 25,
    "errorsweep": 200,
    "pro": 600,
    "agency": 2500,
    "enterprise": 10000,
}


# Billing plan catalog.
# Payment links are read from Streamlit Secrets, so no payment URL is stored in GitHub.
PLAN_CATALOG = {
    "trial": {
        "name": "Free Trial",
        "price": "₹0",
        "credits": 25,
        "tagline": "Try ErrorSweep with a small monthly allowance.",
        "features": [
            "Offline QA checks",
            "Limited segment preview",
            "Basic Excel report",
            "No Rules ZIP for trial users",
        ],
        "secret_key": "",
    },
    "errorsweep": {
        "name": "ErrorSweep",
        "price": "₹999 / month",
        "credits": 200,
        "tagline": "QA review, reports, and client rules for regular users.",
        "features": [
            "QA Run + suggestions",
            "Rules ZIP support",
            "Excel QA reports",
            "Offline + optional AI checks",
        ],
        "secret_key": "PAYMENT_LINK_ERRORSWEEP",
    },
    "pro": {
        "name": "ErrorSweep Pro",
        "price": "₹2,999 / month",
        "credits": 600,
        "tagline": "Translation + review workflow for production files.",
        "features": [
            "Everything in ErrorSweep",
            "Translate + Review",
            "Same-format translation output where possible",
            "Independent review workflow",
        ],
        "secret_key": "PAYMENT_LINK_PRO",
    },
    "agency": {
        "name": "Agency",
        "price": "₹9,999 / month",
        "credits": 2500,
        "tagline": "Higher-volume workflows for localization teams.",
        "features": [
            "Everything in Pro",
            "Higher monthly credits",
            "Large-file workflows",
            "Priority manual support",
        ],
        "secret_key": "PAYMENT_LINK_AGENCY",
    },
    "enterprise": {
        "name": "Enterprise",
        "price": "Custom",
        "credits": 10000,
        "tagline": "Custom credits, limits, private support, and rule logic.",
        "features": [
            "Custom monthly credits",
            "Dedicated support",
            "Private deployment option",
            "Client-specific rule packs",
        ],
        "secret_key": "PAYMENT_LINK_ENTERPRISE",
    },
}


def normalize_plan(plan: Any) -> str:
    plan = str(plan or "trial").strip().lower()
    return plan if plan in PLAN_CATALOG else "trial"


def get_payment_link(plan: str) -> str:
    plan = normalize_plan(plan)
    secret_key = PLAN_CATALOG[plan].get("secret_key", "")
    candidate_keys = []
    if secret_key:
        candidate_keys.append(secret_key)
    candidate_keys.extend([
        f"PAYMENT_LINK_{plan.upper()}",
        f"RAZORPAY_LINK_{plan.upper()}",
        f"RAZORPAY_{plan.upper()}_LINK",
        f"STRIPE_LINK_{plan.upper()}",
    ])
    for key in candidate_keys:
        value = get_secret_value(key)
        if value:
            return str(value)
    return ""


def render_plan_card(plan_key: str, current_plan: str) -> None:
    plan_key = normalize_plan(plan_key)
    current_plan = normalize_plan(current_plan)
    info = PLAN_CATALOG[plan_key]
    is_current = plan_key == current_plan

    st.markdown(f"### {info['name']}")
    st.metric("Price", info["price"])
    st.caption(info["tagline"])
    st.write(f"**Monthly credits:** {info['credits']}")
    for feature in info["features"]:
        st.write(f"- {feature}")

    if is_current:
        st.success("Current plan")
    elif plan_key != "trial":
        link = get_payment_link(plan_key)
        if link:
            st.link_button(f"Upgrade to {info['name']}", link, use_container_width=True)
        else:
            st.info(f"Add {info['secret_key']} in Streamlit Secrets to enable this upgrade button.")
    else:
        st.caption("Trial is created automatically after signup.")


def supabase_configured() -> bool:
    return bool(get_secret_value("SUPABASE_URL") and get_secret_value("SUPABASE_ANON_KEY"))


def supabase_service_configured() -> bool:
    return bool(get_secret_value("SUPABASE_URL") and get_secret_value("SUPABASE_SERVICE_ROLE_KEY"))


def supabase_url(path: str) -> str:
    base = (get_secret_value("SUPABASE_URL") or "").rstrip("/")
    return f"{base}{path}"


def supabase_headers(kind: str = "anon", access_token: Optional[str] = None) -> Dict[str, str]:
    if kind == "service":
        key = get_secret_value("SUPABASE_SERVICE_ROLE_KEY")
    else:
        key = get_secret_value("SUPABASE_ANON_KEY")

    headers = {
        "apikey": key or "",
        "Authorization": f"Bearer {access_token or key or ''}",
        "Content-Type": "application/json",
    }
    return headers


def supabase_post(path: str, payload: Dict[str, Any], kind: str = "anon", access_token: Optional[str] = None) -> Tuple[bool, Any]:
    try:
        res = requests.post(
            supabase_url(path),
            headers=supabase_headers(kind=kind, access_token=access_token),
            json=payload,
            timeout=SUPABASE_TIMEOUT,
        )
        if res.status_code >= 400:
            try:
                return False, res.json()
            except Exception:
                return False, res.text
        try:
            return True, res.json()
        except Exception:
            return True, {}
    except Exception as exc:
        return False, str(exc)


def supabase_get(path: str, kind: str = "anon", access_token: Optional[str] = None) -> Tuple[bool, Any]:
    try:
        res = requests.get(
            supabase_url(path),
            headers=supabase_headers(kind=kind, access_token=access_token),
            timeout=SUPABASE_TIMEOUT,
        )
        if res.status_code >= 400:
            try:
                return False, res.json()
            except Exception:
                return False, res.text
        try:
            return True, res.json()
        except Exception:
            return True, {}
    except Exception as exc:
        return False, str(exc)


def supabase_patch(path: str, payload: Dict[str, Any], kind: str = "service", access_token: Optional[str] = None) -> Tuple[bool, Any]:
    try:
        res = requests.patch(
            supabase_url(path),
            headers={**supabase_headers(kind=kind, access_token=access_token), "Prefer": "return=representation"},
            json=payload,
            timeout=SUPABASE_TIMEOUT,
        )
        if res.status_code >= 400:
            try:
                return False, res.json()
            except Exception:
                return False, res.text
        try:
            return True, res.json()
        except Exception:
            return True, {}
    except Exception as exc:
        return False, str(exc)



def supabase_delete(path: str, kind: str = "service", access_token: Optional[str] = None) -> Tuple[bool, Any]:
    try:
        res = requests.delete(
            supabase_url(path),
            headers=supabase_headers(kind=kind, access_token=access_token),
            timeout=SUPABASE_TIMEOUT,
        )
        if res.status_code >= 400:
            try:
                return False, res.json()
            except Exception:
                return False, res.text
        try:
            return True, res.json()
        except Exception:
            return True, {}
    except Exception as exc:
        return False, str(exc)

def auth_sign_up(email: str, password: str, full_name: str = "") -> Tuple[bool, str, Dict[str, Any]]:
    payload = {
        "email": email.strip().lower(),
        "password": password,
        "data": {"full_name": full_name.strip() or email.strip().split("@")[0]},
    }
    ok, data = supabase_post("/auth/v1/signup", payload, kind="anon")
    if not ok:
        return False, format_supabase_error(data), {}
    return True, "Account created. If email confirmation is enabled, please confirm your email before signing in.", data or {}


def auth_sign_in(email: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
    payload = {"email": email.strip().lower(), "password": password}
    ok, data = supabase_post("/auth/v1/token?grant_type=password", payload, kind="anon")
    if not ok:
        return False, format_supabase_error(data), {}
    if not data.get("access_token"):
        return False, "Login failed. Please check email confirmation and password.", {}
    return True, "Login successful.", data


def auth_send_password_reset(email: str) -> Tuple[bool, str]:
    ok, data = supabase_post("/auth/v1/recover", {"email": email.strip().lower()}, kind="anon")
    if not ok:
        return False, format_supabase_error(data)
    return True, "Password reset email sent if the account exists."


def format_supabase_error(data: Any) -> str:
    if isinstance(data, dict):
        for key in ["msg", "message", "error_description", "error"]:
            if data.get(key):
                return str(data.get(key))
        return json.dumps(data)[:500]
    return str(data)[:500]


def set_session_from_auth(data: Dict[str, Any]) -> None:
    user = data.get("user") or {}
    st.session_state["errorsweep_authenticated"] = True
    st.session_state["sb_access_token"] = data.get("access_token")
    st.session_state["sb_refresh_token"] = data.get("refresh_token")
    st.session_state["sb_user"] = user
    st.session_state["errorsweep_username"] = user.get("email", "user")


def get_current_user() -> Dict[str, Any]:
    return st.session_state.get("sb_user") or {}


def ensure_profile(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    user_id = user.get("id")
    email = user.get("email")
    if not user_id or not supabase_service_configured():
        return None

    profile = get_profile(user_id)
    if profile:
        return profile

    payload = {
        "id": user_id,
        "email": email,
        "full_name": (user.get("user_metadata") or {}).get("full_name") or email,
        "plan": "trial",
        "monthly_credits": DEFAULT_TRIAL_CREDITS,
        "used_credits": 0,
        "total_files_processed": 0,
    }
    ok, data = supabase_post("/rest/v1/profiles", payload, kind="service")
    if not ok:
        return None
    return get_profile(user_id)


def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    if not user_id or not supabase_service_configured():
        return None
    ok, data = supabase_get(f"/rest/v1/profiles?id=eq.{user_id}&select=*", kind="service")
    if ok and isinstance(data, list) and data:
        return data[0]
    return None


def remaining_credits(profile: Optional[Dict[str, Any]]) -> int:
    if not profile:
        return 0
    try:
        return max(0, int(profile.get("monthly_credits") or 0) - int(profile.get("used_credits") or 0))
    except Exception:
        return 0


def calculate_credit_cost(workflow: str, segment_count: int, rules_zip_used: bool = False, independent_review: bool = False) -> int:
    """Transparent MVP credit model.
    QA: 1 credit / 100 segments.
    Pro: 3 credits / 75 segments + optional independent review credit.
    Rules ZIP adds 1 credit because it increases context processing.
    """
    segment_count = max(1, int(segment_count or 1))
    if workflow == "qa":
        credits = max(1, math.ceil(segment_count / 100))
    else:
        credits = max(3, math.ceil(segment_count / 75) * 3)
        if independent_review:
            credits += max(1, math.ceil(segment_count / 150))
    if rules_zip_used:
        credits += 1
    return int(credits)


def credit_preflight(profile: Optional[Dict[str, Any]], credits_needed: int) -> Tuple[bool, str]:
    if not supabase_service_configured():
        return False, "Supabase service role is not configured. Add SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets."
    if not profile:
        return False, "User profile not found. Please log out and log in again."
    if remaining_credits(profile) < credits_needed:
        return False, f"Not enough credits. Required: {credits_needed}, remaining: {remaining_credits(profile)}."
    return True, "OK"


def consume_user_credits(user_id: str, credits: int, workflow: str, file_name: str, segment_count: int, metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not user_id:
        return False, "Missing user id.", None
    if credits <= 0:
        return True, "No credits charged.", get_profile(user_id)
    if not supabase_service_configured():
        return False, "Supabase service role is not configured.", None

    payload = {
        "p_user_id": user_id,
        "p_credits": int(credits),
        "p_workflow": workflow,
        "p_file_name": file_name,
        "p_segments": int(segment_count or 0),
        "p_metadata": metadata or {},
    }
    ok, data = supabase_post("/rest/v1/rpc/consume_user_credits", payload, kind="service")
    if ok:
        refreshed = get_profile(user_id)
        return True, "Credits charged successfully.", refreshed

    # Friendly fallback message. Do not silently bypass payment/credits.
    return False, "Credit deduction failed. Make sure the Supabase SQL setup was executed. Details: " + format_supabase_error(data), get_profile(user_id)


def log_report_record(user_id: str, workflow: str, file_name: str, segment_count: int, issue_count: int, output_name: str, credits_charged: int) -> None:
    if not user_id or not supabase_service_configured():
        return
    payload = {
        "user_id": user_id,
        "workflow": workflow,
        "file_name": file_name,
        "segments": int(segment_count or 0),
        "issues": int(issue_count or 0),
        "output_name": output_name,
        "credits_charged": int(credits_charged or 0),
    }
    supabase_post("/rest/v1/file_jobs", payload, kind="service")


def get_recent_jobs(user_id: str, limit: int = 8) -> List[Dict[str, Any]]:
    if not user_id or not supabase_service_configured():
        return []
    ok, data = supabase_get(
        f"/rest/v1/file_jobs?user_id=eq.{user_id}&select=*&order=created_at.desc&limit={int(limit)}",
        kind="service",
    )
    if ok and isinstance(data, list):
        return data
    return []



# ==========================================================
# ADMIN USER MANAGEMENT
# ==========================================================


def get_admin_emails() -> List[str]:
    raw = get_secret_value("ERRORSWEEP_ADMIN_EMAILS", "") or ""
    return [email.strip().lower() for email in raw.split(",") if email.strip()]


def is_admin_user() -> bool:
    user = get_current_user()
    email = (user.get("email") or st.session_state.get("errorsweep_username", "")).strip().lower()
    return bool(email and email in get_admin_emails())


def admin_list_profiles(search: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    if not supabase_service_configured():
        return []
    if search.strip():
        pattern = quote(f"*{search.strip()}*", safe="")
        query = f"/rest/v1/profiles?select=*&email=ilike.{pattern}&order=created_at.desc&limit={int(limit)}"
    else:
        query = f"/rest/v1/profiles?select=*&order=created_at.desc&limit={int(limit)}"
    ok, data = supabase_get(query, kind="service")
    if ok and isinstance(data, list):
        return data
    return []


def admin_get_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
    if not email.strip() or not supabase_service_configured():
        return None
    email_q = quote(email.strip().lower(), safe="")
    ok, data = supabase_get(f"/rest/v1/profiles?email=eq.{email_q}&select=*&limit=1", kind="service")
    if ok and isinstance(data, list) and data:
        return data[0]
    return None


def admin_update_profile(user_id: str, updates: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not user_id:
        return False, "Missing user id.", None
    allowed = {"plan", "monthly_credits", "used_credits", "full_name"}
    safe_updates = {k: v for k, v in updates.items() if k in allowed}
    if not safe_updates:
        return False, "No valid fields to update.", None
    ok, data = supabase_patch(f"/rest/v1/profiles?id=eq.{user_id}", safe_updates, kind="service")
    if not ok:
        return False, format_supabase_error(data), None
    return True, "Profile updated successfully.", get_profile(user_id)


def admin_list_jobs(user_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    if not supabase_service_configured():
        return []
    if user_id:
        query = f"/rest/v1/file_jobs?user_id=eq.{user_id}&select=*&order=created_at.desc&limit={int(limit)}"
    else:
        query = f"/rest/v1/file_jobs?select=*&order=created_at.desc&limit={int(limit)}"
    ok, data = supabase_get(query, kind="service")
    if ok and isinstance(data, list):
        return data
    return []


def admin_usage_summary() -> Dict[str, Any]:
    profiles = admin_list_profiles(limit=500)
    jobs = admin_list_jobs(limit=500)
    return {
        "users": len(profiles),
        "jobs": len(jobs),
        "credits_used": sum(int(p.get("used_credits") or 0) for p in profiles),
        "credits_allocated": sum(int(p.get("monthly_credits") or 0) for p in profiles),
    }


# ==========================================================
# SECURE TRANSLATION MEMORY
# ==========================================================

def tm_secret_configured() -> bool:
    """Translation Memory requires a private encryption secret."""
    return bool(get_secret_value("ERRORSWEEP_TM_SECRET")) and Fernet is not None and supabase_service_configured()


def tm_fernet() -> Optional[Any]:
    """Build a Fernet instance from ERRORSWEEP_TM_SECRET.

    The secret can be a Fernet key or any long secret phrase. We derive a stable
    Fernet key from it so the database never stores readable source/target text.
    """
    if Fernet is None:
        return None
    secret = get_secret_value("ERRORSWEEP_TM_SECRET")
    if not secret:
        return None
    try:
        raw = secret.encode("utf-8")
        # If the user provided a valid Fernet key, use it directly.
        if len(raw) == 44:
            return Fernet(raw)
        digest = hashlib.sha256(raw).digest()
        return Fernet(base64.urlsafe_b64encode(digest))
    except Exception:
        return None


def tm_client_key(client_name: str) -> str:
    cleaned = normalize_text(client_name or "global").lower()
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", cleaned).strip("-")
    return cleaned or "global"


def tm_normalize_for_hash(text: Any) -> str:
    cleaned = normalize_text(text)
    cleaned = cleaned.replace("\u00A0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def tm_hash_source(source_text: str) -> str:
    return hashlib.sha256(tm_normalize_for_hash(source_text).encode("utf-8")).hexdigest()


def tm_encrypt_text(text: Any) -> Optional[str]:
    f = tm_fernet()
    if f is None:
        return None
    return f.encrypt(str(text or "").encode("utf-8")).decode("utf-8")


def tm_decrypt_text(token: Any) -> str:
    f = tm_fernet()
    if f is None or not token:
        return ""
    try:
        return f.decrypt(str(token).encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def tm_target_lang_key(target_language: str) -> str:
    value = normalize_text(target_language or "auto-detect")
    return value if value else "auto-detect"


def render_translation_memory_controls(context: str, default_target_language: str = "") -> Dict[str, Any]:
    """Workflow-level TM controls. This is opt-in because client privacy matters."""
    prefix = "qa" if context == "qa" else "pro"
    title = "Secure Translation Memory"
    with st.expander(title, expanded=False):
        st.markdown(
            """
            Use private encrypted translation memory to improve future files with exact matches.
            Saved translations are encrypted before storage and separated by user/client scope.
            """
        )
        c1, c2 = st.columns(2)
        with c1:
            use_tm = st.checkbox("Use saved memory matches", value=True, key=f"{prefix}_tm_use")
        with c2:
            save_tm = st.checkbox("Save approved translations after this run", value=False, key=f"{prefix}_tm_save")
        c3, c4 = st.columns(2)
        with c3:
            client_name = st.text_input("Client / project memory name", value="", placeholder="Example: Acme French Legal / Global UI", key=f"{prefix}_tm_client")
        with c4:
            target_language = st.text_input(
                "Target language / locale for memory",
                value=default_target_language or st.session_state.get("es_target_language", ""),
                placeholder="Required for no-API QA: Spanish, French, Hindi, Arabic, ja-JP",
                key=f"{prefix}_tm_target_language",
            )
        if not tm_secret_configured():
            st.warning("Translation Memory is not active. Add ERRORSWEEP_TM_SECRET in Streamlit Secrets and run the TM SQL setup.")
        else:
            st.success("Encrypted Translation Memory is active.")
        st.caption("Privacy note: exact source/target text is encrypted. Matching uses a one-way hash of normalized source text.")
    return {
        "use": bool(use_tm),
        "save": bool(save_tm),
        "client_key": tm_client_key(client_name),
        "client_name": normalize_text(client_name) or "Global",
        "target_language": tm_target_lang_key(target_language),
    }


def tm_batch_lookup(user_id: str, segments: List[Dict[str, Any]], target_language: str, client_key: str, max_records: int = 500) -> Dict[str, Dict[str, Any]]:
    """Return exact TM matches by segment location."""
    if not tm_secret_configured() or not user_id or not segments:
        return {}

    target_language = tm_target_lang_key(target_language)
    client_key = tm_client_key(client_key)
    hash_to_locs: Dict[str, List[str]] = {}
    for seg in segments:
        source = seg.get("source") or seg.get("text") or ""
        if not normalize_text(source):
            continue
        h = tm_hash_source(source)
        hash_to_locs.setdefault(h, []).append(seg.get("location", ""))

    if not hash_to_locs:
        return {}

    all_hashes = list(hash_to_locs.keys())[:max_records]
    found_by_hash: Dict[str, Dict[str, Any]] = {}
    batch_size = 80
    for start in range(0, len(all_hashes), batch_size):
        batch_hashes = all_hashes[start:start + batch_size]
        hash_list = ",".join(batch_hashes)
        query = (
            f"/rest/v1/translation_memory"
            f"?user_id=eq.{user_id}"
            f"&client_key=eq.{quote(client_key)}"
            f"&target_language=eq.{quote(target_language)}"
            f"&source_hash=in.({hash_list})"
            f"&select=id,source_hash,target_text_encrypted,status,use_count"
            f"&limit={len(batch_hashes)}"
        )
        ok, data = supabase_get(query, kind="service")
        if ok and isinstance(data, list):
            for row in data:
                found_by_hash[row.get("source_hash", "")] = row

    loc_matches: Dict[str, Dict[str, Any]] = {}
    for h, row in found_by_hash.items():
        target_text = tm_decrypt_text(row.get("target_text_encrypted"))
        if not target_text:
            continue
        for loc in hash_to_locs.get(h, []):
            if loc:
                loc_matches[loc] = {
                    "translation": target_text,
                    "memory_id": row.get("id"),
                    "status": row.get("status", "approved"),
                }
    return loc_matches


def tm_qa_memory_report_rows(user_id: str, segments: List[Dict[str, Any]], target_language: str, client_key: str) -> List[Dict[str, Any]]:
    matches = tm_batch_lookup(user_id, segments, target_language, client_key)
    rows: List[Dict[str, Any]] = []
    if not matches:
        return rows
    for seg in segments:
        loc = seg.get("location", "")
        match = matches.get(loc)
        if not match:
            continue
        saved_target = normalize_text(match.get("translation", ""))
        current_target = normalize_text(seg.get("translation") or seg.get("text") or "")
        if saved_target and current_target and tm_normalize_for_hash(saved_target) != tm_normalize_for_hash(current_target):
            rows.append(make_report_row(
                seg,
                "Translation Memory",
                "Major",
                current_target,
                saved_target,
                "A previously saved approved translation exists for the same source segment.",
                "Secure Translation Memory",
                f"Client memory: {client_key}",
                "High",
            ))
    return rows


def tm_upsert_translation(
    user_id: str,
    source_text: str,
    target_text: str,
    target_language: str,
    client_key: str,
    domain: str = "",
    status: str = "approved",
    source_language: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    if not tm_secret_configured() or not user_id:
        return False
    source_norm = tm_normalize_for_hash(source_text)
    target_norm = normalize_text(target_text)
    if not source_norm or not target_norm:
        return False

    source_encrypted = tm_encrypt_text(source_text)
    target_encrypted = tm_encrypt_text(target_text)
    if not source_encrypted or not target_encrypted:
        return False

    payload = {
        "user_id": user_id,
        "client_key": tm_client_key(client_key),
        "source_language": normalize_text(source_language or ""),
        "target_language": tm_target_lang_key(target_language),
        "domain": normalize_text(domain or ""),
        "source_hash": tm_hash_source(source_text),
        "source_text_encrypted": source_encrypted,
        "target_text_encrypted": target_encrypted,
        "status": status,
        "metadata": metadata or {},
        "use_count": 0,
    }
    # upsert by unique constraint
    try:
        res = requests.post(
            supabase_url("/rest/v1/translation_memory?on_conflict=user_id,client_key,target_language,source_hash"),
            headers={**supabase_headers(kind="service"), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=payload,
            timeout=SUPABASE_TIMEOUT,
        )
        return res.status_code < 400
    except Exception:
        return False


def tm_save_passed_qa_segments(
    user_id: str,
    segments: List[Dict[str, Any]],
    issue_rows: List[Dict[str, Any]],
    target_language: str,
    client_key: str,
    domain: str = "",
) -> int:
    issue_locs = {str(r.get("Location", "")) for r in issue_rows if r.get("Location")}
    saved = 0
    for seg in segments:
        loc = str(seg.get("location", ""))
        if loc in issue_locs:
            continue
        source = seg.get("source", "")
        target = seg.get("translation") or seg.get("text", "")
        if source and target and tm_upsert_translation(
            user_id,
            source,
            target,
            target_language,
            client_key,
            domain=domain,
            status="approved_existing",
            metadata={"saved_from": "qa_pass", "location": loc},
        ):
            saved += 1
    return saved


def tm_save_pro_translations(
    user_id: str,
    translated_segments: List[Dict[str, Any]],
    review_rows: List[Dict[str, Any]],
    target_language: str,
    client_key: str,
    domain: str = "",
) -> int:
    issue_locs = {str(r.get("Location", "")) for r in review_rows if r.get("Location")}
    saved = 0
    for seg in translated_segments:
        loc = str(seg.get("location", ""))
        if loc in issue_locs:
            continue
        source = seg.get("source") or ""
        target = seg.get("translation") or seg.get("text") or ""
        if source and target and tm_upsert_translation(
            user_id,
            source,
            target,
            target_language,
            client_key,
            domain=domain,
            status="reviewed_or_passed",
            metadata={"saved_from": "pro_translation", "location": loc},
        ):
            saved += 1
    return saved


# ==========================================================
# MEMORY & RULE PACK MANAGER
# ==========================================================

def get_user_rule_packs(user_id: str, workflow_type: str = "") -> List[Dict[str, Any]]:
    if not user_id or not supabase_service_configured():
        return []
    query = f"/rest/v1/rule_packs?user_id=eq.{user_id}&select=*&order=created_at.desc&limit=500"
    if workflow_type:
        query = f"/rest/v1/rule_packs?user_id=eq.{user_id}&or=(workflow_type.eq.{quote(workflow_type)},workflow_type.eq.both)&select=*&order=created_at.desc&limit=500"
    ok, data = supabase_get(query, kind="service")
    if ok and isinstance(data, list):
        return data
    return []


def get_rule_pack_by_id(user_id: str, pack_id: str) -> Optional[Dict[str, Any]]:
    if not user_id or not pack_id or not supabase_service_configured():
        return None
    ok, data = supabase_get(
        f"/rest/v1/rule_packs?id=eq.{pack_id}&user_id=eq.{user_id}&select=*&limit=1",
        kind="service",
    )
    if ok and isinstance(data, list) and data:
        return data[0]
    return None


def create_rule_pack(
    user_id: str,
    name: str,
    client_name: str,
    workflow_type: str,
    source_language: str,
    target_language: str,
    domain: str,
    zip_file_name: str,
    parsed_rules: Dict[str, Any],
) -> Tuple[bool, str]:
    if not user_id or not supabase_service_configured():
        return False, "Supabase service role is not configured."
    payload = {
        "user_id": user_id,
        "name": normalize_text(name) or "Untitled Rule Pack",
        "client_name": normalize_text(client_name) or "General",
        "workflow_type": workflow_type or "both",
        "source_language": normalize_text(source_language),
        "target_language": normalize_text(target_language),
        "domain": normalize_text(domain),
        "zip_file_name": zip_file_name,
        "parsed_rules_json": parsed_rules or {},
        "glossary_count": len((parsed_rules or {}).get("glossary", [])),
        "dnt_count": len((parsed_rules or {}).get("dnt", [])),
        "chunk_count": len((parsed_rules or {}).get("chunks", [])),
    }
    ok, data = supabase_post("/rest/v1/rule_packs", payload, kind="service")
    if ok:
        return True, "Rule pack saved."
    return False, format_supabase_error(data)


def delete_rule_pack(user_id: str, pack_id: str) -> Tuple[bool, str]:
    if not user_id or not pack_id:
        return False, "Missing user or rule pack id."
    ok, data = supabase_delete(f"/rest/v1/rule_packs?id=eq.{pack_id}&user_id=eq.{user_id}", kind="service")
    if ok:
        return True, "Rule pack deleted."
    return False, format_supabase_error(data)


def touch_rule_pack(pack_id: str) -> None:
    if not pack_id or not supabase_service_configured():
        return
    supabase_patch(
        f"/rest/v1/rule_packs?id=eq.{pack_id}",
        {"last_used_at": datetime.now(timezone.utc).isoformat()},
        kind="service",
    )


def merge_rules(base_rules: Dict[str, Any], extra_rules: Dict[str, Any]) -> Dict[str, Any]:
    merged = {"chunks": [], "glossary": [], "dnt": [], "files": [], "warnings": []}
    for source in [base_rules or {}, extra_rules or {}]:
        for key in merged.keys():
            val = source.get(key, [])
            if isinstance(val, list):
                merged[key].extend(val)
    return merged


def render_rule_pack_selector(user_id: str, workflow_type: str, prefix: str) -> Tuple[Dict[str, Any], Optional[str]]:
    rules = {"chunks": [], "glossary": [], "dnt": [], "files": [], "warnings": []}
    selected_id = None
    packs = get_user_rule_packs(user_id, workflow_type)
    if not packs:
        st.caption("No saved rule packs yet. Upload a ZIP below and save it for reuse.")
        return rules, selected_id
    options = {f"{p.get('name','Untitled')} · {p.get('client_name','General')} · {p.get('target_language') or 'Any'}": p.get("id") for p in packs}
    selected_label = st.selectbox(
        "Use saved rule pack (optional)",
        ["None"] + list(options.keys()),
        key=f"{prefix}_saved_rule_pack_select",
    )
    if selected_label != "None":
        selected_id = options[selected_label]
        pack = get_rule_pack_by_id(user_id, selected_id)
        if pack:
            rules = pack.get("parsed_rules_json") or rules
            st.success(
                f"Loaded saved rule pack: {pack.get('name')} · glossary {len(rules.get('glossary', []))}, DNT {len(rules.get('dnt', []))}, rule chunks {len(rules.get('chunks', []))}."
            )
            touch_rule_pack(selected_id)
    return rules, selected_id


def render_rule_pack_save_box(user_id: str, prefix: str, workflow_type: str, parsed_rules: Dict[str, Any], zip_name: str, default_domain: str = "") -> None:
    if not parsed_rules or not zip_name:
        return
    with st.expander("Save this ZIP as reusable rule pack", expanded=False):
        st.caption("Save client style guides, glossary, DNT lists, and instructions once, then reuse them in future jobs.")
        c1, c2 = st.columns(2)
        with c1:
            pack_name = st.text_input("Rule pack name", value=zip_name.rsplit('.', 1)[0], key=f"{prefix}_save_pack_name")
            client_name = st.text_input("Client / project name", value="General", key=f"{prefix}_save_pack_client")
        with c2:
            source_language = st.text_input("Source language", value="", key=f"{prefix}_save_pack_src")
            target_language = st.text_input("Target language / locale", value=st.session_state.get("es_target_language", ""), key=f"{prefix}_save_pack_tgt")
        wf = st.selectbox("Workflow type", [workflow_type, "both", "qa", "pro"], key=f"{prefix}_save_pack_workflow")
        if st.button("Save Rule Pack", key=f"{prefix}_save_pack_button", use_container_width=True):
            ok, msg = create_rule_pack(
                user_id=user_id,
                name=pack_name,
                client_name=client_name,
                workflow_type=wf,
                source_language=source_language,
                target_language=target_language,
                domain=default_domain,
                zip_file_name=zip_name,
                parsed_rules=parsed_rules,
            )
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()


def get_translation_memory_records(user_id: str, limit: int = 5000) -> List[Dict[str, Any]]:
    if not user_id or not supabase_service_configured():
        return []
    ok, data = supabase_get(
        f"/rest/v1/translation_memory?user_id=eq.{user_id}&select=*&order=created_at.desc&limit={int(limit)}",
        kind="service",
    )
    if ok and isinstance(data, list):
        return data
    return []


def summarize_translation_memory(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["Client Memory", "Target Language", "Domain", "Entries", "Statuses", "Created", "Last Used"])
    summary: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in records:
        key = (r.get("client_key") or "global", r.get("target_language") or "auto-detect", r.get("domain") or "")
        item = summary.setdefault(key, {"Client Memory": key[0], "Target Language": key[1], "Domain": key[2], "Entries": 0, "Statuses": set(), "Created": r.get("created_at"), "Last Used": r.get("last_used_at")})
        item["Entries"] += 1
        if r.get("status"):
            item["Statuses"].add(r.get("status"))
        if r.get("created_at") and (not item.get("Created") or str(r.get("created_at")) < str(item.get("Created"))):
            item["Created"] = r.get("created_at")
        if r.get("last_used_at") and (not item.get("Last Used") or str(r.get("last_used_at")) > str(item.get("Last Used"))):
            item["Last Used"] = r.get("last_used_at")
    rows = []
    for item in summary.values():
        rows.append({**item, "Statuses": ", ".join(sorted(item["Statuses"]))})
    return pd.DataFrame(rows).sort_values(["Client Memory", "Target Language"]) if rows else pd.DataFrame()


def export_translation_memory_csv(records: List[Dict[str, Any]]) -> bytes:
    rows = []
    for r in records:
        rows.append({
            "client_key": r.get("client_key", ""),
            "source_language": r.get("source_language", ""),
            "target_language": r.get("target_language", ""),
            "domain": r.get("domain", ""),
            "source_text": tm_decrypt_text(r.get("source_text_encrypted")),
            "target_text": tm_decrypt_text(r.get("target_text_encrypted")),
            "status": r.get("status", ""),
            "created_at": r.get("created_at", ""),
            "last_used_at": r.get("last_used_at", ""),
        })
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def delete_translation_memory_scope(user_id: str, client_key: str, target_language: str = "") -> Tuple[bool, str]:
    if not user_id or not client_key:
        return False, "Missing user or memory name."
    path = f"/rest/v1/translation_memory?user_id=eq.{user_id}&client_key=eq.{quote(client_key)}"
    if target_language:
        path += f"&target_language=eq.{quote(target_language)}"
    ok, data = supabase_delete(path, kind="service")
    if ok:
        return True, "Translation memory deleted for the selected scope."
    return False, format_supabase_error(data)



# ==========================================================
# CORRECTION HISTORY / HUMAN FEEDBACK LEARNING
# ==========================================================

def correction_history_configured() -> bool:
    return supabase_service_configured()


def normalize_correction_col(name: Any) -> str:
    value = normalize_text(name).lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def parse_correction_history_upload(uploaded_file) -> List[Dict[str, Any]]:
    """Parse human correction history from CSV/XLSX.

    Supported columns:
    source/source_text, bad_translation/wrong/current_translation,
    fixed_translation/correct/suggestion/preferred_translation,
    error_type/category, severity, target_language, client, domain, notes.
    """
    if uploaded_file is None:
        return []

    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)

    col_map = {normalize_correction_col(c): c for c in df.columns}

    def find_col(*names: str) -> Optional[str]:
        for n in names:
            key = normalize_correction_col(n)
            if key in col_map:
                return col_map[key]
        for key, original in col_map.items():
            if any(normalize_correction_col(n) in key for n in names):
                return original
        return None

    source_col = find_col("source", "source_text", "source segment", "source string")
    bad_col = find_col("bad_translation", "wrong", "wrong_translation", "current_translation", "translation", "issue", "wrong_part")
    fixed_col = find_col("fixed_translation", "correct", "correct_translation", "suggestion", "preferred_translation", "approved_translation", "target")
    type_col = find_col("error_type", "category", "error category", "issue_type")
    sev_col = find_col("severity", "error severity")
    lang_col = find_col("target_language", "language", "locale", "target locale")
    client_col = find_col("client", "client_name", "project", "project_name", "memory", "client_key")
    domain_col = find_col("domain", "content_domain")
    notes_col = find_col("notes", "comment", "reviewer_comment", "explanation")

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        source = normalize_text(row[source_col]) if source_col and pd.notna(row.get(source_col)) else ""
        bad = normalize_text(row[bad_col]) if bad_col and pd.notna(row.get(bad_col)) else ""
        fixed = normalize_text(row[fixed_col]) if fixed_col and pd.notna(row.get(fixed_col)) else ""
        if not fixed:
            continue
        if not bad and not source:
            continue
        error_type = normalize_text(row[type_col]) if type_col and pd.notna(row.get(type_col)) else "Client Correction"
        severity = normalize_text(row[sev_col]) if sev_col and pd.notna(row.get(sev_col)) else "Major"
        if severity not in {"Critical", "Major", "Minor", "Review"}:
            severity = "Major"
        target_language = normalize_text(row[lang_col]) if lang_col and pd.notna(row.get(lang_col)) else "auto-detect"
        client_name = normalize_text(row[client_col]) if client_col and pd.notna(row.get(client_col)) else "Global"
        domain = normalize_text(row[domain_col]) if domain_col and pd.notna(row.get(domain_col)) else ""
        notes = normalize_text(row[notes_col]) if notes_col and pd.notna(row.get(notes_col)) else ""
        records.append({
            "source_text": source,
            "bad_translation": bad,
            "fixed_translation": fixed,
            "error_type": error_type,
            "severity": severity,
            "target_language": target_language,
            "client_name": client_name,
            "client_key": tm_client_key(client_name),
            "domain": domain,
            "notes": notes,
        })
    return records[:5000]


def save_correction_history_records(user_id: str, records: List[Dict[str, Any]]) -> Tuple[bool, str, int]:
    if not user_id:
        return False, "Missing user id.", 0
    if not correction_history_configured():
        return False, "Supabase service role is not configured.", 0
    if not records:
        return False, "No valid correction rows found.", 0

    payload = []
    for r in records:
        payload.append({
            "user_id": user_id,
            "client_key": tm_client_key(r.get("client_key") or r.get("client_name") or "global"),
            "client_name": r.get("client_name") or "Global",
            "source_language": r.get("source_language", ""),
            "target_language": tm_target_lang_key(r.get("target_language") or "auto-detect"),
            "domain": r.get("domain", ""),
            "source_text": r.get("source_text", ""),
            "bad_translation": r.get("bad_translation", ""),
            "fixed_translation": r.get("fixed_translation", ""),
            "error_type": r.get("error_type", "Client Correction"),
            "severity": r.get("severity", "Major"),
            "status": "approved",
            "notes": r.get("notes", ""),
            "metadata": r.get("metadata", {}),
        })

    saved = 0
    batch_size = 200
    for start in range(0, len(payload), batch_size):
        batch = payload[start:start + batch_size]
        ok, data = supabase_post("/rest/v1/correction_history", batch, kind="service")
        if not ok:
            return False, format_supabase_error(data), saved
        saved += len(batch)
    return True, f"Saved {saved} correction history row(s).", saved


def get_correction_history_records(user_id: str, client_key: str = "", target_language: str = "", limit: int = 1000) -> List[Dict[str, Any]]:
    if not user_id or not correction_history_configured():
        return []
    query = f"/rest/v1/correction_history?user_id=eq.{user_id}&select=*&order=created_at.desc&limit={int(limit)}"
    if client_key:
        query += f"&client_key=eq.{quote(tm_client_key(client_key))}"
    if target_language:
        query += f"&target_language=eq.{quote(tm_target_lang_key(target_language))}"
    ok, data = supabase_get(query, kind="service")
    if ok and isinstance(data, list):
        return data
    return []


def load_correction_history_as_rules(user_id: str, client_key: str = "", target_language: str = "", domain: str = "") -> List[Dict[str, str]]:
    records = get_correction_history_records(user_id, client_key=client_key, target_language=target_language, limit=2000)
    corrections: List[Dict[str, str]] = []
    for r in records:
        bad = normalize_text(r.get("bad_translation", ""))
        fixed = normalize_text(r.get("fixed_translation", ""))
        if not bad or not fixed or bad == fixed:
            continue
        corrections.append({
            "wrong": bad,
            "correct": fixed,
            "error_type": r.get("error_type", "Client Correction"),
            "category": r.get("error_type", "Client Correction"),
            "severity": r.get("severity", "Major"),
            "source": f"Correction History · {r.get('client_name') or r.get('client_key') or 'Global'}",
        })
    return corrections[:2000]


def export_correction_history_csv(records: List[Dict[str, Any]]) -> bytes:
    cols = [
        "client_name", "client_key", "source_language", "target_language", "domain",
        "source_text", "bad_translation", "fixed_translation", "error_type",
        "severity", "status", "notes", "created_at"
    ]
    rows = [{c: r.get(c, "") for c in cols} for r in records]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def delete_correction_history_scope(user_id: str, client_key: str, target_language: str = "") -> Tuple[bool, str]:
    if not user_id or not client_key:
        return False, "Missing user or client scope."
    path = f"/rest/v1/correction_history?user_id=eq.{user_id}&client_key=eq.{quote(tm_client_key(client_key))}"
    if target_language:
        path += f"&target_language=eq.{quote(tm_target_lang_key(target_language))}"
    ok, data = supabase_delete(path, kind="service")
    if ok:
        return True, "Correction history deleted for the selected scope."
    return False, format_supabase_error(data)


def render_correction_history_manager(user_id: str) -> None:
    st.markdown("### Human Correction History")
    st.caption("Save approved human corrections so ErrorSweep learns client-specific spelling, grammar, terminology, and style patterns without API keys.")

    records = get_correction_history_records(user_id, limit=1000)
    c1, c2, c3 = st.columns(3)
    c1.metric("Saved corrections", len(records))
    c2.metric("Client scopes", len({r.get("client_key") for r in records}))
    c3.metric("Languages", len({r.get("target_language") for r in records}))

    if records:
        preview_cols = ["client_name", "target_language", "domain", "bad_translation", "fixed_translation", "error_type", "severity", "created_at"]
        st.dataframe(pd.DataFrame([{c: r.get(c, "") for c in preview_cols} for r in records[:300]]), use_container_width=True, hide_index=True)
        st.download_button(
            "Export correction history CSV",
            export_correction_history_csv(records),
            file_name="errorsweep_correction_history_export.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("No correction history saved yet. Upload a correction CSV/XLSX below or save corrections from client QA history.")

    st.markdown("#### Upload correction history")
    st.markdown(
        """
        Accepted columns:
        `source`, `bad_translation` / `wrong`, `fixed_translation` / `correct`,
        `error_type`, `severity`, `target_language`, `client`, `domain`, `notes`.
        """
    )
    correction_file = st.file_uploader("Upload corrections CSV/XLSX", type=["csv", "xlsx", "xlsm"], key="correction_history_upload")
    parsed_records: List[Dict[str, Any]] = []
    if correction_file:
        try:
            parsed_records = parse_correction_history_upload(correction_file)
            st.success(f"Parsed {len(parsed_records)} valid correction row(s).")
            if parsed_records:
                st.dataframe(pd.DataFrame(parsed_records).head(100), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Could not parse correction file: {exc}")

    if parsed_records:
        if st.button("Save parsed corrections", type="primary", use_container_width=True, key="save_correction_history"):
            ok, msg, _ = save_correction_history_records(user_id, parsed_records)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

    if records:
        with st.expander("Delete correction history scope", expanded=False):
            clients = sorted({r.get("client_key") or "global" for r in records})
            client_key = st.selectbox("Client/project scope", clients, key="delete_correction_client")
            langs = [""] + sorted({r.get("target_language") or "auto-detect" for r in records if (r.get("client_key") or "global") == client_key})
            lang = st.selectbox("Target language scope", langs, format_func=lambda x: "All languages" if not x else x, key="delete_correction_lang")
            confirm = st.text_input("Type DELETE to confirm", key="delete_correction_confirm")
            if st.button("Delete selected correction history", key="delete_correction_button", type="primary", use_container_width=True):
                if confirm != "DELETE":
                    st.error("Type DELETE to confirm deletion.")
                else:
                    ok, msg = delete_correction_history_scope(user_id, client_key, lang)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()


def render_memory_rulepacks_page(user_id: str, profile: Optional[Dict[str, Any]]) -> None:
    st.markdown("## Memory & Rule Packs")
    st.caption("Manage encrypted translation memory and reusable client rule packs. This page gives users privacy control over saved language data.")
    tab_memory, tab_rules, tab_corrections, tab_privacy = st.tabs(["Translation Memory", "Saved Rule Packs", "Correction History", "Privacy Controls"])

    with tab_memory:
        st.markdown("### Secure Translation Memory")
        if not tm_secret_configured():
            st.warning("Translation Memory is not active. Add ERRORSWEEP_TM_SECRET in Streamlit Secrets, make sure cryptography is installed, and run the translation memory SQL.")
        records = get_translation_memory_records(user_id)
        c1, c2, c3 = st.columns(3)
        c1.metric("Saved entries", len(records))
        c2.metric("Client memories", len({r.get('client_key') for r in records}))
        c3.metric("Target languages", len({r.get('target_language') for r in records}))
        summary_df = summarize_translation_memory(records)
        if not summary_df.empty:
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            st.download_button("Export decrypted memory CSV", export_translation_memory_csv(records), file_name="errorsweep_translation_memory_export.csv", mime="text/csv", use_container_width=True)
            with st.expander("Delete memory scope", expanded=False):
                clients = sorted({r.get("client_key") or "global" for r in records})
                client_key = st.selectbox("Client memory", clients, key="tm_delete_client")
                langs = [""] + sorted({r.get("target_language") or "auto-detect" for r in records if (r.get("client_key") or "global") == client_key})
                lang = st.selectbox("Target language scope", langs, format_func=lambda x: "All languages" if not x else x, key="tm_delete_lang")
                confirm = st.text_input("Type DELETE to confirm", key="tm_delete_confirm")
                if st.button("Delete selected memory", key="tm_delete_button", type="primary", use_container_width=True):
                    if confirm != "DELETE":
                        st.error("Type DELETE to confirm deletion.")
                    else:
                        ok, msg = delete_translation_memory_scope(user_id, client_key, lang)
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()
        else:
            st.info("No saved translation memory yet. Enable 'Save approved translations' inside ErrorSweep or ErrorSweep Pro to start building client memory.")

    with tab_rules:
        st.markdown("### Saved Rule Packs")
        packs = get_user_rule_packs(user_id)
        if packs:
            rows = []
            for p in packs:
                rows.append({
                    "Name": p.get("name"),
                    "Client": p.get("client_name"),
                    "Workflow": p.get("workflow_type"),
                    "Target": p.get("target_language"),
                    "Domain": p.get("domain"),
                    "Glossary": p.get("glossary_count", 0),
                    "DNT": p.get("dnt_count", 0),
                    "Chunks": p.get("chunk_count", 0),
                    "Created": p.get("created_at"),
                    "Last Used": p.get("last_used_at"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            with st.expander("Delete saved rule pack", expanded=False):
                opts = {f"{p.get('name')} · {p.get('client_name')} · {p.get('workflow_type')}": p.get("id") for p in packs}
                label = st.selectbox("Rule pack", list(opts.keys()), key="delete_rule_pack_select")
                if st.button("Delete rule pack", key="delete_rule_pack_button", use_container_width=True):
                    ok, msg = delete_rule_pack(user_id, opts[label])
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
        else:
            st.info("No saved rule packs yet. Upload a ZIP in ErrorSweep or ErrorSweep Pro, then save it as a reusable pack.")

        st.markdown("### Add rule pack from this page")
        new_zip = st.file_uploader("Upload Rules ZIP", type=["zip"], key="memory_page_rules_zip")
        if new_zip:
            parsed = parse_rules_zip_bytes(new_zip.getvalue())
            st.write(f"Parsed files: {len(parsed.get('files', []))}; glossary: {len(parsed.get('glossary', []))}; DNT: {len(parsed.get('dnt', []))}; chunks: {len(parsed.get('chunks', []))}")
            with st.form("memory_page_save_rule_pack_form"):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Rule pack name", value=new_zip.name.rsplit('.', 1)[0])
                    client_name = st.text_input("Client / project", value="General")
                    workflow_type = st.selectbox("Workflow type", ["both", "qa", "pro"])
                with c2:
                    source_language = st.text_input("Source language", value="")
                    target_language = st.text_input("Target language", value="")
                    domain = st.text_input("Domain", value="")
                submitted = st.form_submit_button("Save Rule Pack", use_container_width=True)
            if submitted:
                ok, msg = create_rule_pack(user_id, name, client_name, workflow_type, source_language, target_language, domain, new_zip.name, parsed)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    with tab_corrections:
        render_correction_history_manager(user_id)

    with tab_privacy:
        st.markdown("### Privacy controls")
        st.markdown("""
        **How storage works**
        - Translation Memory is separated by user, client/project memory name, and target language.
        - Source and target text are encrypted before being stored.
        - Exact matching uses a one-way source hash, so future files can find approved translations without storing readable text in plain form.
        - Saving memory is opt-in from the workflow pages.
        - Correction History stores human-approved corrections for client-specific QA learning.

        **Recommended client policy**
        - Create a separate memory name for each client/project.
        - Do not mix confidential clients in the same memory.
        - Export and delete memory when a client requests it.
        - Keep ERRORSWEEP_TM_SECRET safe; changing it can make old encrypted memory unreadable.
        """)
        st.info("For enterprise clients, add a written privacy statement explaining what is saved, why it is saved, and how they can delete/export it.")

def render_credit_panel(profile: Optional[Dict[str, Any]]) -> None:
    if not profile:
        st.warning("Profile unavailable. Check Supabase setup.")
        return
    plan = str(profile.get("plan") or "trial").title()
    monthly = int(profile.get("monthly_credits") or 0)
    used = int(profile.get("used_credits") or 0)
    remaining = max(0, monthly - used)
    st.markdown("### Account")
    st.caption(profile.get("email", "user"))
    st.metric("Plan", plan)
    st.metric("Credits Remaining", remaining)
    st.progress(min(1.0, used / max(monthly, 1)))
    st.caption(f"{used} / {monthly} credits used this month")


def render_usage_dashboard(user_id: str) -> None:
    profile = get_profile(user_id)
    if not profile:
        return
    plan = str(profile.get("plan") or "trial").title()
    monthly = int(profile.get("monthly_credits") or 0)
    used = int(profile.get("used_credits") or 0)
    remaining = max(0, monthly - used)
    jobs = get_recent_jobs(user_id, limit=8)

    st.markdown("### Usage Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plan", plan)
    c2.metric("Monthly Credits", monthly)
    c3.metric("Used", used)
    c4.metric("Remaining", remaining)

    if jobs:
        with st.expander("Recent jobs", expanded=False):
            st.dataframe(pd.DataFrame(jobs), use_container_width=True, hide_index=True)

# ==========================================================
# LOGIN / SESSION AUTH
# ==========================================================

def is_authenticated() -> bool:
    return bool(st.session_state.get("errorsweep_authenticated") and st.session_state.get("sb_user"))


def logout_user() -> None:
    for key in [
        "errorsweep_authenticated",
        "errorsweep_username",
        "sb_access_token",
        "sb_refresh_token",
        "sb_user",
        "sb_profile",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


def render_login_page() -> None:
    st.markdown(textwrap.dedent(
        """
        <style>
        .login-wrapper {
            max-width: 620px;
            margin: 6vh auto 0 auto;
            background: linear-gradient(135deg, rgba(0,255,136,0.12), rgba(56,189,248,0.08), rgba(139,92,246,0.10));
            border: 1px solid rgba(56,189,248,0.22);
            border-radius: 24px;
            padding: 38px 36px 26px 36px;
            box-shadow: 0 25px 80px rgba(0,0,0,0.35);
            text-align: center;
        }
        .login-title {
            font-family: 'Space Mono', monospace;
            font-size: 40px;
            color: #00ff88;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .login-subtitle {
            color: #a8acc8;
            font-size: 15px;
            margin-bottom: 10px;
        }
        .login-badge {
            display: inline-block;
            background: rgba(0,255,136,0.08);
            border: 1px solid rgba(0,255,136,0.25);
            color: #00ff88;
            border-radius: 999px;
            padding: 6px 16px;
            font-size: 12px;
            margin-top: 8px;
        }
        
.account-hero {
    background: linear-gradient(135deg, rgba(8,14,26,.92), rgba(17,23,43,.92));
    border: 1px solid rgba(56,189,248,.16);
    border-radius: 22px;
    padding: 26px;
    margin: 8px 0 18px 0;
    box-shadow: 0 22px 50px rgba(0,0,0,.26);
}
.account-hero-grid {
    display: grid;
    grid-template-columns: 120px 1.5fr 1fr;
    gap: 20px;
    align-items: center;
}
.account-avatar {
    width: 96px;
    height: 96px;
    border-radius: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Mono', monospace;
    font-size: 34px;
    font-weight: 700;
    color: white;
    background: linear-gradient(135deg, rgba(0,255,136,.9), rgba(56,189,248,.9));
    box-shadow: 0 16px 30px rgba(14,165,233,.22);
}
.account-title {
    font-size: 30px;
    line-height: 1.1;
    font-weight: 800;
    color: #eef2ff;
    margin: 0;
}
.account-subline {
    color: #9fb0d6;
    font-size: 15px;
    margin-top: 8px;
}
.account-badge-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 14px;
}
.account-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-radius: 999px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .15px;
    border: 1px solid rgba(255,255,255,.08);
    background: rgba(255,255,255,.04);
    color: #e8ecfb;
}
.account-pill.plan { background: rgba(0,255,136,.10); color: #8df2c1; border-color: rgba(0,255,136,.20); }
.account-pill.role { background: rgba(56,189,248,.10); color: #8fdcff; border-color: rgba(56,189,248,.20); }
.account-pill.status { background: rgba(250,204,21,.10); color: #fde68a; border-color: rgba(250,204,21,.20); }
.account-pill.security { background: rgba(139,92,246,.10); color: #d8b4fe; border-color: rgba(139,92,246,.20); }
.account-kpi-wrap {
    display: grid;
    grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 12px;
}
.account-kpi {
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 16px;
    padding: 14px;
}
.account-kpi-label { color: #90a3c8; font-size: 12px; text-transform: uppercase; letter-spacing: .8px; }
.account-kpi-value { color: #f8fafc; font-size: 26px; font-weight: 800; margin-top: 4px; }
.account-kpi-sub { color: #8fa0c3; font-size: 12px; margin-top: 2px; }
.account-section-title {
    margin: 6px 0 12px 0;
    font-size: 22px;
    font-weight: 800;
    color: #eef2ff;
}
.account-info-card {
    background: rgba(16, 19, 34, 0.74);
    border: 1px solid rgba(56,189,248,0.16);
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 12px;
    min-height: 100%;
}
.account-info-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 14px 18px;
}
.account-info-item { min-width: 0; }
.account-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: #86a0c8;
}
.account-value {
    font-size: 15px;
    color: #edf2ff;
    font-weight: 600;
    margin-top: 4px;
    word-break: break-word;
}
.account-soft-note {
    background: rgba(56,189,248,.07);
    border: 1px solid rgba(56,189,248,.14);
    border-radius: 14px;
    padding: 12px 14px;
    color: #a9bbdd;
    font-size: 13px;
    margin-top: 10px;
}
.account-activity-empty {
    border: 1px dashed rgba(56,189,248,.2);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    color: #97a8c8;
    background: rgba(255,255,255,.02);
}
@media (max-width: 900px) {
    .account-hero-grid { grid-template-columns: 1fr; }
    .account-kpi-wrap, .account-info-grid { grid-template-columns: 1fr; }
    .account-avatar { width: 84px; height: 84px; font-size: 28px; }
}

</style>
        <div class="login-wrapper">
            <div class="login-title">ErrorSweep</div>
            <div class="login-subtitle">Secure language automation dashboard</div>
            <div class="login-badge">Account required</div>
        </div>
        """),
        unsafe_allow_html=True,
    )

    if not supabase_configured():
        st.error("Supabase is not configured yet.")
        st.info("Add these values in Streamlit Cloud → App → Settings → Secrets:")
        st.code(
            'SUPABASE_URL = "https://your-project.supabase.co"\n'
            'SUPABASE_ANON_KEY = "your-anon-key"\n'
            'SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"',
            language="toml",
        )
        st.stop()

    tab_login, tab_signup, tab_reset = st.tabs(["Sign in", "Create account", "Reset password"])

    with tab_login:
        with st.form("supabase_login_form", clear_on_submit=False):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
        if submitted:
            ok, msg, data = auth_sign_in(email, password)
            if ok:
                set_session_from_auth(data)
                profile = ensure_profile(data.get("user") or {})
                st.session_state["sb_profile"] = profile
                st.success("Signed in successfully.")
                st.rerun()
            else:
                st.error(msg)

    with tab_signup:
        with st.form("supabase_signup_form", clear_on_submit=False):
            full_name = st.text_input("Full name")
            new_email = st.text_input("Email", key="signup_email")
            new_password = st.text_input("Password", type="password", key="signup_password", help="Use at least 8 characters.")
            confirm_password = st.text_input("Confirm password", type="password")
            signup_submitted = st.form_submit_button("Create account", use_container_width=True, type="primary")
        if signup_submitted:
            if len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                ok, msg, data = auth_sign_up(new_email, new_password, full_name)
                if ok:
                    user = data.get("user") or {}
                    if user:
                        ensure_profile(user)
                    st.success(msg)
                else:
                    st.error(msg)

    with tab_reset:
        with st.form("password_reset_form", clear_on_submit=True):
            reset_email = st.text_input("Account email")
            reset_submitted = st.form_submit_button("Send reset email", use_container_width=True)
        if reset_submitted:
            ok, msg = auth_send_password_reset(reset_email)
            if ok:
                st.success(msg)
            else:
                st.error(msg)


# ==========================================================
# NO-SIDEBAR APPLICATION LAYOUT
# Everything users need is available from normal pages.
# The app no longer depends on st.sidebar for logout/settings.
# ==========================================================

def init_page_state() -> None:
    defaults = {
        "es_page": "Dashboard",
        "es_domain": "Auto-detect",
        "es_strictness": "Strict",
        "es_check_whole_file": True,
        "es_max_segments": 200,
        "es_batch_size": 20,
        "es_source_col_hint": "",
        "es_target_col_hint": "",
        "es_skip_non_content": True,
        "es_deep_scan": False,
        "es_target_language": "Auto-detect",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def get_page_settings() -> Dict[str, Any]:
    check_whole_file = bool(st.session_state.get("es_check_whole_file", True))
    return {
        "domain": st.session_state.get("es_domain", "Auto-detect"),
        "strictness": st.session_state.get("es_strictness", "Strict"),
        "check_whole_file": check_whole_file,
        "max_segments": 0 if check_whole_file else int(st.session_state.get("es_max_segments", 200)),
        "batch_size": int(st.session_state.get("es_batch_size", 20)),
        "source_col_hint": st.session_state.get("es_source_col_hint", ""),
        "target_col_hint": st.session_state.get("es_target_col_hint", ""),
        "skip_non_content": bool(st.session_state.get("es_skip_non_content", True)),
        "deep_scan": bool(st.session_state.get("es_deep_scan", False)),
        "target_language": st.session_state.get("es_target_language", "Auto-detect"),
        "openai_model": DEFAULT_OPENAI_MODEL,
        "gemini_model": DEFAULT_GEMINI_MODEL,
    }


def render_top_account_bar(profile: Optional[Dict[str, Any]]) -> None:
    user = get_current_user()
    email = user.get("email") or st.session_state.get("errorsweep_username", "user")
    c1, c2, c3, c4 = st.columns([2.2, 1.2, 1.2, 1])
    with c1:
        st.caption(f"Signed in as: {email}")
    with c2:
        if profile:
            st.caption(f"Plan: {str(profile.get('plan', 'trial')).title()}")
    with c3:
        if profile:
            st.caption(f"Credits: {remaining_credits(profile)}")
    with c4:
        if st.button("Logout", use_container_width=True, key="top_logout_button"):
            logout_user()


def render_top_nav() -> str:
    pages = ["Dashboard", "ErrorSweep", "ErrorSweep Pro", "Memory & Rules", "Billing", "Account"]
    if is_admin_user():
        pages.append("Admin")
    if st.session_state.get("es_page") not in pages:
        st.session_state["es_page"] = "Dashboard"
    return st.radio(
        "Navigation",
        pages,
        key="es_page",
        horizontal=True,
        label_visibility="collapsed",
    )


def render_settings_summary(settings: Dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Domain", settings["domain"])
    c2.metric("Strictness", settings["strictness"])
    c3.metric("Scan", "Whole file" if settings["check_whole_file"] else str(settings["max_segments"]))
    c4.metric("Batch", settings["batch_size"])
    with st.expander("Current settings", expanded=False):
        st.write(f"Source column hint: {settings['source_col_hint'] or 'Auto-detect'}")
        st.write(f"Target column hint: {settings['target_col_hint'] or 'Auto-detect'}")
        st.write(f"Skip non-content sheets: {'Yes' if settings['skip_non_content'] else 'No'}")
        st.write(f"Deep scan fallback: {'Yes' if settings['deep_scan'] else 'No'}")
        st.write(f"Target language for Pro: {settings['target_language']}")
        st.write(f"Managed AI allowed: {'Yes' if managed_ai_allowed() else 'No'}")
        st.write(f"User language-engine key entered: {'Yes' if bool(get_user_openai_key()) else 'No'}")


def render_workflow_hero(title: str, subtitle: str, mode: str) -> None:
    if mode == "qa":
        steps = [
            ("1", "Upload translated file", "Excel, Word, CSV, XLIFF, PDF, JSON, SRT, or text."),
            ("2", "Add client context", "Use saved rule pack or upload a ZIP with glossary, DNT, style guide, and references."),
            ("3", "Run QA", "ErrorSweep auto-detects layout, checks rules, and exports an Excel report."),
        ]
    else:
        steps = [
            ("1", "Upload source file", "The app detects source rows and target/output areas automatically."),
            ("2", "Choose language + rules", "Pick target language and optionally add memory/rule context."),
            ("3", "Translate + review", "The app uses memory, glossary, local/managed engine, then quality-gates output."),
        ]
    step_html = "".join(
        f'<div class="workflow-step"><div class="num">{n}</div><h4>{escape(h)}</h4><p>{escape(p)}</p></div>'
        for n, h, p in steps
    )
    st.markdown(
        f"""
        <div class="workflow-hero-card">
            <h2>{escape(title)}</h2>
            <p>{escape(subtitle)}</p>
        </div>
        <div class="workflow-steps">{step_html}</div>
        """,
        unsafe_allow_html=True,
    )


def render_engine_status_cards(context: str, openai_client=None, gemini_client=None) -> None:
    if context == "qa":
        cards = [
            ("Rule engine", "ON", "ready"),
            ("Grammar/style", "ON if available", "ready"),
            ("Memory", "Optional", "ready"),
            ("AI suggestions", "Optional", "warn" if openai_client is None else "ready"),
        ]
    else:
        local_ready = has_local_translation_engine() if 'has_local_translation_engine' in globals() else False
        if openai_client:
            engine = "Language engine"
            cls = "ready"
        elif local_ready:
            engine = "Self-hosted engine"
            cls = "ready"
        else:
            engine = "Memory / glossary only"
            cls = "warn"
        cards = [
            ("Translation", engine, cls),
            ("Review", "Available" if gemini_client else "Rules only", "ready" if gemini_client else "warn"),
            ("Format output", "Same file type", "ready"),
            ("Memory", "Reuse first", "ready"),
        ]
    html = "".join(
        f'<div class="simple-status-card {cls}"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'
        for label, value, cls in cards
    )
    st.markdown(f'<div class="simple-status-grid">{html}</div>', unsafe_allow_html=True)


def render_inline_workflow_settings(context: str) -> Dict[str, Any]:
    """Simple Mode settings. Essential controls visible; everything technical hidden."""
    is_pro = context == "pro"

    with st.container(border=True):
        st.markdown("### Simple setup")
        c1, c2 = st.columns(2)
        with c1:
            if is_pro:
                st.text_input(
                    "Target language",
                    key="es_target_language",
                    placeholder="Required: Spanish, French, Hindi, Arabic, ja-JP",
                    help="Required for translation. Example: French, Spanish, Telugu, hi-IN, ar, ja-JP.",
                )
            else:
                st.text_input(
                    "Target language / locale",
                    key="es_target_language",
                    placeholder="Auto-detect, English, Spanish, French, Hindi, Arabic, ja-JP",
                    help="For best no-API QA, choose the real target language. Auto-detect is okay for formatting-only checks.",
                )
        with c2:
            st.selectbox(
                "Content domain",
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
                key="es_domain",
            )
        st.markdown(
            "<div class='simple-advanced-note'>Most settings are automatic. Open Advanced Settings only if the app does not detect your file layout correctly.</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Advanced Settings", expanded=False):
        st.markdown("#### Quality and scan behavior")
        a1, a2, a3 = st.columns(3)
        with a1:
            st.select_slider(
                "QA strictness",
                options=["Lenient", "Standard", "Strict", "Very Strict"],
                key="es_strictness",
            )
        with a2:
            st.checkbox("Check whole file", key="es_check_whole_file")
            if not st.session_state.get("es_check_whole_file", True):
                st.number_input("Max total segments", min_value=5, max_value=5000, key="es_max_segments")
        with a3:
            st.number_input("Segments per batch", min_value=5, max_value=50, key="es_batch_size")

        st.markdown("#### File detection hints")
        d1, d2 = st.columns(2)
        with d1:
            st.text_input("Source column name / index", key="es_source_col_hint", placeholder="Example: Source Text or 2")
        with d2:
            st.text_input("Target / translation column name / index", key="es_target_col_hint", placeholder="Example: Translation or 3")
        f1, f2 = st.columns(2)
        with f1:
            st.checkbox("Skip non-content sheets", key="es_skip_non_content")
        with f2:
            st.checkbox("Deep scan if columns are not found", key="es_deep_scan")

        st.markdown("#### No-API spelling / grammar / style")
        g1, g2, g3 = st.columns(3)
        with g1:
            st.checkbox("Run global grammar/style engine", value=True, key="es_enable_languagetool")
        with g2:
            st.selectbox("Grammar engine mode", ["public", "local"], key="es_languagetool_mode")
        with g3:
            st.number_input("Max chars per segment", min_value=200, max_value=3000, value=1200, step=100, key="es_languagetool_max_chars")
        st.caption("Public mode can send text to LanguageTool. Use local/private mode for confidential files.")

        st.markdown("#### Optional user API keys")
        k1, k2 = st.columns(2)
        with k1:
            st.text_input("Language-engine API key", type="password", key="es_user_openai_api_key", placeholder="Optional")
        with k2:
            if is_pro:
                st.text_input("Independent-review API key", type="password", key="es_user_gemini_api_key", placeholder="Optional")
            else:
                st.info("Independent review key is used only in ErrorSweep Pro.")
        st.caption(f"Managed server AI is {'enabled' if managed_ai_allowed() else 'disabled'} by deployment settings.")

    return get_page_settings()

def render_control_center_page() -> None:
    st.markdown("## Control Center")
    st.caption("All controls that were previously in the left panel are now available here.")

    st.markdown("### QA Settings")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox(
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
            key="es_domain",
        )
    with c2:
        st.select_slider(
            "QA Strictness",
            options=["Lenient", "Standard", "Strict", "Very Strict"],
            key="es_strictness",
        )

    st.markdown("### Scan Size")
    st.checkbox(
        "Check whole file",
        key="es_check_whole_file",
        help="When enabled, ErrorSweep extracts and checks every available segment instead of stopping after a fixed limit.",
    )
    if st.session_state.get("es_check_whole_file", True):
        st.info("Full-file mode is ON. Large files can take longer and may consume more credits/API usage.")
    else:
        st.number_input("Max total segments", min_value=5, max_value=5000, key="es_max_segments")
    st.number_input("Segments per AI call", min_value=5, max_value=50, key="es_batch_size")

    st.markdown("### File Detection")
    d1, d2 = st.columns(2)
    with d1:
        st.text_input("Source column name/index", key="es_source_col_hint", placeholder="Example: Source Text or 2")
    with d2:
        st.text_input("Translation column name/index", key="es_target_col_hint", placeholder="Example: Original Translation or 3")
    st.checkbox("Skip non-content sheets", key="es_skip_non_content")
    st.checkbox("Deep scan if columns are not found", key="es_deep_scan")

    st.markdown("### ErrorSweep Pro")
    st.text_input("Default target language", key="es_target_language", placeholder="Required for no-API QA: Spanish, French, Hindi, Arabic, ja-JP")

    st.markdown("### API Cost Control")
    st.info("API keys are optional. Without keys, ErrorSweep QA still runs in offline rule-based mode. ErrorSweep Pro uses glossary/DNT reference mode unless a language-engine key is provided.")
    st.text_input("Your language-engine API key (optional, current session only)", type="password", key="es_user_openai_api_key", help="Use this only if you want AI QA or full translation to use your own API account.")
    st.text_input("Your independent-review API key (optional, current session only)", type="password", key="es_user_gemini_api_key", help="Optional review engine key for independent review.")
    st.caption(f"Managed server AI is {'enabled' if managed_ai_allowed() else 'disabled'} by deployment settings.")

    st.markdown("### System Status")
    c1, c2 = st.columns(2)
    c1.metric("Language Engine", "Configured" if get_openai_client() else "Missing")
    c2.metric("Review Engine", "Configured" if get_gemini_client() else "Missing")
    st.caption("If an engine is missing, check Streamlit Secrets. This page replaces the hidden left panel.")


def _format_dt(value: Any, with_time: bool = False) -> str:
    if not value:
        return "—"
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%d %b %Y, %H:%M UTC" if with_time else "%d %b %Y")
    except Exception:
        return str(value)


def _initials(name: str) -> str:
    if not name:
        return "ES"
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", name) if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return "ES"


def _bool_label(flag: bool) -> str:
    return "Enabled" if flag else "Disabled"


def render_account_page(profile: Optional[Dict[str, Any]]) -> None:
    user = get_current_user()
    user_id = str(user.get("id") or "")
    email = user.get("email") or st.session_state.get("errorsweep_username", "user@example.com")

    if not profile:
        st.warning("Profile unavailable. Please log out and sign in again.")
        if st.button("Logout", key="account_logout_missing", use_container_width=True):
            logout_user()
        return

    settings = get_page_settings()
    jobs = get_recent_jobs(user_id, limit=6) if user_id else []

    plan_key = normalize_plan(profile.get("plan"))
    plan_name = PLAN_CATALOG.get(plan_key, PLAN_CATALOG["trial"])["name"]
    monthly = int(profile.get("monthly_credits") or 0)
    used = int(profile.get("used_credits") or 0)
    remaining = max(0, monthly - used)
    full_name = (profile.get("full_name") or email.split("@")[0]).strip()
    display_name = full_name.replace(".", " ").replace("_", " ").title()
    role_label = "Master Access" if is_admin_user() else "Member"
    status_label = str(profile.get("subscription_status") or "active").replace("_", " ").title()
    member_since = _format_dt(profile.get("created_at"))
    last_activity = _format_dt(jobs[0].get("created_at"), with_time=True) if jobs else "No jobs yet"
    initials = _initials(display_name or email)
    workflow_mix = sum(1 for j in jobs if str(j.get("workflow", "")).lower().startswith("error"))
    last_workflow = jobs[0].get("workflow") if jobs else "No recent workflow"
    credits_used_pct = int(round((used / max(monthly, 1)) * 100)) if monthly else 0

    st.markdown("## Account Overview")
    st.markdown(f"""
    <div class="account-hero">
        <div class="account-hero-grid">
            <div class="account-avatar">{escape(initials)}</div>
            <div>
                <div class="account-title">{escape(display_name)}</div>
                <div class="account-subline">{escape(email)}</div>
                <div class="account-badge-row">
                    <span class="account-pill plan">Plan · {escape(plan_name)}</span>
                    <span class="account-pill role">Role · {escape(role_label)}</span>
                    <span class="account-pill status">Status · {escape(status_label)}</span>
                    <span class="account-pill security">Managed AI · {escape(_bool_label(managed_ai_allowed()))}</span>
                </div>
            </div>
            <div class="account-kpi-wrap">
                <div class="account-kpi">
                    <div class="account-kpi-label">Credits Remaining</div>
                    <div class="account-kpi-value">{remaining}</div>
                    <div class="account-kpi-sub">of {monthly} monthly credits</div>
                </div>
                <div class="account-kpi">
                    <div class="account-kpi-label">Usage This Cycle</div>
                    <div class="account-kpi-value">{credits_used_pct}%</div>
                    <div class="account-kpi-sub">{used} credits consumed</div>
                </div>
                <div class="account-kpi">
                    <div class="account-kpi-label">Recent Activity</div>
                    <div class="account-kpi-value">{len(jobs)}</div>
                    <div class="account-kpi-sub">latest 6 jobs tracked</div>
                </div>
                <div class="account-kpi">
                    <div class="account-kpi-label">Member Since</div>
                    <div class="account-kpi-value" style="font-size:18px;">{escape(member_since)}</div>
                    <div class="account-kpi-sub">last active {escape(last_activity)}</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Plan", plan_name)
    c2.metric("Credits Remaining", remaining)
    c3.metric("Used Credits", used)
    c4.metric("Monthly Credits", monthly)
    st.progress(min(1.0, used / max(monthly, 1)) if monthly else 0.0)

    left, right = st.columns(2)
    with left:
        st.markdown("### Profile & Access")
        st.markdown(f"""
        <div class="account-info-card">
            <div class="account-info-grid">
                <div class="account-info-item"><div class="account-label">Display name</div><div class="account-value">{escape(display_name)}</div></div>
                <div class="account-info-item"><div class="account-label">Email</div><div class="account-value">{escape(email)}</div></div>
                <div class="account-info-item"><div class="account-label">Role</div><div class="account-value">{escape(role_label)}</div></div>
                <div class="account-info-item"><div class="account-label">Account status</div><div class="account-value">{escape(status_label)}</div></div>
                <div class="account-info-item"><div class="account-label">Member since</div><div class="account-value">{escape(member_since)}</div></div>
                <div class="account-info-item"><div class="account-label">Last activity</div><div class="account-value">{escape(last_activity)}</div></div>
                <div class="account-info-item"><div class="account-label">User ID</div><div class="account-value">{escape(user_id or '—')}</div></div>
                <div class="account-info-item"><div class="account-label">Recent workflow</div><div class="account-value">{escape(str(last_workflow))}</div></div>
            </div>
            <div class="account-soft-note">Your account details, plan status, and current access level are shown here. This page is designed as a premium user profile dashboard for clients and internal team members.</div>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown("### Workflow Preferences")
        st.markdown(f"""
        <div class="account-info-card">
            <div class="account-info-grid">
                <div class="account-info-item"><div class="account-label">Content domain</div><div class="account-value">{escape(str(settings['domain']))}</div></div>
                <div class="account-info-item"><div class="account-label">QA strictness</div><div class="account-value">{escape(str(settings['strictness']))}</div></div>
                <div class="account-info-item"><div class="account-label">Default target language</div><div class="account-value">{escape(str(settings['target_language']))}</div></div>
                <div class="account-info-item"><div class="account-label">Batch size</div><div class="account-value">{settings['batch_size']}</div></div>
                <div class="account-info-item"><div class="account-label">Full-file scan</div><div class="account-value">{escape('On' if settings['check_whole_file'] else 'Off')}</div></div>
                <div class="account-info-item"><div class="account-label">Deep scan fallback</div><div class="account-value">{escape('On' if settings['deep_scan'] else 'Off')}</div></div>
                <div class="account-info-item"><div class="account-label">User language engine key</div><div class="account-value">{escape(_bool_label(bool(get_user_openai_key())))}</div></div>
                <div class="account-info-item"><div class="account-label">Independent review key</div><div class="account-value">{escape(_bool_label(bool(get_user_gemini_key())))}</div></div>
            </div>
            <div class="account-soft-note">These are the workflow preferences currently active in this session. Users can fine-tune QA and translation settings inside the ErrorSweep and ErrorSweep Pro pages.</div>
        </div>
        """, unsafe_allow_html=True)

    s1, s2 = st.columns(2)
    with s1:
        st.markdown("### Security & Access")
        st.markdown(f"""
        <div class="account-info-card">
            <div class="account-info-grid">
                <div class="account-info-item"><div class="account-label">Login method</div><div class="account-value">Email + password</div></div>
                <div class="account-info-item"><div class="account-label">Managed AI mode</div><div class="account-value">{escape(_bool_label(managed_ai_allowed()))}</div></div>
                <div class="account-info-item"><div class="account-label">Admin / master access</div><div class="account-value">{escape('Granted' if is_admin_user() else 'No')}</div></div>
                <div class="account-info-item"><div class="account-label">Session state</div><div class="account-value">Authenticated</div></div>
                <div class="account-info-item"><div class="account-label">Billing model</div><div class="account-value">Credits + plan based</div></div>
                <div class="account-info-item"><div class="account-label">Data processing</div><div class="account-value">Private app workflow</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with s2:
        st.markdown("### Usage Snapshot")
        qa_jobs = sum(1 for j in jobs if 'qa' in str(j.get('workflow','')).lower() or 'errorsweep' in str(j.get('workflow','')).lower())
        pro_jobs = sum(1 for j in jobs if 'pro' in str(j.get('workflow','')).lower())
        st.markdown(f"""
        <div class="account-info-card">
            <div class="account-info-grid">
                <div class="account-info-item"><div class="account-label">Tracked jobs</div><div class="account-value">{len(jobs)}</div></div>
                <div class="account-info-item"><div class="account-label">QA runs</div><div class="account-value">{qa_jobs}</div></div>
                <div class="account-info-item"><div class="account-label">Pro runs</div><div class="account-value">{pro_jobs}</div></div>
                <div class="account-info-item"><div class="account-label">Workflow mix</div><div class="account-value">{workflow_mix} tracked activity items</div></div>
                <div class="account-info-item"><div class="account-label">Credits consumed</div><div class="account-value">{used}</div></div>
                <div class="account-info-item"><div class="account-label">Next best action</div><div class="account-value">{escape('Upgrade plan' if remaining <= max(5, monthly * 0.1) else 'Continue working')}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Actions")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button("Go to Billing", use_container_width=True, key="account_go_billing"):
            st.session_state["es_page"] = "Billing"
            st.rerun()
    with a2:
        if st.button("Open ErrorSweep", use_container_width=True, key="account_go_qa"):
            st.session_state["es_page"] = "ErrorSweep"
            st.rerun()
    with a3:
        if st.button("Send reset email", use_container_width=True, key="account_reset_email"):
            ok, msg = auth_send_password_reset(email)
            (st.success if ok else st.error)(msg)
    with a4:
        if st.button("Logout", type="primary", use_container_width=True, key="account_logout_button"):
            logout_user()

    st.markdown("### Recent activity")
    if jobs:
        job_rows = []
        for j in jobs:
            job_rows.append({
                "Created": _format_dt(j.get("created_at"), with_time=True),
                "Workflow": j.get("workflow", "—"),
                "File": j.get("file_name") or j.get("filename") or "—",
                "Status": j.get("status", "—"),
                "Credits": j.get("credits_used") or j.get("credits") or 0,
            })
        st.dataframe(pd.DataFrame(job_rows), use_container_width=True, hide_index=True)
    else:
        st.markdown('<div class="account-activity-empty">No activity yet. Run your first QA check or translation workflow to start building account history.</div>', unsafe_allow_html=True)


# ==========================================================
# PAYMENT HISTORY / WEBHOOK STATUS
# ==========================================================

def payment_events_table_available() -> bool:
    if not supabase_service_configured():
        return False
    ok, data = supabase_get("/rest/v1/payment_events?select=id&limit=1", kind="service")
    return bool(ok)


def get_user_payment_events(profile: Optional[Dict[str, Any]], limit: int = 25) -> List[Dict[str, Any]]:
    if not profile or not supabase_service_configured():
        return []
    user_id = profile.get("id", "")
    email = profile.get("email", "")

    queries = []
    if user_id:
        queries.append(f"/rest/v1/payment_events?user_id=eq.{user_id}&select=*&order=created_at.desc&limit={int(limit)}")
    if email:
        queries.append(f"/rest/v1/payment_events?user_email=ilike.{quote(str(email))}&select=*&order=created_at.desc&limit={int(limit)}")

    rows_by_id: Dict[str, Dict[str, Any]] = {}
    for query in queries:
        ok, data = supabase_get(query, kind="service")
        if ok and isinstance(data, list):
            for row in data:
                rid = str(row.get("id") or row.get("payment_id") or len(rows_by_id))
                rows_by_id[rid] = row
    rows = list(rows_by_id.values())
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return rows[:limit]


def admin_list_payment_events(limit: int = 100, email_filter: str = "") -> List[Dict[str, Any]]:
    if not supabase_service_configured():
        return []
    if email_filter.strip():
        query = f"/rest/v1/payment_events?user_email=ilike.{quote('%' + email_filter.strip() + '%')}&select=*&order=created_at.desc&limit={int(limit)}"
    else:
        query = f"/rest/v1/payment_events?select=*&order=created_at.desc&limit={int(limit)}"
    ok, data = supabase_get(query, kind="service")
    if ok and isinstance(data, list):
        return data
    return []


def format_payment_events_for_display(events: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for event in events:
        amount = event.get("amount")
        if amount is not None:
            try:
                amount_display = round(float(amount) / 100, 2)
            except Exception:
                amount_display = amount
        else:
            amount_display = ""
        rows.append({
            "Date": event.get("created_at", ""),
            "Email": event.get("user_email", ""),
            "Plan": event.get("plan", ""),
            "Credits": event.get("credits", ""),
            "Amount": amount_display,
            "Currency": event.get("currency", ""),
            "Status": event.get("status", ""),
            "Processed": "Yes" if event.get("processed") else "No",
            "Payment ID": event.get("payment_id", ""),
            "Error": event.get("error", ""),
        })
    return pd.DataFrame(rows)


def render_payment_history_section(profile: Optional[Dict[str, Any]]) -> None:
    st.markdown("### Payment history")
    if not payment_events_table_available():
        st.info("Payment event tracking is not active yet. Run the payment webhook SQL setup in Supabase to enable payment history and automatic plan upgrades.")
        with st.expander("Supabase SQL setup needed", expanded=False):
            st.write("Run the Razorpay payment webhook schema SQL in Supabase. This creates the `payment_events` table and payment columns in `profiles`.")
        return

    events = get_user_payment_events(profile, limit=25)
    if not events:
        st.info("No payment events found yet. After a successful payment webhook, events will appear here.")
        return

    df = format_payment_events_for_display(events)
    st.dataframe(df, use_container_width=True, hide_index=True)

    processed = sum(1 for e in events if e.get("processed"))
    pending = len(events) - processed
    c1, c2, c3 = st.columns(3)
    c1.metric("Payment Events", len(events))
    c2.metric("Processed", processed)
    c3.metric("Pending / Failed", pending)


def render_billing_page(profile: Optional[Dict[str, Any]]) -> None:
    st.markdown("## Billing & Plans")
    st.caption("Use payment links for MVP billing. If Razorpay webhook is configured, upgrades can be automatic. Manual admin upgrade remains available as backup.")

    if not profile:
        st.warning("Profile unavailable. Please log out and log in again.")
        return

    current_plan = normalize_plan(profile.get("plan"))
    monthly = int(profile.get("monthly_credits") or 0)
    used = int(profile.get("used_credits") or 0)
    remaining = max(0, monthly - used)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Plan", PLAN_CATALOG[current_plan]["name"])
    c2.metric("Credits Remaining", remaining)
    c3.metric("Used Credits", used)
    c4.metric("Monthly Credits", monthly)

    if monthly > 0:
        st.progress(min(1.0, used / max(monthly, 1)))

    if remaining <= max(5, monthly * 0.10):
        st.warning("Credits are low. Upgrade or contact admin to add credits.")

    st.markdown("### Choose a plan")
    p1, p2, p3 = st.columns(3)
    with p1:
        with st.container(border=True):
            render_plan_card("errorsweep", current_plan)
    with p2:
        with st.container(border=True):
            render_plan_card("pro", current_plan)
    with p3:
        with st.container(border=True):
            render_plan_card("agency", current_plan)

    with st.expander("Enterprise / custom plan", expanded=False):
        render_plan_card("enterprise", current_plan)

    render_payment_history_section(profile)

    st.markdown("### How billing works")
    st.markdown(
        """
        **Preferred automatic flow**

        1. User clicks an upgrade button and completes payment.
        2. Payment provider sends a webhook to Supabase Edge Function.
        3. Supabase updates the user's plan and credits automatically.
        4. User refreshes ErrorSweep and sees upgraded credits.

        **Manual backup flow**

        If webhook is not configured or a payment used a different email, admin can still verify payment manually and upgrade the user from the **Admin** page.
        """
    )

    st.markdown("### Credit charging guide")
    st.dataframe(
        pd.DataFrame([
            {"Workflow": "ErrorSweep QA", "Credit rule": "1 credit per 100 segments", "Notes": "Rules ZIP adds 1 credit"},
            {"Workflow": "ErrorSweep Pro", "Credit rule": "3 credits per 75 segments", "Notes": "Independent review and Rules ZIP may add credits"},
            {"Workflow": "Offline QA", "Credit rule": "Same app credits apply", "Notes": "API availability does not make runs free"},
        ]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Secrets to add for payment buttons")
    st.code(
        'PAYMENT_LINK_ERRORSWEEP = "https://your-payment-link-for-errorsweep"\n'
        'PAYMENT_LINK_PRO = "https://your-payment-link-for-pro"\n'
        'PAYMENT_LINK_AGENCY = "https://your-payment-link-for-agency"\n'
        'PAYMENT_LINK_ENTERPRISE = "https://your-enterprise-contact-or-payment-link"',
        language="toml",
    )


def render_dashboard_page(user_id: str, profile: Optional[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    st.markdown(
        """
    <div class="hero">
        <div class="hero-title">ErrorSweep</div>
        <div class="hero-sub">QA suggestions, company rules ZIP, translation, and independent review</div>
        <div class="hero-badge">Top navigation · Workflow settings inside each page · Secure memory manager</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="note-card">
        <b>Simple Mode enabled:</b> ErrorSweep now shows only essential workflow inputs first. Advanced settings are hidden unless needed.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if user_id:
        render_usage_dashboard(user_id)

    render_settings_summary(settings)

    st.markdown("### Workflows")
    st.markdown(
        """
        <div class="es-visual-grid">
          <div class="es-tile"><h4>ErrorSweep</h4><p>QA settings, file detection, offline rules, optional API key, and QA Rules ZIP are all inside this page.</p></div>
          <div class="es-tile"><h4>ErrorSweep Pro</h4><p>Target language, translation settings, optional API keys, review settings, and Pro Rules ZIP are all inside this page.</p></div>
          <div class="es-tile"><h4>Billing</h4><p>View credits, plans, and upgrade options without using a sidebar.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rule_upload(prefix: str, user_id: str = "", workflow_type: str = "both") -> Tuple[Any, Any, Dict[str, Any]]:
    uploaded_file = st.file_uploader(
        "Upload file",
        type=None,
        key=f"{prefix}_uploaded_file",
        help="Upload any file. ErrorSweep will automatically extract text/segments from Excel, Word, PDF, CSV, XLIFF/XML/XLZ, JSON, subtitles, PO/properties, and other text-like files. Binary files without readable text will return an Excel report explaining the issue.",
    )

    saved_rules, selected_pack_id = render_rule_pack_selector(user_id, workflow_type, prefix) if user_id else ({"chunks": [], "glossary": [], "dnt": [], "files": [], "warnings": []}, None)

    rules_zip = st.file_uploader(
        "Upload Rules ZIP (optional: style guide, DNT list, glossary, instructions, references)",
        type=["zip"],
        key=f"{prefix}_rules_zip",
    )
    uploaded_rules = {"chunks": [], "glossary": [], "dnt": [], "files": [], "warnings": []}
    if rules_zip:
        uploaded_rules = parse_rules_zip_bytes(rules_zip.getvalue())
        with st.expander("Rules ZIP summary", expanded=False):
            st.write(f"Files parsed: {len(uploaded_rules.get('files', []))}")
            st.write(f"Rule chunks: {len(uploaded_rules.get('chunks', []))}")
            st.write(f"Glossary entries: {len(uploaded_rules.get('glossary', []))}")
            st.write(f"DNT entries: {len(uploaded_rules.get('dnt', []))}")
            if uploaded_rules.get("files"):
                st.write(uploaded_rules.get("files")[:20])
            for w in uploaded_rules.get("warnings", []):
                st.warning(w)
        render_rule_pack_save_box(user_id, prefix, workflow_type, uploaded_rules, rules_zip.name, default_domain=st.session_state.get("es_domain", ""))

    # Saved rule pack + uploaded ZIP are merged; uploaded ZIP can supplement/override current run context.
    rules = merge_rules(saved_rules, uploaded_rules)
    return uploaded_file, rules_zip or selected_pack_id, rules




# ==========================================================
# OFFLINE / REFERENCE-ONLY TRANSLATION FALLBACK
# ==========================================================

def _apply_glossary_replacements(source_text: str, rules: Dict[str, Any]) -> Tuple[str, int]:
    """Very conservative no-API pre-translation.

    It uses only uploaded glossary terms. This is NOT a full machine translation.
    It is a safe fallback when no language engine/API key is available.
    """
    result = source_text or ""
    replacements = 0
    glossary = rules.get("glossary", []) if rules else []
    # Longest first avoids replacing small substrings before longer terms.
    glossary_sorted = sorted(glossary, key=lambda g: len(str(g.get("source_term", ""))), reverse=True)
    for g in glossary_sorted[:1000]:
        src = normalize_text(g.get("source_term", ""))
        tgt = normalize_text(g.get("target_term", ""))
        if not src or not tgt:
            continue
        pattern = re.compile(re.escape(src), re.IGNORECASE)
        result, count = pattern.subn(tgt, result)
        replacements += count
    return result, replacements


def offline_reference_translate_batch(
    segments: List[Dict[str, Any]],
    target_language: str,
    rules: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """No-API fallback for ErrorSweep Pro.

    Full translation needs a translation engine. When no API is available, this
    function still keeps the workflow alive by applying uploaded glossary/DNT
    references and returning safe placeholder output. It never pretends that a
    full professional translation was produced.
    """
    output = []
    dnt_terms = [normalize_text(d.get("term", "")) for d in (rules.get("dnt", []) if rules else []) if normalize_text(d.get("term", ""))]
    for seg in segments:
        loc = seg.get("location", "")
        source = normalize_text(seg.get("source") or seg.get("text") or "")
        if not source:
            output.append({"location": loc, "translation": ""})
            continue
        # Preserve placeholders-only, DNT-only, or bracket labels as-is.
        if source.startswith("[") and source.endswith("]"):
            translation = source
        elif any(term and source.strip() == term for term in dnt_terms):
            translation = source
        else:
            translation, count = _apply_glossary_replacements(source, rules)
            # If no glossary replacement happened, keep target blank rather than
            # copying English as a fake translation.
            if count == 0:
                translation = ""
        output.append({"location": loc, "translation": translation})
    return output


def build_offline_translation_review_rows(segments: List[Dict[str, Any]], translations_by_loc: Dict[str, str]) -> List[Dict[str, Any]]:
    rows = []
    for seg in segments:
        loc = seg.get("location", "")
        trans = translations_by_loc.get(loc, "")
        if not trans:
            rows.append(make_report_row(
                {**seg, "translation": ""},
                "Translation Engine Required",
                "Review",
                "No offline full translation available",
                "Provide a language-engine API key or upload a glossary/rule pack with approved translations.",
                "Offline mode can apply deterministic QA and glossary/DNT references, but it cannot generate full professional translations for arbitrary global languages.",
                "Offline Reference Mode",
                "Built-in fallback",
                "High",
            ))
    return rows

def render_errorsweep_page(user_id: str, profile: Optional[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    render_workflow_hero(
        "ErrorSweep — QA Run",
        "Upload a translated file, add optional client rules, and get an Excel QA report with real errors first.",
        "qa",
    )
    openai_client = get_openai_client()
    render_engine_status_cards("qa", openai_client=openai_client)
    settings = render_inline_workflow_settings("qa")

    if openai_client is None:
        st.info("Offline QA mode is available. Deterministic rules, company Rules ZIP, glossary, DNT, placeholders, numbers, spacing, punctuation, and language-specific checks can run without any API key. App credits still apply to generate reports.")

    uploaded_file, rules_zip, rules = render_rule_upload("qa", user_id=user_id, workflow_type="qa")
    tm_controls = render_translation_memory_controls("qa", default_target_language=settings.get("target_language", ""))
    history_corrections = load_correction_history_as_rules(
        user_id,
        client_key=tm_controls.get("client_key", "global"),
        target_language=tm_controls.get("target_language", settings.get("target_language", "auto-detect")),
        domain=settings.get("domain", ""),
    )
    if history_corrections:
        rules.setdefault("corrections", [])
        rules["corrections"].extend(history_corrections)
        st.info(f"Loaded {len(history_corrections)} approved correction-history rule(s) for this QA run.")

    st.markdown("### Run")
    # Simple Mode defaults. Users only open advanced controls when needed.
    run_rules = True
    run_zwnj = True
    output_highlighted = True
    include_ai_style = False
    run_ai = bool(openai_client and st.session_state.get("qa_run_ai", False))
    with st.expander("Advanced QA run options", expanded=False):
        a1, a2, a3 = st.columns(3)
        with a1:
            run_ai = st.checkbox("Enable AI suggestions", value=bool(openai_client and st.session_state.get("qa_run_ai", False)), key="qa_run_ai")
        with a2:
            output_highlighted = st.checkbox("Highlight Excel output", value=True, key="qa_highlight")
        with a3:
            include_ai_style = st.checkbox("Allow subjective style suggestions", value=False, key="qa_ai_style")
        run_zwnj = st.checkbox("Check invisible/ZWNJ character issues", value=True, key="qa_zwnj")

    run = st.button("Run QA", type="primary", use_container_width=True, disabled=not uploaded_file, key="run_qa_no_sidebar")

    if uploaded_file and run:
        if run_ai and openai_client is None:
            st.warning("AI QA is unavailable, so ErrorSweep will continue in offline rule-based mode. No API key is required, but app credits are still required for the report.")
            run_ai = False
        if not run_rules and not run_ai:
            st.warning("No checks selected. Turning deterministic offline rules ON so the file can still be reviewed without API keys.")
            run_rules = True

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

        file_bytes = uploaded_file_bytes(uploaded_file)
        if lower.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")) or is_openpyxl_compatible(file_bytes):
            workbook, segments, cell_map, _, logs = extract_excel_segments(
                io.BytesIO(file_bytes), settings["source_col_hint"], settings["target_col_hint"], "qa", int(settings["max_segments"]), settings["skip_non_content"], settings["deep_scan"]
            )
        elif lower.endswith(".csv"):
            _, segments, logs = extract_csv_segments(uploaded_file, settings["source_col_hint"], settings["target_col_hint"], "qa", int(settings["max_segments"]), settings["deep_scan"])
        elif lower.endswith(".docx"):
            _, segments, _, logs = extract_docx_segments(uploaded_file, "qa", int(settings["max_segments"]), settings["source_col_hint"], settings["target_col_hint"])
        elif lower.endswith(".pdf"):
            segments, logs = extract_pdf_segments(uploaded_file, "qa", int(settings["max_segments"]))
        else:
            _, segments, logs = extract_text_segments(uploaded_file, "qa", int(settings["max_segments"]))

        with st.expander("Extraction log", expanded=True):
            for log in logs:
                st.write(log)
            st.info(f"Found {len(segments)} segment(s) to check. Full-file mode is {'ON' if settings['check_whole_file'] else 'OFF'}.")

        if not segments:
            st.error("No segments found. Use the settings panel on this page to set source/translation columns or enable deep scan.")
            st.stop()

        # App credits are required for every generated report, even when API/AI is unavailable.
        # API credits and ErrorSweep app credits are separate:
        # - API credits pay the external language/review engine provider.
        # - App credits pay for ErrorSweep extraction, rule checks, report generation, storage/logging, and product usage.
        using_managed_ai = bool(run_ai and openai_client)
        segments, credits_needed, credit_message = maybe_limit_segments_to_available_credits(
            segments, profile, "qa", rules_zip_used=bool(rules_zip), independent_review=False
        )
        if not segments:
            st.error(f"{credit_message} App credits are required for all QA reports, including offline rule-based reports.")
            st.stop()
        if "Not enough credits" in credit_message:
            st.warning(credit_message)
        else:
            st.info(credit_message)
        engine_label = "Offline rules + managed AI QA" if using_managed_ai else "Offline rules only"
        st.info(f"Engine: {engine_label}. API availability does not block offline QA; app credits still apply.")

        if run_rules:
            status.text("Running deterministic checks...")
            for idx, seg in enumerate(segments, start=1):
                report_rows.extend(deterministic_checks(seg, rules, enable_zwnj=run_zwnj))
                progress.progress(min(idx / max(len(segments), 1) * 0.35, 0.35))

        if tm_controls.get("use"):
            status.text("Checking secure translation memory...")
            tm_rows = tm_qa_memory_report_rows(user_id, segments, tm_controls["target_language"], tm_controls["client_key"])
            if tm_rows:
                st.info(f"Secure Translation Memory found {len(tm_rows)} exact-match suggestion(s).")
            report_rows.extend(tm_rows)

        if using_managed_ai:
            status.text("Running AI QA suggestions...")
            total_batches = max(1, (len(segments) + int(settings["batch_size"]) - 1) // int(settings["batch_size"]))
            for b in range(total_batches):
                batch = segments[b * int(settings["batch_size"]):(b + 1) * int(settings["batch_size"])]
                status.text(f"AI QA batch {b + 1}/{total_batches}...")
                report_rows.extend(ai_qa_batch(openai_client, settings["openai_model"], batch, rules, settings["domain"], settings["strictness"], include_ai_style))
                progress.progress(0.35 + ((b + 1) / total_batches) * 0.60)

        report_rows, dropped_ai_rows = post_filter_report_rows(report_rows, include_ai_style)
        report_rows = apply_quality_gate(report_rows)
        if dropped_ai_rows:
            st.info(f"Filtered {dropped_ai_rows} low-confidence or subjective AI suggestion(s).")

        progress.progress(1.0)
        status.text(f"QA complete in {round(time.time() - start, 2)} seconds.")

        if lower.endswith(".xlsx") and workbook is not None:
            if output_highlighted:
                highlight_excel_cells(cell_map, report_rows)
            issue_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation", "Check Source", "Rule Source", "Confidence", "Quality Gate", "Action Required", "Score Impact"]
            status_rows = build_segment_status_rows(segments, report_rows, checked_by="Rule Engine + AI QA")
            status_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Review Status", "Issue Count", "Confirmed Error Count", "Needs Review Count", "Highest Severity", "Quality Gate Types", "Error Types", "Suggestion Summary", "Explanation Summary", "Checked By"]
            add_report_sheet_to_workbook(workbook, "All Segment Review", status_rows, status_headers)
            add_report_sheet_to_workbook(workbook, "ErrorSweep Report", report_rows, issue_headers)
            bio = io.BytesIO()
            workbook.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_reviewed_" + uploaded_file.name
        else:
            status_rows = build_segment_status_rows(segments, report_rows, checked_by="Rule Engine + AI QA")
            output_bytes = build_excel_report_bytes(
                issue_rows=report_rows,
                status_rows=status_rows,
                extraction_logs=logs,
                title="ErrorSweep QA Report",
            )
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_review_report_" + re.sub(r"\.[^.]+$", ".xlsx", uploaded_file.name)

        refreshed_profile = profile
        charge_ok, charge_msg, refreshed_profile = consume_user_credits(
            user_id=user_id,
            credits=credits_needed,
            workflow="qa",
            file_name=uploaded_file.name,
            segment_count=len(segments),
            metadata={
                "issues": len(report_rows),
                "rules_zip": bool(rules_zip),
                "engine": "managed_ai" if using_managed_ai else "offline_rules",
                "api_used": bool(using_managed_ai),
            },
        )
        if not charge_ok:
            st.error(f"Could not deduct app credits, so the report cannot be released. {charge_msg}")
            st.stop()
        if refreshed_profile:
            st.session_state["sb_profile"] = refreshed_profile
        st.success(f"App credits charged: {credits_needed}. Remaining credits: {remaining_credits(refreshed_profile or profile)}")
        if tm_controls.get("save"):
            saved_tm = tm_save_passed_qa_segments(
                user_id,
                segments,
                report_rows,
                tm_controls["target_language"],
                tm_controls["client_key"],
                domain=settings.get("domain", ""),
            )
            if saved_tm:
                st.success(f"Saved {saved_tm} approved/pass segment(s) to encrypted Translation Memory.")
            elif tm_secret_configured():
                st.info("No pass segments were saved to Translation Memory for this run.")
        log_report_record(user_id, "qa", uploaded_file.name, len(segments), len(report_rows), output_name, credits_needed)

        status_rows_for_ui = build_segment_status_rows(segments, report_rows, checked_by="Rule Engine + AI QA")
        render_quality_gate_summary(report_rows, status_rows_for_ui)
        st.markdown("### Segment Coverage")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Segments checked", len(status_rows_for_ui))
        c2.metric("Blocked", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Blocked"))
        c3.metric("Needs Review", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Needs Review"))
        c4.metric("Passed", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Pass"))
        with st.expander("All Segment Review Preview", expanded=False):
            st.dataframe(pd.DataFrame(status_rows_for_ui).head(200), use_container_width=True, hide_index=True)
        render_report(report_rows, "ErrorSweep QA Report")
        st.download_button("Download ErrorSweep Output", output_bytes, file_name=output_name, mime=mime_type, use_container_width=True)
        st.download_button(
            "Download Excel QA Report",
            build_excel_report_bytes(report_rows, status_rows_for_ui, extraction_logs=logs, title="ErrorSweep QA Report"),
            file_name="errorsweep_qa_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_errorsweep_pro_page(user_id: str, profile: Optional[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    render_workflow_hero(
        "ErrorSweep Pro — Translate + Review",
        "Upload a source file, choose target language, add optional client rules, and export translated output in the same format.",
        "pro",
    )
    openai_client = get_openai_client()
    gemini_client = get_gemini_client()
    render_engine_status_cards("pro", openai_client=openai_client, gemini_client=gemini_client)
    settings = render_inline_workflow_settings("pro")

    if openai_client is None and not has_local_translation_engine(settings.get("target_language", "")):
        st.info("No language engine is configured. ErrorSweep Pro will use Offline Reference Mode only. It can reuse saved Translation Memory and uploaded glossary/rule-pack matches, but it cannot create full new professional translations without a user API key, managed engine, or self-hosted translation engine. App credits still apply to outputs.")
    elif openai_client is None and has_local_translation_engine(settings.get("target_language", "")):
        st.info("Self-hosted translation engine is configured. ErrorSweep Pro will use Translation Memory first, then the routed local engine for unmatched segments.")

    uploaded_file, rules_zip, rules = render_rule_upload("pro", user_id=user_id, workflow_type="pro")

    target_language = settings.get("target_language", "")
    render_translation_route_status(target_language, openai_client=openai_client, gemini_client=gemini_client)
    tm_controls = render_translation_memory_controls("pro", default_target_language=target_language)
    history_corrections = load_correction_history_as_rules(
        user_id,
        client_key=tm_controls.get("client_key", "global"),
        target_language=tm_controls.get("target_language", target_language),
        domain=settings.get("domain", ""),
    )
    if history_corrections:
        rules.setdefault("corrections", [])
        rules["corrections"].extend(history_corrections)
        st.info(f"Loaded {len(history_corrections)} correction-history rule(s) for Pro review.")


    st.markdown("### Run")
    review_with_gemini = bool(gemini_client)
    apply_gemini_suggestions = False
    with st.expander("Advanced Pro run options", expanded=False):
        p1, p2 = st.columns(2)
        with p1:
            review_with_gemini = st.checkbox("Run independent review", value=bool(gemini_client), key="pro_review", disabled=not bool(gemini_client))
        with p2:
            apply_gemini_suggestions = st.checkbox("Apply reviewer suggestions to final output", value=False, key="pro_apply_review")
        st.markdown("<div class='es-soft-card'><p>Independent review is useful for delivery quality. Keep automatic application OFF unless you trust the reviewer output.</p></div>", unsafe_allow_html=True)

    run_pro = st.button("Run Translate + Review", type="primary", use_container_width=True, disabled=not uploaded_file, key="run_pro_no_sidebar")

    if uploaded_file and run_pro:
        using_language_engine = bool(openai_client or can_use_local_translation_engine(target_language))
        if not using_language_engine:
            st.warning("Offline Reference Mode is active. The app will preserve the file format and apply saved memory/glossary/DNT references where possible. New unmatched source segments will be left blank or marked for translation instead of fake-translated. Full professional translation requires a user API key, managed engine, or self-hosted translation engine. App credits still apply.")
            review_with_gemini = False
        if review_with_gemini and gemini_client is None:
            st.warning("Independent review service is not configured. Independent review will be skipped; deterministic review still runs.")
            review_with_gemini = False
        if not target_language.strip() or target_language.strip().lower() in {"auto", "auto-detect", "autodetect"}:
            st.error("Please enter a real target language before running Pro. Example: Spanish, French, Hindi, Arabic, ja-JP.")
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
        json_obj = None
        json_path_map = {}
        xml_tree = None
        xml_target_map = {}
        xlz_package = None
        xlz_target_map = {}
        srt_line_map = {}
        cell_map = {}
        translation_col_map = {}
        para_map = {}

        file_bytes = uploaded_file_bytes(uploaded_file)
        if lower.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")) or is_openpyxl_compatible(file_bytes):
            workbook, segments, cell_map, translation_col_map, logs = extract_excel_segments(
                io.BytesIO(file_bytes), settings["source_col_hint"], settings["target_col_hint"], "pro", int(settings["max_segments"]), settings["skip_non_content"], settings["deep_scan"]
            )
        elif lower.endswith(".csv"):
            dataframe, segments, logs = extract_csv_segments(uploaded_file, settings["source_col_hint"], settings["target_col_hint"], "pro", int(settings["max_segments"]), settings["deep_scan"])
        elif lower.endswith(".docx"):
            doc, segments, para_map, logs = extract_docx_segments(uploaded_file, "pro", int(settings["max_segments"]), settings["source_col_hint"], settings["target_col_hint"])
        elif lower.endswith(".json"):
            json_obj, segments, json_path_map, logs = extract_json_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith(".xlz"):
            xlz_package, segments, xlz_target_map, logs = extract_xlz_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith((".xml", ".xliff", ".xlf", ".sdlxliff", ".mqxliff")):
            xml_tree, segments, xml_target_map, logs = extract_xml_xliff_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith(".srt"):
            text_original, segments, srt_line_map, logs = extract_srt_pro_segments(uploaded_file, int(settings["max_segments"]))
        elif lower.endswith(".pdf"):
            segments, logs = extract_pdf_segments(uploaded_file, "pro", int(settings["max_segments"]))
        else:
            text_original, segments, logs = extract_text_segments(uploaded_file, "pro", int(settings["max_segments"]))

        with st.expander("Extraction log", expanded=True):
            for log in logs:
                st.write(log)
            st.info(f"Found {len(segments)} segment(s) for translation. Full-file mode is {'ON' if settings['check_whole_file'] else 'OFF'}.")

        if not segments:
            st.error("No source segments found. Use the settings panel on this page to set the source column name/index.")
            st.stop()

        # App credits are required for every Pro output, even in Offline Reference Mode.
        # If API/language-engine credits are unavailable, ErrorSweep Pro can still create a same-format
        # reference-assisted output, but users must still spend app credits to receive that output.
        using_managed_pro_engine = bool(openai_client or can_use_local_translation_engine(target_language) or (review_with_gemini and gemini_client))
        segments, credits_needed, credit_message = maybe_limit_segments_to_available_credits(
            segments, profile, "pro", rules_zip_used=bool(rules_zip), independent_review=bool(review_with_gemini)
        )
        if not segments:
            st.error(f"{credit_message} App credits are required for ErrorSweep Pro outputs, including Offline Reference Mode.")
            st.stop()
        if "Not enough credits" in credit_message:
            st.warning(credit_message)
        else:
            st.info(credit_message)
        if openai_client:
            engine_label = "Language engine"
        elif can_use_local_translation_engine(target_language):
            engine_label = f"Self-hosted translation engine ({get_translation_engine_config(target_language).get('label', 'local')})"
        else:
            engine_label = "Offline Reference Mode"
        st.info(f"Engine: {engine_label}. API availability does not block reference-mode output; app credits still apply.")

        status.text("Preparing translations...")
        translations_by_loc: Dict[str, str] = {}
        active_tm_target_language = target_language.strip()
        if tm_controls.get("use"):
            # Important: Pro Translation Memory must follow the selected target language.
            # This prevents old Telugu memory from being reused during a French run.
            tm_matches = tm_batch_lookup(user_id, segments, active_tm_target_language, tm_controls["client_key"])
            tm_matches, dropped_wrong_lang = filter_tm_matches_for_target_language(tm_matches, active_tm_target_language)
            for loc, match in tm_matches.items():
                translations_by_loc[loc] = match.get("translation", "")
            if tm_matches:
                st.success(f"Reused {len(tm_matches)} exact saved {active_tm_target_language} translation(s) from encrypted Translation Memory.")
            if dropped_wrong_lang:
                st.warning(f"Ignored {dropped_wrong_lang} Translation Memory match(es) because they did not look like {active_tm_target_language}. They will be retranslated by the selected engine.")

        engine_segments = [seg for seg in segments if seg.get("location") not in translations_by_loc]
        if engine_segments and not openai_client:
            engine_ok, engine_msg = translation_engine_live_preflight(target_language)
            if not engine_ok:
                st.error(
                    f"Translation engine is not ready for {target_language}. "
                    f"{engine_msg} {len(engine_segments)} segment(s) still need machine translation. "
                    "ErrorSweep Pro will not create a blank/placeholder-only output."
                )
                st.stop()
            st.success(f"Translation engine preflight passed: {engine_msg}")
        if engine_segments:
            status.text("Translating remaining segments...")
            total_batches = max(1, (len(engine_segments) + int(settings["batch_size"]) - 1) // int(settings["batch_size"]))
            for b in range(total_batches):
                batch = engine_segments[b * int(settings["batch_size"]):(b + 1) * int(settings["batch_size"])]
                status.text(f"Translation batch {b + 1}/{total_batches}...")
                if openai_client:
                    result = openai_translate_batch(openai_client, settings["openai_model"], batch, target_language, settings["domain"], rules)
                elif can_use_local_translation_engine(target_language):
                    result = local_translate_batch_adapter(batch, target_language, settings["domain"])
                else:
                    result = offline_reference_translate_batch(batch, target_language, rules)
                for item in result:
                    loc = item.get("location", "")
                    trans = item.get("translation", "")
                    if loc is not None:
                        original_seg = next((s for s in batch if str(s.get("location", "")) == str(loc)), {"source": ""})
                        translations_by_loc[loc] = restore_translation_item(original_seg, trans or "")
                progress.progress(((b + 1) / total_batches) * 0.45)
        else:
            progress.progress(0.45)

        # Block bad Pro outputs: after engine/TM/reference pass, every non-empty source must have a translation.
        missing_after_translation = missing_translation_segments(segments, translations_by_loc)
        if missing_after_translation:
            st.error(
                f"Translation coverage failed: {len(missing_after_translation)} segment(s) are still blank. "
                "Download is blocked to avoid delivering an incomplete translated file. "
                "Check that the selected target language is supported and the local translation engine is running."
            )
            with st.expander("Missing translation locations", expanded=True):
                st.dataframe(pd.DataFrame([{
                    "Location": s.get("location", ""),
                    "Source": truncate(s.get("source") or s.get("text") or "", 300),
                } for s in missing_after_translation[:200]]), use_container_width=True, hide_index=True)
            st.stop()

        translated_segments = []
        for seg in segments:
            loc = seg["location"]
            trans = translations_by_loc.get(loc, "")
            translated_segments.append({**seg, "translation": trans, "text": trans})

        review_rows: List[Dict[str, Any]] = []
        status.text("Running deterministic review...")
        for idx, seg in enumerate(translated_segments, start=1):
            review_rows.extend(deterministic_checks(seg, rules, enable_zwnj=True))
            progress.progress(0.45 + (idx / max(len(translated_segments), 1)) * 0.15)
        if not openai_client:
            review_rows.extend(build_offline_translation_review_rows(segments, translations_by_loc))

        if review_with_gemini:
            status.text("Running independent review...")
            total_review_batches = max(1, (len(translated_segments) + int(settings["batch_size"]) - 1) // int(settings["batch_size"]))
            for b in range(total_review_batches):
                batch = translated_segments[b * int(settings["batch_size"]):(b + 1) * int(settings["batch_size"])]
                status.text(f"Review batch {b + 1}/{total_review_batches}...")
                gemini_errors = gemini_review_translations(gemini_client, settings["gemini_model"], batch, target_language, settings["domain"], rules)
                loc_to_seg = {s["location"]: s for s in batch}
                for err in gemini_errors:
                    loc = err.get("location", "")
                    seg = loc_to_seg.get(loc, {"location": loc, "source": "", "translation": "", "sheet": ""})
                    review_rows.append(make_report_row(
                        seg,
                        err.get("error_type", "Independent Review"),
                        err.get("severity", "Review"),
                        err.get("wrong_part", ""),
                        err.get("suggestion", ""),
                        err.get("explanation", ""),
                        "Independent Review",
                        "Reviewer",
                        err.get("confidence", "Medium"),
                    ))
                    if apply_gemini_suggestions and err.get("suggestion") and loc in translations_by_loc:
                        translations_by_loc[loc] = err["suggestion"]
                progress.progress(0.60 + ((b + 1) / total_review_batches) * 0.35)

        review_rows = apply_quality_gate(review_rows)

        status.text("Building output file...")
        output_bytes = b""
        output_name = "errorsweep_pro_" + uploaded_file.name
        mime_type = "text/csv"

        if lower.endswith(".xlsx") and workbook is not None:
            for seg in segments:
                loc = seg["location"]
                if loc in translation_col_map:
                    ws_name, row_num, col_idx = translation_col_map[loc]
                    if col_idx is None:
                        continue
                    workbook[ws_name].cell(row=row_num, column=col_idx + 1).value = translations_by_loc.get(loc, "")
            highlight_excel_cells(cell_map, review_rows)
            issue_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Error Type", "Severity", "Wrong Part", "Suggestion", "Explanation", "Check Source", "Rule Source", "Confidence", "Quality Gate", "Action Required", "Score Impact"]
            status_rows = build_segment_status_rows(translated_segments, review_rows, checked_by="Rules + Independent Review")
            status_headers = ["Sheet", "Location", "Mode", "Source Text", "Translation", "Review Status", "Issue Count", "Confirmed Error Count", "Needs Review Count", "Highest Severity", "Quality Gate Types", "Error Types", "Suggestion Summary", "Explanation Summary", "Checked By"]
            add_report_sheet_to_workbook(workbook, "All Segment Review", status_rows, status_headers)
            add_report_sheet_to_workbook(workbook, "ErrorSweep Pro Review", review_rows, issue_headers)
            bio = io.BytesIO()
            workbook.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".csv") and dataframe is not None:
            out_col = "AI Translation"
            if "AI Translation" not in dataframe.columns:
                dataframe[out_col] = ""
            for seg in segments:
                dataframe.at[seg["row"], out_col] = translations_by_loc.get(seg["location"], "")
            output_bytes = dataframe.to_csv(index=False).encode("utf-8-sig")
            mime_type = "text/csv"
            output_name = "errorsweep_pro_translated_" + re.sub(r"\.[^.]+$", ".csv", uploaded_file.name)
        elif lower.endswith(".docx") and doc is not None:
            for seg in segments:
                target_info = para_map.get(seg["location"])
                write_docx_translation_target(target_info, translations_by_loc.get(seg["location"], ""))
            bio = io.BytesIO()
            doc.save(bio)
            bio.seek(0)
            output_bytes = bio.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".json") and json_obj is not None:
            output_bytes = build_translated_json_bytes(json_obj, json_path_map, translations_by_loc)
            mime_type = "application/json"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".xlz") and xlz_package is not None:
            output_bytes = build_translated_xlz_bytes(xlz_package, xlz_target_map, translations_by_loc)
            mime_type = "application/zip"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith((".xml", ".xliff", ".xlf", ".sdlxliff", ".mqxliff")) and xml_tree is not None:
            output_bytes = build_translated_xml_bytes(xml_tree, xml_target_map, translations_by_loc)
            mime_type = "application/xml"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif lower.endswith(".srt") and text_original is not None:
            output_bytes = build_translated_srt_bytes(text_original, srt_line_map, translations_by_loc)
            mime_type = "text/plain"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        elif is_text_like_extension(uploaded_file.name) and text_original is not None:
            output_bytes = build_preserved_text_translation(text_original, segments, translations_by_loc)
            mime_type = "text/plain"
            output_name = "errorsweep_pro_translated_" + uploaded_file.name
        else:
            # For PDFs and truly unknown/binary formats, safely return an Excel translation table.
            # Rebuilding a binary/PDF in the exact same format requires a dedicated renderer and is not safe to fake.
            table = []
            for seg in segments:
                table.append({"Location": seg["location"], "Source": seg.get("source") or seg.get("text", ""), "Translation": translations_by_loc.get(seg["location"], "")})
            output_bytes = build_excel_report_bytes(
                issue_rows=[],
                status_rows=[],
                extraction_logs=logs + ["Exact same-format rebuild is unavailable for this file type; returned an Excel translation table instead."],
                translation_rows=table,
                title="ErrorSweep Pro Translations",
            )
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            output_name = "errorsweep_pro_translations_" + re.sub(r"\.[^.]+$", ".xlsx", uploaded_file.name)

        progress.progress(1.0)
        status.text(f"Pro workflow complete in {round(time.time() - start, 2)} seconds.")

        refreshed_profile = profile
        charge_ok, charge_msg, refreshed_profile = consume_user_credits(
            user_id=user_id,
            credits=credits_needed,
            workflow="pro",
            file_name=uploaded_file.name,
            segment_count=len(segments),
            metadata={
                "review_issues": len(review_rows),
                "rules_zip": bool(rules_zip),
                "independent_review": bool(review_with_gemini),
                "engine": "managed_ai" if using_managed_pro_engine else "offline_reference",
                "api_used": bool(using_managed_pro_engine),
            },
        )
        if not charge_ok:
            st.error(f"Could not deduct app credits, so the output cannot be released. {charge_msg}")
            st.stop()
        if refreshed_profile:
            st.session_state["sb_profile"] = refreshed_profile
        st.success(f"App credits charged: {credits_needed}. Remaining credits: {remaining_credits(refreshed_profile or profile)}")
        if tm_controls.get("save"):
            saved_tm = tm_save_pro_translations(
                user_id,
                translated_segments,
                review_rows,
                target_language.strip(),
                tm_controls["client_key"],
                domain=settings.get("domain", ""),
            )
            if saved_tm:
                st.success(f"Saved {saved_tm} reviewed/pass {target_language.strip()} translation(s) to encrypted Translation Memory.")
            elif tm_secret_configured():
                st.info("No reviewed/pass translations were saved to Translation Memory for this run.")
        log_report_record(user_id, "pro", uploaded_file.name, len(segments), len(review_rows), output_name, credits_needed)

        st.markdown("### Translation Preview")
        preview = []
        for seg in translated_segments[:50]:
            preview.append({"Location": seg["location"], "Source": truncate(seg.get("source") or seg.get("text", ""), 300), "Translation": truncate(translations_by_loc.get(seg["location"], ""), 300)})
        st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

        status_rows_for_ui = build_segment_status_rows(translated_segments, review_rows, checked_by="Rules + Independent Review")
        st.markdown("### Segment Coverage")
        c1, c2, c3 = st.columns(3)
        c1.metric("Segments translated/reviewed", len(status_rows_for_ui))
        c2.metric("Segments with issues", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Needs Review"))
        c3.metric("Segments passed", sum(1 for r in status_rows_for_ui if r.get("Review Status") == "Pass"))
        with st.expander("All Segment Review Preview", expanded=False):
            st.dataframe(pd.DataFrame(status_rows_for_ui).head(200), use_container_width=True, hide_index=True)

        render_report(review_rows, "Independent Review Report")
        st.download_button("Download Translated Output", output_bytes, file_name=output_name, mime=mime_type, use_container_width=True)
        translation_rows_for_report = [
            {
                "Location": seg["location"],
                "Source": truncate(seg.get("source") or seg.get("text", ""), 1000),
                "Translation": truncate(translations_by_loc.get(seg["location"], ""), 1000),
            }
            for seg in translated_segments
        ]
        st.download_button(
            "Download Excel Translation + Review Report",
            build_excel_report_bytes(
                issue_rows=review_rows,
                status_rows=status_rows_for_ui,
                extraction_logs=logs,
                translation_rows=translation_rows_for_report,
                title="ErrorSweep Pro Translation + Review Report",
            ),
            file_name="errorsweep_pro_excel_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_admin_page(profile: Optional[Dict[str, Any]]) -> None:
    st.markdown("## Admin — User Management")
    st.caption("Manage users, plans, credits, and recent jobs. This page is visible only to emails listed in ERRORSWEEP_ADMIN_EMAILS.")

    if not is_admin_user():
        st.error("You do not have admin access.")
        return

    if not supabase_service_configured():
        st.error("Supabase service role is not configured. Add SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets.")
        return

    summary = admin_usage_summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users", summary["users"])
    c2.metric("Recent Jobs", summary["jobs"])
    c3.metric("Credits Used", summary["credits_used"])
    c4.metric("Credits Allocated", summary["credits_allocated"])

    st.divider()
    st.markdown("### Find user")
    search_email = st.text_input("Search by email", placeholder="user@example.com")
    profiles = admin_list_profiles(search_email, limit=50)

    if profiles:
        display_df = pd.DataFrame(profiles)
        preferred_cols = ["email", "plan", "monthly_credits", "used_credits", "total_files_processed", "created_at", "id"]
        cols = [col for col in preferred_cols if col in display_df.columns]
        st.dataframe(display_df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("No users found for the current search.")

    st.divider()
    st.markdown("### Upgrade / adjust credits")
    with st.form("admin_update_user_form"):
        target_email = st.text_input("User email to update", value=search_email or "")
        new_plan = st.selectbox("Plan", ["trial", "errorsweep", "pro", "agency", "enterprise"], index=2)
        monthly_credits = st.number_input("Monthly credits", min_value=0, max_value=1000000, value=600, step=25)
        used_credits = st.number_input("Used credits", min_value=0, max_value=1000000, value=0, step=1)
        reset_used = st.checkbox("Reset used credits to 0", value=True)
        submitted = st.form_submit_button("Update user", type="primary", use_container_width=True)

    if submitted:
        target = admin_get_profile_by_email(target_email)
        if not target:
            st.error("User profile not found. Ask the user to sign up/login once, then try again.")
        else:
            updates = {
                "plan": new_plan,
                "monthly_credits": int(monthly_credits),
                "used_credits": 0 if reset_used else int(used_credits),
            }
            ok, msg, refreshed = admin_update_profile(target["id"], updates)
            if ok:
                st.success(msg)
                if refreshed:
                    st.json({k: refreshed.get(k) for k in ["email", "plan", "monthly_credits", "used_credits"]})
            else:
                st.error(msg)

    st.divider()
    st.markdown("### Add bonus credits")
    with st.form("admin_bonus_credits_form"):
        bonus_email = st.text_input("User email", key="bonus_email")
        bonus = st.number_input("Bonus credits to add to monthly credits", min_value=1, max_value=100000, value=100, step=10)
        bonus_submit = st.form_submit_button("Add bonus credits", use_container_width=True)

    if bonus_submit:
        target = admin_get_profile_by_email(bonus_email)
        if not target:
            st.error("User profile not found.")
        else:
            new_monthly = int(target.get("monthly_credits") or 0) + int(bonus)
            ok, msg, refreshed = admin_update_profile(target["id"], {"monthly_credits": new_monthly})
            if ok:
                st.success(f"Added {bonus} credits. New monthly credits: {new_monthly}")
            else:
                st.error(msg)

    st.divider()
    st.markdown("### Job history")
    job_email = st.text_input("Filter jobs by user email", value=search_email or "", key="job_email_filter")
    job_user_id = None
    if job_email.strip():
        target = admin_get_profile_by_email(job_email)
        if target:
            job_user_id = target.get("id")
    jobs = admin_list_jobs(user_id=job_user_id, limit=100)
    if jobs:
        st.dataframe(pd.DataFrame(jobs), use_container_width=True, hide_index=True)
    else:
        st.info("No jobs found.")

    st.divider()
    st.markdown("### Payment events")
    payment_filter = st.text_input("Filter payment events by email", value=search_email or "", key="admin_payment_filter")
    payment_events = admin_list_payment_events(limit=100, email_filter=payment_filter)
    if payment_events:
        st.dataframe(format_payment_events_for_display(payment_events), use_container_width=True, hide_index=True)
        processed_count = sum(1 for e in payment_events if e.get("processed"))
        p1, p2, p3 = st.columns(3)
        p1.metric("Events", len(payment_events))
        p2.metric("Processed", processed_count)
        p3.metric("Pending / Failed", len(payment_events) - processed_count)
    else:
        st.info("No payment events found. If payment webhook is configured, successful payment events will appear here.")

    st.divider()
    st.markdown("### Master access reminder")
    st.code('ERRORSWEEP_ADMIN_EMAILS = "your-email@example.com,adapalanaveen401@gmail.com"', language="toml")


def render_dashboard() -> None:
    init_page_state()
    user = get_current_user()
    user_id = user.get("id")
    profile = ensure_profile(user)
    if profile:
        st.session_state["sb_profile"] = profile

    render_top_account_bar(profile)
    page = render_top_nav()
    settings = get_page_settings()

    if page == "Dashboard":
        render_dashboard_page(user_id, profile, settings)
    elif page == "ErrorSweep":
        render_errorsweep_page(user_id, profile, settings)
    elif page == "ErrorSweep Pro":
        render_errorsweep_pro_page(user_id, profile, settings)
    elif page == "Memory & Rules":
        render_memory_rulepacks_page(user_id, profile)
    elif page == "Billing":
        render_billing_page(profile)
    elif page == "Account":
        render_account_page(profile)
    elif page == "Admin":
        render_admin_page(profile)


if not is_authenticated():
    render_login_page()
else:
    render_dashboard()