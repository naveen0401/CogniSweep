
"""
CogniSweep QA Engine v2
-----------------------
Modular, source-driven offline QA rule engine.

This module is designed to sit beside the Streamlit app. It does not replace
file extraction/output. It only receives segment dictionaries and returns
report rows compatible with the existing CogniSweep report schema.

Segment contract:
{
    "source": "...",
    "translation": "...",
    "text": "...",
    "location": "...",
    "sheet": "...",
    "file_type": "...",
    "mode": "...",
}

Client rules contract:
{
    "glossary": [{"source_term": "...", "target_term": "...", "source": "..."}],
    "dnt": [{"term": "...", "source": "..."}],
    "chunks": [...]
}
"""

from __future__ import annotations

import json
import re
import logging
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple
from functools import lru_cache

import requests

LOGGER = logging.getLogger(__name__)

try:
    import language_tool_python
except ImportError as exc:
    LOGGER.debug("language_tool_python is unavailable: %s", exc)
    language_tool_python = None

# ==========================================================
# NORMALIZATION + SCRIPT UTILITIES
# ==========================================================

ZWNJ = "\u200c"
ZWJ = "\u200d"
ZWSP = "\u200b"
NBSP = "\u00a0"

TELUGU_RE = re.compile(r"[\u0C00-\u0C7F]")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
CJK_RE = re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]")
BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
GURMUKHI_RE = re.compile(r"[\u0A00-\u0A7F]")
GUJARATI_RE = re.compile(r"[\u0A80-\u0AFF]")
ODIA_RE = re.compile(r"[\u0B00-\u0B7F]")
TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
KANNADA_RE = re.compile(r"[\u0C80-\u0CFF]")
MALAYALAM_RE = re.compile(r"[\u0D00-\u0D7F]")
SINHALA_RE = re.compile(r"[\u0D80-\u0DFF]")
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
LAO_RE = re.compile(r"[\u0E80-\u0EFF]")
KHMER_RE = re.compile(r"[\u1780-\u17FF]")
MYANMAR_RE = re.compile(r"[\u1000-\u109F]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
GREEK_RE = re.compile(r"[\u0370-\u03FF]")
ETHIOPIC_RE = re.compile(r"[\u1200-\u137F]")
LATIN_RE = re.compile(r"[A-Za-z]")

URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
TAG_RE = re.compile(r"<[^>]+>")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]\ufe0f?")
PLACEHOLDER_RE = re.compile(
    r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|\b\w+_id\b|<[^>]+>)"
)
NUMBER_RE = re.compile(r"\d+(?:[.,:/-]\d+)*")
SKU_RE = re.compile(r"\b[A-Z]{2,}[-_][A-Z0-9][A-Z0-9_-]*\b|\b[A-Z0-9]{4,}-[A-Z0-9-]{2,}\b")


def normalize_for_qa(text: Any) -> str:
    """Normalize safely for QA without deleting ZWNJ.

    We normalize compatibility characters and common whitespace while preserving
    ZWNJ because it is meaningful for Indic scripts.
    """
    if text is None:
        return ""
    value = str(text)
    value = unicodedata.normalize("NFC", value)
    value = value.replace(NBSP, " ")
    value = value.replace(ZWSP, "")
    # Keep ZWNJ and ZWJ visible to rules.
    return value.strip("\r\n")


def compact_space(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def visible_invisibles(text: Any) -> str:
    value = "" if text is None else str(text)
    return (
        value.replace(ZWSP, "")
        .replace(NBSP, " ")
        .replace(ZWJ, "")
    )


def has_telugu(text: str) -> bool:
    return bool(TELUGU_RE.search(text or ""))


def has_devanagari(text: str) -> bool:
    return bool(DEVANAGARI_RE.search(text or ""))


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def infer_language_module(target_language: str, source: str, target: str) -> str:
    """Infer a broad script/language module from UI selection and target text.

    Returns a module name used for offline rules. This is intentionally broad:
    exact grammar checks are left to client rules / AI / future local ML.
    """
    lang = (target_language or "").strip().lower()
    target = target or ""

    if any(x in lang for x in ["telugu", "te-", "tel"]) or lang in {"te", "tel"} or has_telugu(target):
        return "telugu"

    if any(x in lang for x in ["hindi", "marathi", "nepali", "sanskrit", "devanagari"]) or lang in {"hi", "mr", "ne", "sa"} or has_devanagari(target):
        return "devanagari"

    if any(x in lang for x in ["bengali", "bangla", "assamese"]) or lang in {"bn", "as"} or BENGALI_RE.search(target):
        return "bengali"
    if "punjabi" in lang or "gurmukhi" in lang or lang == "pa" or GURMUKHI_RE.search(target):
        return "gurmukhi"
    if "gujarati" in lang or lang == "gu" or GUJARATI_RE.search(target):
        return "gujarati"
    if any(x in lang for x in ["odia", "oriya"]) or lang == "or" or ODIA_RE.search(target):
        return "odia"
    if "tamil" in lang or lang == "ta" or TAMIL_RE.search(target):
        return "tamil"
    if "kannada" in lang or lang == "kn" or KANNADA_RE.search(target):
        return "kannada"
    if "malayalam" in lang or lang == "ml" or MALAYALAM_RE.search(target):
        return "malayalam"
    if "sinhala" in lang or lang == "si" or SINHALA_RE.search(target):
        return "sinhala"
    if "hausa" in lang or lang.startswith("ha"):
        return "hausa"

    if any(x in lang for x in ["arabic", "urdu", "persian", "farsi"]) or lang in {"ar", "ur", "fa"} or ARABIC_RE.search(target):
        return "arabic"
    if "hebrew" in lang or lang == "he" or HEBREW_RE.search(target):
        return "hebrew"

    if "lao" in lang or lang == "lo":
        return "lao"
    if "khmer" in lang or "cambodian" in lang or lang == "km":
        return "khmer"
    if "myanmar" in lang or "burmese" in lang or lang == "my":
        return "myanmar"
    if any(x in lang for x in ["thai"]) or lang == "th" or THAI_RE.search(target):
        return "thai"
    if LAO_RE.search(target):
        return "lao"
    if KHMER_RE.search(target):
        return "khmer"
    if MYANMAR_RE.search(target):
        return "myanmar"

    if any(x in lang for x in ["chinese", "japanese", "korean", "cjk", "mandarin", "cantonese"]) or lang in {"zh", "ja", "ko"} or has_cjk(target):
        if "japanese" in lang or lang == "ja" or re.search(r"[\u3040-\u30FF]", target):
            return "japanese"
        if "korean" in lang or lang == "ko" or re.search(r"[\uAC00-\uD7AF]", target):
            return "korean"
        return "cjk"

    if "mongolian" in lang or lang == "mn":
        return "mongolian"

    if any(x in lang for x in ["russian", "ukrainian", "bulgarian", "serbian", "macedonian", "cyrillic"]) or lang in {"ru", "uk", "bg", "sr", "mk"} or CYRILLIC_RE.search(target):
        return "cyrillic"
    if "greek" in lang or lang == "el" or GREEK_RE.search(target):
        return "greek"
    if "amharic" in lang or lang == "am" or ETHIOPIC_RE.search(target):
        return "amharic"

    if "french" in lang or lang.startswith("fr"):
        return "french"
    if "spanish" in lang or lang.startswith("es"):
        return "spanish"
    if "german" in lang or lang.startswith("de"):
        return "german"
    if "italian" in lang or lang.startswith("it"):
        return "italian"
    if "portuguese" in lang or lang.startswith("pt"):
        return "portuguese"
    if "dutch" in lang or lang.startswith("nl"):
        return "dutch"
    if any(x in lang for x in ["swedish", "norwegian", "danish", "nordic"]) or lang.startswith(("sv", "no", "nb", "nn", "da")):
        return "nordic"
    if "polish" in lang or lang.startswith("pl"):
        return "polish"
    if "english" in lang or lang.startswith("en") or "uk english" in lang or "us english" in lang:
        return "english"
    if "turkish" in lang or lang.startswith("tr"):
        return "turkish"
    if "swahili" in lang or "kiswahili" in lang or lang.startswith("sw"):
        return "swahili"
    if "indonesian" in lang or "bahasa indonesia" in lang or lang in {"id", "id-id"}:
        return "indonesian"
    if "malay" in lang or "bahasa melayu" in lang or lang in {"ms", "ms-my"}:
        return "malay"
    if "tagalog" in lang or "filipino" in lang or lang in {"tl", "fil"}:
        return "tagalog"
    if "yoruba" in lang or lang.startswith("yo"):
        return "yoruba"
    if "zulu" in lang or "isizulu" in lang or lang.startswith("zu"):
        return "zulu"
    if "afrikaans" in lang or lang.startswith("af"):
        return "afrikaans"
    if "vietnamese" in lang or lang.startswith("vi"):
        return "vietnamese"

    return "global"

def extract_placeholders(text: str) -> List[str]:
    return PLACEHOLDER_RE.findall(text or "")


def extract_numbers(text: str) -> List[str]:
    return NUMBER_RE.findall(text or "")


def extract_urls(text: str) -> List[str]:
    return URL_RE.findall(text or "")


def extract_emails(text: str) -> List[str]:
    return EMAIL_RE.findall(text or "")


def extract_tags(text: str) -> List[str]:
    return TAG_RE.findall(text or "")


def extract_emoji(text: str) -> List[str]:
    return EMOJI_RE.findall(text or "")


def extract_skus(text: str) -> List[str]:
    return SKU_RE.findall(text or "")


def protected_terms_from_rules(rules: Dict[str, Any]) -> List[str]:
    protected: List[str] = []
    for item in (rules or {}).get("dnt", []):
        term = normalize_for_qa(item.get("term", ""))
        if term:
            protected.append(term)
    for item in (rules or {}).get("glossary", []):
        src = normalize_for_qa(item.get("source_term", ""))
        tgt = normalize_for_qa(item.get("target_term", ""))
        if src:
            protected.append(src)
        if tgt:
            protected.append(tgt)
    protected.extend(sorted(COMMON_PROTECTED_UNITS))
    return protected


# ==========================================================
# REPORT ROW MODEL
# ==========================================================

@dataclass
class QAFinding:
    rule_id: str
    category: str
    severity: str
    confidence: str
    wrong_part: str
    suggestion: str
    explanation: str
    rule_source: str = "Rule Engine"
    autofix_possible: bool = False
    priority: int = 50


def truncate(text: Any, max_len: int = 500) -> str:
    value = visible_invisibles(text)
    if len(value) <= max_len:
        return value
    return value[:max_len] + "..."


def to_report_row(segment: Dict[str, Any], finding: QAFinding) -> Dict[str, Any]:
    return {
        "Sheet": segment.get("sheet", ""),
        "Location": segment.get("location", ""),
        "Mode": segment.get("mode", ""),
        "Source Text": truncate(segment.get("source", ""), 400),
        "Translation": truncate(segment.get("translation", segment.get("text", "")), 400),
        "Error Type": finding.category,
        "Severity": finding.severity,
        "Wrong Part": truncate(finding.wrong_part, 300),
        "Suggestion": truncate(finding.suggestion, 400),
        "Explanation": finding.explanation,
        "Check Source": "Rule Engine",
        "Rule Source": finding.rule_source,
        "Confidence": finding.confidence,
        "Rule ID": finding.rule_id,
        "Autofix Possible": "Yes" if finding.autofix_possible else "No",
        "Priority": finding.priority,
    }


# ==========================================================
# RULE REGISTRY
# ==========================================================

RuleFn = Callable[[Dict[str, Any], Dict[str, Any], str, str], List[QAFinding]]


@dataclass
class RuleSpec:
    rule_id: str
    category: str
    fn: RuleFn
    enabled: bool = True


class RuleRegistry:
    def __init__(self) -> None:
        self.rules: List[RuleSpec] = []

    def register(self, rule_id: str, category: str):
        def decorator(fn: RuleFn):
            self.rules.append(RuleSpec(rule_id=rule_id, category=category, fn=fn))
            return fn
        return decorator

    def run(self, segment: Dict[str, Any], client_rules: Dict[str, Any], target_language: str, domain: str) -> List[QAFinding]:
        findings: List[QAFinding] = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            try:
                findings.extend(rule.fn(segment, client_rules or {}, target_language, domain))
            except Exception as exc:
                findings.append(QAFinding(
                    rule_id=f"{rule.rule_id}.runtime_warning",
                    category="Rule Warning",
                    severity="Review",
                    confidence="Low",
                    wrong_part=rule.rule_id,
                    suggestion="Review this rule configuration.",
                    explanation=f"Rule execution warning: {str(exc)[:180]}",
                    rule_source="Rule Engine",
                    priority=99,
                ))
        return findings


registry = RuleRegistry()


def _seg_texts(segment: Dict[str, Any]) -> Tuple[str, str]:
    source = normalize_for_qa(segment.get("source", ""))
    target = normalize_for_qa(segment.get("translation", "") or segment.get("text", ""))
    return source, target



NON_LATIN_MODULES = {
    "telugu", "devanagari", "bengali", "gurmukhi", "gujarati", "odia",
    "tamil", "kannada", "malayalam", "sinhala", "arabic", "hebrew",
    "thai", "lao", "khmer", "myanmar", "cjk", "japanese", "korean",
    "cyrillic", "greek",
}

INDIC_MODULES = {
    "telugu", "devanagari", "bengali", "gurmukhi", "gujarati", "odia",
    "tamil", "kannada", "malayalam", "sinhala",
}

RTL_MODULES = {"arabic", "hebrew"}

COMMON_PROTECTED_UNITS = {"kcal", "mins", "min", "kg", "g", "mg", "km", "m", "cm", "mm", "mb", "gb", "tb", "kb", "fps", "dpi", "px"}


# Global language profile map used for offline routing and UI documentation.
# These profiles are intentionally conservative: they power deterministic checks,
# not full grammar/semantic judgments.
LANGUAGE_PROFILES = {
    "english": {"module": "latin", "script": "Latin", "locale_rules": ["apostrophes", "case", "ASCII punctuation"]},
    "french": {"module": "french", "script": "Latin", "locale_rules": ["space before : ; ? !", "accents"]},
    "spanish": {"module": "spanish", "script": "Latin", "locale_rules": ["¿/¡", "accents"]},
    "german": {"module": "german", "script": "Latin", "locale_rules": ["noun capitalization"]},
    "italian": {"module": "italian", "script": "Latin", "locale_rules": ["apostrophes", "accents"]},
    "portuguese": {"module": "portuguese", "script": "Latin", "locale_rules": ["accents"]},
    "turkish": {"module": "turkish", "script": "Latin", "locale_rules": ["dotted/dotless I"]},
    "vietnamese": {"module": "vietnamese", "script": "Latin", "locale_rules": ["diacritic density"]},
    "russian": {"module": "cyrillic", "script": "Cyrillic", "locale_rules": ["Latin confusables"]},
    "ukrainian": {"module": "cyrillic", "script": "Cyrillic", "locale_rules": ["Latin confusables"]},
    "greek": {"module": "greek", "script": "Greek", "locale_rules": ["Latin confusables"]},
    "arabic": {"module": "arabic", "script": "Arabic", "locale_rules": ["RTL", "Arabic comma"]},
    "hebrew": {"module": "hebrew", "script": "Hebrew", "locale_rules": ["RTL"]},
    "hindi": {"module": "devanagari", "script": "Devanagari", "locale_rules": ["danda", "nukta"]},
    "marathi": {"module": "devanagari", "script": "Devanagari", "locale_rules": ["danda", "nukta"]},
    "bengali": {"module": "bengali", "script": "Bengali", "locale_rules": ["Indic punctuation"]},
    "punjabi": {"module": "gurmukhi", "script": "Gurmukhi", "locale_rules": ["Indic punctuation"]},
    "gujarati": {"module": "gujarati", "script": "Gujarati", "locale_rules": ["Indic punctuation"]},
    "odia": {"module": "odia", "script": "Odia", "locale_rules": ["Indic punctuation"]},
    "tamil": {"module": "tamil", "script": "Tamil", "locale_rules": ["Indic punctuation"]},
    "telugu": {"module": "telugu", "script": "Telugu", "locale_rules": ["ZWNJ", "Indic punctuation"]},
    "kannada": {"module": "kannada", "script": "Kannada", "locale_rules": ["Indic punctuation"]},
    "malayalam": {"module": "malayalam", "script": "Malayalam", "locale_rules": ["Indic punctuation"]},
    "sinhala": {"module": "sinhala", "script": "Sinhala", "locale_rules": ["Indic punctuation"]},
    "chinese": {"module": "cjk", "script": "Han", "locale_rules": ["CJK spacing", "full-width punctuation"]},
    "japanese": {"module": "japanese", "script": "Kana/Han", "locale_rules": ["CJK spacing", "full-width punctuation"]},
    "korean": {"module": "korean", "script": "Hangul", "locale_rules": ["Korean spacing"]},
    "thai": {"module": "thai", "script": "Thai", "locale_rules": ["Thai spacing"]},
    "lao": {"module": "lao", "script": "Lao", "locale_rules": ["Lao spacing"]},
    "khmer": {"module": "khmer", "script": "Khmer", "locale_rules": ["Khmer spacing"]},
    "myanmar": {"module": "myanmar", "script": "Myanmar", "locale_rules": ["Myanmar spacing"]},
}

BULLET_RE = re.compile(r"^\s*([•∙◦▪▫●○\\-–—*]|\\d+[.)])\s*")
ELLIPSIS_RE = re.compile(r"(…|\\.\\.\\.)$")

# ==========================================================
# GLOBAL HIGH-PRECISION RULES
# ==========================================================

@registry.register("global.unicode.invisible_junk", "Unicode Hygiene")
def rule_invisible_junk(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    if ZWSP in target:
        findings.append(QAFinding(
            "global.unicode.invisible_junk",
            "Unicode Hygiene",
            "Minor",
            "High",
            "Zero Width Space",
            target.replace(ZWSP, ""),
            "Zero Width Space is invisible and can cause copy/paste or rendering issues.",
            autofix_possible=True,
            priority=10,
        ))
    if ZWJ in target and infer_language_module(target_language, "", target) not in {"arabic", "devanagari", "telugu"}:
        findings.append(QAFinding(
            "global.unicode.unexpected_zwj",
            "Unicode Hygiene",
            "Review",
            "Medium",
            "Zero Width Joiner",
            target.replace(ZWJ, ""),
            "Unexpected Zero Width Joiner found. Verify if this script/style requires it.",
            priority=60,
        ))
    return findings


@registry.register("global.unicode.zwnj_integrity", "ZWNJ")
def rule_zwnj_integrity(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    source_count = source.count(ZWNJ)
    target_count = target.count(ZWNJ)
    module = infer_language_module(target_language, source, target)
    lang = (target_language or "").lower()

    if source_count and target_count < source_count:
        findings.append(QAFinding(
            "global.unicode.zwnj.missing_from_source",
            "ZWNJ",
            "Major",
            "High",
            f"Expected {source_count} Zero Width Non-Joiner character(s), found {target_count}.",
            "Preserve the source ZWNJ character(s) where the same protected form appears in target.",
            "Source contains Zero Width Non-Joiner characters that are missing or reduced in target.",
            rule_source="Global Unicode rules",
            priority=7,
        ))

    if target_count:
        if re.search(rf"(^|[\s\.,;:!?]){ZWNJ}|{ZWNJ}($|[\s\.,;:!?])", target):
            findings.append(QAFinding(
                "global.unicode.zwnj.bad_position",
                "ZWNJ",
                "Major",
                "High",
                "Misplaced Zero Width Non-Joiner",
                target.replace(f" {ZWNJ}", ZWNJ).replace(f"{ZWNJ} ", ZWNJ),
                "ZWNJ is adjacent to whitespace, punctuation, or a string boundary. It should sit between characters that must not join.",
                rule_source="Global Unicode rules",
                autofix_possible=True,
                priority=9,
            ))
        if module not in {"arabic", "devanagari", "telugu", "bengali", "gurmukhi", "gujarati", "odia", "kannada", "malayalam", "sinhala"} and not source_count:
            findings.append(QAFinding(
                "global.unicode.zwnj.unexpected_script",
                "ZWNJ",
                "Review",
                "Medium",
                "Zero Width Non-Joiner",
                "Remove the ZWNJ unless the client language rules require it.",
                "Target contains ZWNJ in a script where CogniSweep does not normally expect it.",
                rule_source="Global Unicode rules",
                priority=62,
            ))

    if any(name in lang for name in ["persian", "farsi", "fa"]) or lang == "fa":
        for prefix in ["می", "نمی"]:
            match = re.search(rf"({re.escape(prefix)})\s+([\u0600-\u06FF]{{2,}})", target)
            if match:
                suggestion = target.replace(match.group(0), f"{match.group(1)}{ZWNJ}{match.group(2)}", 1)
                findings.append(QAFinding(
                    "persian.zwnj.verb_prefix",
                    "ZWNJ",
                    "Minor",
                    "Medium",
                    match.group(0),
                    suggestion,
                    "Persian verb prefixes commonly use ZWNJ instead of a visible space.",
                    rule_source="Persian Unicode rules",
                    autofix_possible=True,
                    priority=32,
                ))
    return findings


@registry.register("global.emoji.preserve", "Formatting")
def rule_emoji_preserve(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    src = extract_emoji(source)
    if not src:
        return []
    tgt = extract_emoji(target)
    missing = [symbol for symbol in src if symbol not in tgt]
    if missing:
        return [QAFinding(
            "global.emoji.missing_or_changed",
            "Formatting",
            "Major",
            "High",
            " ".join(missing),
            "Keep source emoji/icon characters unchanged unless client rules say to remove them.",
            "Emoji or icon characters from the source are missing or changed in target.",
            rule_source="Global source-driven formatting",
            priority=6,
        )]
    return []


@registry.register("global.spacing.extra_spaces", "Spacing")
def rule_spacing(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    if re.search(r"[ \t]{2,}", target):
        suggestion = re.sub(r"[ \t]{2,}", " ", target)
        findings.append(QAFinding(
            "global.spacing.extra_spaces",
            "Spacing",
            "Minor",
            "High",
            visible_invisibles(target),
            visible_invisibles(suggestion),
            "Multiple consecutive spaces found.",
            autofix_possible=True,
            priority=15,
        ))
    if target != target.strip():
        findings.append(QAFinding(
            "global.spacing.leading_trailing",
            "Spacing",
            "Minor",
            "High",
            visible_invisibles(target),
            visible_invisibles(target.strip()),
            "Leading or trailing spaces found.",
            autofix_possible=True,
            priority=15,
        ))
    return findings


ENDING_PUNCT_EQUIV = {
    ".": {".", "。", "．", "।", "॥"},
    "!": {"!", "！"},
    "?": {"?", "？"},
    ";": {";", "；"},
    ":": {":", "："},
}


@registry.register("global.punctuation.source_driven_ending", "Punctuation")
def rule_source_driven_ending_punct(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    source = source.strip()
    target = target.strip()
    if not source or not target:
        return []
    src_end = source[-1]
    tgt_end = target[-1]
    if src_end not in ENDING_PUNCT_EQUIV:
        return []
    if tgt_end in ENDING_PUNCT_EQUIV[src_end]:
        return []
    preferred = "।" if src_end == "." and infer_language_module(target_language, source, target) == "devanagari" else src_end
    return [QAFinding(
        "global.punctuation.source_driven_ending",
        "Punctuation",
        "Minor",
        "High",
        "missing ending punctuation",
        target + preferred,
        f"Source ends with '{src_end}', so target should preserve equivalent ending punctuation.",
        autofix_possible=True,
        priority=20,
    )]


@registry.register("global.punctuation.repeated", "Punctuation")
def rule_repeated_punctuation(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    if re.search(r"([!?.,;:])\1{1,}", target):
        suggestion = re.sub(r"([!?.,;:])\1{1,}", r"\1", target)
        findings.append(QAFinding(
            "global.punctuation.repeated",
            "Punctuation",
            "Minor",
            "High",
            visible_invisibles(target),
            visible_invisibles(suggestion),
            "Repeated punctuation found.",
            autofix_possible=True,
            priority=18,
        ))
    if re.search(r"\s+([,.;:!?])", target):
        suggestion = re.sub(r"\s+([,.;:!?])", r"\1", target)
        findings.append(QAFinding(
            "global.punctuation.space_before_punct",
            "Punctuation",
            "Minor",
            "High",
            visible_invisibles(target),
            visible_invisibles(suggestion),
            "Unexpected space before punctuation.",
            autofix_possible=True,
            priority=18,
        ))
    return findings


@registry.register("global.placeholder.preserve", "Placeholder")
def rule_placeholders(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source:
        return []
    src = extract_placeholders(source)
    tgt = extract_placeholders(target)
    findings: List[QAFinding] = []
    missing = [p for p in src if p not in tgt]
    extra = [p for p in tgt if p not in src]
    if missing:
        findings.append(QAFinding(
            "global.placeholder.missing",
            "Placeholder",
            "Major",
            "High",
            ", ".join(missing),
            target,
            "Placeholder/tag from source is missing in target.",
            priority=5,
        ))
    if extra:
        findings.append(QAFinding(
            "global.placeholder.extra",
            "Placeholder",
            "Major",
            "High",
            ", ".join(extra),
            target,
            "Target contains placeholder/tag not found in source.",
            priority=5,
        ))
    return findings


@registry.register("global.number.preserve", "Number")
def rule_numbers(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source:
        return []
    src = extract_numbers(source)
    tgt = extract_numbers(target)
    missing = [n for n in src if n not in tgt]
    if missing:
        return [QAFinding(
            "global.number.missing_or_changed",
            "Number",
            "Major",
            "High",
            ", ".join(missing),
            target,
            "Number from source is missing or changed in target.",
            priority=6,
        )]
    return []


@registry.register("global.protected.url_email_sku", "Formatting")
def rule_urls_emails_skus(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    for label, extractor, severity in [
        ("URL", extract_urls, "Major"),
        ("Email", extract_emails, "Major"),
        ("SKU", extract_skus, "Review"),
        ("HTML/XML tag", extract_tags, "Major"),
    ]:
        src = extractor(source)
        tgt = extractor(target)
        missing = [x for x in src if x not in tgt]
        if missing:
            findings.append(QAFinding(
                f"global.protected.{label.lower().replace('/', '_')}.missing",
                "Formatting",
                severity,
                "High",
                ", ".join(missing),
                target,
                f"{label} from source is missing or changed in target.",
                priority=6,
            ))
    return findings


def _quote_count_for_real_quotes(text: str) -> int:
    """Count only likely quotation marks, not inch symbols after numbers/fractions."""
    count = 0
    for i, ch in enumerate(text):
        if ch != '"':
            continue
        prev = text[i - 1] if i > 0 else ""
        # 0.1", 1/2", 13/16" are measurements, not quotes.
        if prev.isdigit():
            continue
        count += 1
    return count


@registry.register("global.quote_balance.source_driven", "Formatting")
def rule_quote_balance(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    # Count ASCII quotes excluding inch symbols; smart quotes are counted normally.
    for label, chars in [("double quote", ['"', "“", "”"]), ("single quote", ["'", "‘", "’"])]:
        if label == "double quote":
            src_count = _quote_count_for_real_quotes(source) + source.count("“") + source.count("”")
            tgt_count = _quote_count_for_real_quotes(target) + target.count("“") + target.count("”")
        else:
            # Do not count apostrophes inside words.
            src_count = len(re.findall(r"(?<!\w)'|'(?!\w)|[‘’]", source))
            tgt_count = len(re.findall(r"(?<!\w)'|'(?!\w)|[‘’]", target))
        if src_count == 0 and tgt_count == 0:
            continue
        if src_count % 2 == 0 and tgt_count % 2 != 0:
            findings.append(QAFinding(
                f"global.quote_balance.{label.replace(' ', '_')}",
                "Formatting",
                "Minor",
                "High",
                f"unbalanced {label}",
                target,
                f"Target has unbalanced {label}s. Measurement inch symbols are ignored.",
                priority=25,
            ))
    return findings


@registry.register("global.bracket_balance", "Formatting")
def rule_bracket_balance(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    pairs = [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">")]
    for left, right in pairs:
        if target.count(left) != target.count(right):
            return [QAFinding(
                "global.bracket_balance",
                "Formatting",
                "Minor",
                "High",
                f"Unbalanced {left}{right}",
                target,
                "Unbalanced brackets detected in target.",
                priority=25,
            )]
    return []


@registry.register("global.source_copied", "Accuracy")
def rule_source_copied(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source or not target:
        return []
    if len(source) < 6:
        return []
    if tm_norm(source) == tm_norm(target) and LATIN_RE.search(source):
        return [QAFinding(
            "global.source_copied",
            "Accuracy",
            "Major",
            "High",
            target,
            "Translate the source text or confirm it is intentionally DNT.",
            "Target appears copied from source.",
            priority=8,
        )]
    return []


def tm_norm(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_for_qa(text)).strip().lower()


@registry.register("global.dnt.preserve", "DNT")
def rule_dnt(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    for d in (rules or {}).get("dnt", []):
        term = normalize_for_qa(d.get("term", ""))
        if not term:
            continue
        if term.lower() in source.lower() and term not in target:
            findings.append(QAFinding(
                "global.dnt.preserve",
                "DNT",
                "Major",
                "High",
                term,
                f"Keep '{term}' unchanged.",
                "Do-not-translate term from client rules is missing or changed.",
                rule_source=d.get("source", "Client Rules"),
                priority=4,
            ))
    return findings


@registry.register("global.glossary.required_term", "Glossary")
def rule_glossary(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings: List[QAFinding] = []
    for g in (rules or {}).get("glossary", []):
        src_term = normalize_for_qa(g.get("source_term", ""))
        tgt_term = normalize_for_qa(g.get("target_term", ""))
        if not src_term or not tgt_term:
            continue
        if src_term.lower() in source.lower() and tgt_term not in target:
            findings.append(QAFinding(
                "global.glossary.required_term",
                "Glossary",
                "Major",
                "High",
                src_term,
                tgt_term,
                "Client glossary target term is missing in translation.",
                rule_source=g.get("source", "Client Glossary"),
                priority=4,
            ))
    return findings


# ==========================================================
# GLOBAL LANGUAGE-SPECIFIC RULES
# ==========================================================

@registry.register("global.script.unexpected_latin", "Mixed Script")
def rule_unexpected_latin(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if module not in NON_LATIN_MODULES:
        return []

    protected = set(protected_terms_from_rules(rules))
    protected.update(extract_urls(target))
    protected.update(extract_emails(target))
    protected.update(extract_skus(target))
    protected.update(extract_placeholders(target))
    protected.update(extract_tags(target))

    latin_words = re.findall(r"\b[A-Za-z][A-Za-z0-9._-]*\b", target)
    unexpected = []
    for word in latin_words:
        if word in protected:
            continue
        if any(word in p for p in protected):
            continue
        # UI/product acronyms are often valid. Keep this conservative.
        if word.isupper() and len(word) <= 6:
            continue
        unexpected.append(word)

    if unexpected:
        return [QAFinding(
            f"{module}.script.unexpected_latin",
            "Mixed Script",
            "Major",
            "Medium",
            ", ".join(sorted(set(unexpected))[:10]),
            target,
            "Unexpected Latin/Roman text found inside non-Latin target text. Add to DNT/glossary if allowed.",
            priority=22,
        )]
    return []


@registry.register("global.cjk.spacing", "Spacing")
def rule_cjk_spacing(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "cjk":
        return []
    # Spaces between CJK characters are usually suspicious.
    if re.search(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]\s+[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]", target):
        suggestion = re.sub(r"([\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF])\s+([\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF])", r"\1\2", target)
        return [QAFinding(
            "cjk.spacing.internal_space",
            "Spacing",
            "Minor",
            "Medium",
            target,
            suggestion,
            "Unexpected space between CJK characters.",
            autofix_possible=True,
            priority=35,
        )]
    return []


@registry.register("french.punctuation.spacing", "Punctuation")
def rule_french_punctuation_spacing(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    lang = (target_language or "").lower()
    if "french" not in lang and "fr" not in lang:
        return []
    # French normally uses a space before : ; ? !
    if re.search(r"\S[:;?!]", target):
        suggestion = re.sub(r"(\S)([:;?!])", r"\1 \2", target)
        return [QAFinding(
            "french.punctuation.spacing",
            "Punctuation",
            "Minor",
            "Medium",
            target,
            suggestion,
            "French punctuation convention usually requires spacing before : ; ? !.",
            autofix_possible=True,
            priority=45,
        )]
    return []


# ==========================================================
# TELUGU PLUGIN
# ==========================================================

TELUGU_ZWNJ_TABLE = [
    ("డాక్యుమెంట్", ["ను", "లను", "లు", "తో", "కి", "లో"]),
    ("పాస్‌వర్డ్", ["ను", "తో", "లో", "కి"]),
    ("పాస్వర్డ్", ["ను", "తో", "లో", "కి"]),
    ("డాష్‌బోర్డ్", ["ను", "లో", "కి"]),
    ("అప్‌లోడ్", ["ను", "చేయండి", "తో"]),
    ("డౌన్‌లోడ్", ["ను", "చేయండి", "తో"]),
    ("టెంప్లేట్", ["లు", "ను", "లను", "లో"]),
    ("సెట్టింగ్", ["లు", "లను", "లో", "కి"]),
    ("కనెక్షన్", ["ను", "తో", "లో"]),
    ("ఫైల్", ["ను", "లను", "లు", "లో"]),
]

TELUGU_COMMON_CORRECTIONS = {
    "పాస్వర్డ్": "పాస్‌వర్డ్",
    "పాస్ వర్డ్": "పాస్‌వర్డ్",
    "డౌన్లోడ్": "డౌన్‌లోడ్",
    "డౌన్ లోడ్": "డౌన్‌లోడ్",
    "అప్లోడ్": "అప్‌లోడ్",
    "అప్ లోడ్": "అప్‌లోడ్",
    "డాష్బోర్డ్": "డాష్‌బోర్డ్",
    "డాష్ బోర్డ్": "డాష్‌బోర్డ్",
}


TELUGU_VIRAMA = "\u0c4d"
TELUGU_LETTER_RE = re.compile(r"[\u0c05-\u0c39\u0c58-\u0c5a\u0c60-\u0c61]")
TELUGU_DEPENDENT_SIGN_RANGES = (
    (0x0C3C, 0x0C3C),
    (0x0C3E, 0x0C44),
    (0x0C46, 0x0C48),
    (0x0C4A, 0x0C4D),
    (0x0C55, 0x0C56),
    (0x0C62, 0x0C63),
)


def _is_telugu_dependent_sign(ch: str) -> bool:
    if not ch:
        return False
    codepoint = ord(ch)
    return any(start <= codepoint <= end for start, end in TELUGU_DEPENDENT_SIGN_RANGES)


def _is_telugu_letter(ch: str) -> bool:
    return bool(TELUGU_LETTER_RE.fullmatch(ch or ""))


@registry.register("telugu.common_dictionary", "Spelling")
def rule_telugu_common_dictionary(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "telugu":
        return []
    findings: List[QAFinding] = []
    for wrong, correct in TELUGU_COMMON_CORRECTIONS.items():
        if wrong in target:
            findings.append(QAFinding(
                "telugu.common_dictionary",
                "Spelling",
                "Minor",
                "High",
                wrong,
                target.replace(wrong, correct),
                "Common Telugu UI/localization spelling or ZWNJ form should use the approved form.",
                rule_source="Built-in Telugu dictionary",
                autofix_possible=True,
                priority=28,
            ))
    return findings


@registry.register("telugu.zwnj.loanword_suffix", "ZWNJ")
def rule_telugu_zwnj(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "telugu":
        return []
    findings: List[QAFinding] = []
    for base, suffixes in TELUGU_ZWNJ_TABLE:
        for suffix in suffixes:
            good = base + ZWNJ + suffix
            bad_joined = base + suffix
            bad_spaced = base + " " + suffix
            if bad_joined in target:
                findings.append(QAFinding(
                    "telugu.zwnj.loanword_suffix.missing",
                    "ZWNJ",
                    "Minor",
                    "Medium",
                    visible_invisibles(bad_joined),
                    visible_invisibles(target.replace(bad_joined, good)),
                    "Possible missing ZWNJ between Telugu loanword/base and suffix.",
                    rule_source="Built-in Telugu ZWNJ table",
                    autofix_possible=True,
                    priority=30,
                ))
            if bad_spaced in target:
                findings.append(QAFinding(
                    "telugu.zwnj.loanword_suffix.visible_space",
                    "ZWNJ",
                    "Minor",
                    "Medium",
                    visible_invisibles(bad_spaced),
                    visible_invisibles(target.replace(bad_spaced, good)),
                    "Visible space found where ZWNJ may be required.",
                    rule_source="Built-in Telugu ZWNJ table",
                    autofix_possible=True,
                    priority=30,
                ))
    return findings


@registry.register("telugu.unicode.malformed_cluster_hint", "Unicode Hygiene")
def rule_telugu_malformed_cluster_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "telugu" or not target:
        return []

    findings: List[QAFinding] = []

    repeated_virama = re.search(f"{TELUGU_VIRAMA}{{2,}}", target)
    if repeated_virama:
        findings.append(QAFinding(
            "telugu.unicode.malformed_cluster_hint.repeated_virama",
            "Unicode Hygiene",
            "Major",
            "High",
            visible_invisibles(repeated_virama.group(0)),
            target.replace(repeated_virama.group(0), TELUGU_VIRAMA, 1),
            "Repeated Telugu virama signs can create a malformed consonant cluster.",
            rule_source="Built-in Telugu Unicode rules",
            autofix_possible=True,
            priority=22,
        ))

    dangling_virama = re.search(rf"{TELUGU_VIRAMA}(?:$|[\s\.,;:!?])", target)
    if dangling_virama:
        matched = dangling_virama.group(0)
        suffix = "" if matched.endswith(TELUGU_VIRAMA) else matched[-1]
        suggestion = target[:dangling_virama.start()] + suffix + target[dangling_virama.end():]
        findings.append(QAFinding(
            "telugu.unicode.malformed_cluster_hint.dangling_virama",
            "Unicode Hygiene",
            "Major",
            "High",
            visible_invisibles(matched),
            suggestion,
            "Telugu virama appears at a word or punctuation boundary. Verify the consonant cluster is complete.",
            rule_source="Built-in Telugu Unicode rules",
            autofix_possible=True,
            priority=23,
        ))

    for idx, ch in enumerate(target):
        if ch == TELUGU_VIRAMA or not _is_telugu_dependent_sign(ch):
            continue
        previous = target[idx - 1] if idx else ""
        if not _is_telugu_letter(previous):
            snippet = target[max(0, idx - 1): idx + 2]
            findings.append(QAFinding(
                "telugu.unicode.malformed_cluster_hint.orphan_dependent_sign",
                "Unicode Hygiene",
                "Review",
                "Medium",
                visible_invisibles(snippet or ch),
                target,
                "A Telugu dependent vowel/sign appears without a preceding Telugu letter. Review the Unicode cluster.",
                rule_source="Built-in Telugu Unicode rules",
                priority=35,
            ))
            break

    return findings


@registry.register("telugu.ui_imperative.consistency_hint", "Style")
def rule_telugu_ui_imperative_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "telugu":
        return []
    if not source or not target:
        return []

    # Only warn when source is a clear UI command and target has no common imperative marker.
    command_words = ["save", "delete", "continue", "try again", "upload", "download", "select", "choose", "create", "submit"]
    if not any(w in source.lower() for w in command_words):
        return []
    if any(marker in target for marker in ["చేయండి", "ఎంచుకోండి", "తొలగించండి", "కొనసాగించండి", "సేవ్"]):
        return []
    return [QAFinding(
        "telugu.ui_imperative.consistency_hint",
        "Style",
        "Review",
        "Low",
        target,
        target,
        "This looks like a UI command. Verify whether the target follows the client’s preferred Telugu imperative style.",
        rule_source="Built-in Telugu UI style hint",
        priority=85,
    )]


@registry.register("indic.master_rules.punctuation_profile", "Country Standards")
def rule_master_linguistic_punctuation_profile(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    lang = (target_language or "").lower()
    findings: List[QAFinding] = []
    if not target:
        return findings

    # Hindi/Bengali master profile: sentence-ending danda is expected in formal UI/prose.
    if (
        "hindi" in lang
        or lang in {"hi"}
        or "bengali" in lang
        or "bangla" in lang
        or lang in {"bn"}
        or "punjabi" in lang
        or "gurmukhi" in lang
        or lang in {"pa"}
        or module == "gurmukhi"
    ) and target.rstrip().endswith("."):
        suggestion = target.rstrip()[:-1] + "\u0964"
        findings.append(QAFinding(
            "indic.master_rules.danda_expected",
            "Country Standards",
            "Minor",
            "Medium",
            ".",
            suggestion,
            "Master linguistic rules indicate this language normally uses danda/poorna viram for sentence-ending punctuation.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=34,
        ))

    # These master profiles use the English period, not danda.
    marathi_lang = "marathi" in lang or lang == "mr"
    gujarati_lang = "gujarati" in lang or lang == "gu"
    if (module in {"tamil", "telugu", "kannada", "malayalam", "gujarati"} or marathi_lang or gujarati_lang) and "\u0964" in target:
        findings.append(QAFinding(
            "indic.master_rules.danda_unexpected",
            "Country Standards",
            "Minor",
            "High",
            "\u0964",
            target.replace("\u0964", "."),
            "Master linguistic rules indicate this language profile should use the standard period instead of danda.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=31,
        ))
    arabic_script_lang = module == "arabic" or any(x in lang for x in ["arabic", "urdu", "persian", "farsi"]) or lang in {"ar", "ur", "fa"}
    if arabic_script_lang and "," in target:
        findings.append(QAFinding(
            "master_rules.arabic_script_comma",
            "Country Standards",
            "Minor",
            "Medium",
            ",",
            target.replace(",", "\u060c"),
            "Master linguistic rules indicate Arabic-script locales should use the Arabic comma in localized text.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=35,
        ))
    if arabic_script_lang and "?" in target:
        findings.append(QAFinding(
            "master_rules.arabic_script_question_mark",
            "Country Standards",
            "Minor",
            "Medium",
            "?",
            target.replace("?", "\u061f"),
            "Master linguistic rules indicate Arabic-script locales should use the Arabic question mark.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=35,
        ))
    if (module == "amharic" or "amharic" in lang or lang == "am") and target.rstrip().endswith("."):
        findings.append(QAFinding(
            "master_rules.amharic_ethiopic_full_stop",
            "Country Standards",
            "Minor",
            "Medium",
            ".",
            target.rstrip()[:-1] + "\u1362",
            "Master linguistic rules indicate Amharic should use the Ethiopic full stop.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=35,
        ))
    return findings


@registry.register("indic.master_rules.formality_profile", "Style")
def rule_master_linguistic_formality_profile(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    lang = (target_language or "").lower()
    if not target:
        return []
    marathi_lang = "marathi" in lang or lang == "mr"
    checks: List[Tuple[bool, List[str], str, str]] = [
        ("hindi" in lang or lang == "hi" or (module == "devanagari" and not marathi_lang), ["\u0924\u0942", "\u0924\u0941\u092e"], "\u0906\u092a", "Hindi UI/business text should use the formal/respectful second person."),
        (marathi_lang, ["\u0924\u0942"], "\u0924\u0941\u092e\u094d\u0939\u0940", "Marathi professional UI/business text should use a respectful second person unless the client asks for informal tone."),
        ("bengali" in lang or "bangla" in lang or lang == "bn" or module == "bengali", ["\u09a4\u09c1\u0987", "\u09a4\u09c1\u09ae\u09bf"], "\u0986\u09aa\u09a8\u09bf", "Bengali UI/business text should use the formal second person."),
        (module == "tamil", ["\u0ba8\u0bc0"], "\u0ba8\u0bc0\u0b99\u0bcd\u0b95\u0bb3\u0bcd", "Tamil UI/business text should use the formal/plural second person."),
        (module == "telugu", ["\u0c28\u0c41\u0c35\u0c4d\u0c35\u0c41"], "\u0c2e\u0c40\u0c30\u0c41", "Telugu UI/business text should use the formal/plural second person."),
        (module == "kannada", ["\u0ca8\u0cc0\u0ca8\u0cc1"], "\u0ca8\u0cc0\u0cb5\u0cc1", "Kannada UI/business text should use the formal/plural second person."),
        (module == "malayalam", ["\u0d28\u0d40"], "\u0d28\u0d3f\u0d19\u0d4d\u0d19\u0d7e", "Malayalam professional software text should use a respectful, slightly formal tone."),
        (module == "gujarati", ["\u0aa4\u0ac1\u0a82"], "\u0aa4\u0aae\u0ac7", "Gujarati business/SaaS text should use the formal second person unless the client specifies informal tone."),
        (module == "gurmukhi", ["\u0a24\u0a42\u0a70"], "\u0a24\u0a41\u0a38\u0a40\u0a02", "Punjabi UI/business text should use the respectful second person unless informal tone is requested."),
        (module == "arabic" and ("urdu" in lang or lang == "ur"), ["\u062a\u0648", "\u062a\u0645"], "\u0622\u067e", "Urdu professional text should use the respectful second person."),
        (module == "arabic" and ("persian" in lang or "farsi" in lang or lang == "fa"), ["\u062a\u0648"], "\u0634\u0645\u0627", "Persian SaaS/UI text should use the formal second person."),
        (module == "greek", ["\u0395\u03c3\u03cd", "\u03b5\u03c3\u03cd"], "\u0395\u03c3\u03b5\u03af\u03c2", "Greek SaaS UI usually uses formal/plural address."),
        (module == "amharic", ["\u12a0\u1295\u1270", "\u12a0\u1295\u127a"], "\u12a5\u122d\u1235\u12ce", "Amharic formal UI should use respectful, gender-neutral address."),
    ]
    findings: List[QAFinding] = []
    for applies, informal_terms, formal_term, explanation in checks:
        if not applies:
            continue
        for term in informal_terms:
            if term and term in target:
                findings.append(QAFinding(
                    "indic.master_rules.formality",
                    "Style",
                    "Review",
                    "Medium",
                    term,
                    f"Consider using {formal_term} or the client-approved formal equivalent.",
                    explanation,
                    rule_source="linguisticrules.md",
                    priority=68,
                ))
                return findings
    if module == "french" and re.search(r"\b(tu|toi|ton|ta|tes)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "indic.master_rules.french_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using vous/votre unless the client-approved tone is informal.",
            "Master linguistic rules indicate SaaS French often needs a formal register.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "german" and re.search(r"\b(du|dich|dir|dein(?:e[msnr]?)?)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "indic.master_rules.german_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using Sie/Ihr unless the client-approved tone is informal.",
            "Master linguistic rules indicate German SaaS UI often needs formal register.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "italian" and re.search(r"\b(tu|ti|tuo|tua|tuoi|tue)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.italian_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using Lei/Le/Suo unless the client-approved tone is informal.",
            "Master linguistic rules indicate Italian B2B SaaS often uses formal address.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "turkish" and re.search(r"\b(sen|seni|sana|senin)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.turkish_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using Siz/Sizin unless the client-approved tone is informal.",
            "Master linguistic rules indicate Turkish SaaS UI defaults to formal/plural address.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "cyrillic" and ("russian" in lang or lang == "ru") and re.search(r"\b(ты|тебя|тебе|твой|твоя|твои)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.russian_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using Вы/вы unless the client-approved tone is informal.",
            "Master linguistic rules indicate Russian SaaS/UI usually uses formal address.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "cyrillic" and ("ukrainian" in lang or lang == "uk") and re.search(r"\b(ти|тебе|твій|твоя|твої)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.ukrainian_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using Ви/ви unless the client-approved tone is informal.",
            "Master linguistic rules indicate Ukrainian SaaS/UI defaults to formal address.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "afrikaans" and re.search(r"\b(jy|jou|julle)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.afrikaans_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using U or impersonal phrasing for business UI unless informal tone is approved.",
            "Master linguistic rules indicate Afrikaans business UI often uses formal or impersonal address.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "yoruba" and re.search(r"\b(o|iwo)\b|\u00ccw\u1ecd", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.yoruba_honorific",
            "Style",
            "Review",
            "Medium",
            target,
            "Consider using \u1eb8/\u1eb8yin or the client-approved respectful address.",
            "Master linguistic rules indicate Yoruba professional UI should use respectful honorific address.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    return findings


@registry.register("indic.master_rules.ui_imperative_hint", "Style")
def rule_master_linguistic_ui_imperative_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if module not in {"tamil", "telugu", "kannada"} or not source or not target:
        return []
    command_words = ["save", "delete", "continue", "try again", "upload", "download", "select", "choose", "create", "submit", "login", "sign in"]
    if not any(word in source.lower() for word in command_words):
        return []
    expected_markers = {
        "tamil": ["\u0bb5\u0bc1\u0bae\u0bcd"],
        "telugu": ["\u0c02\u0c21\u0c3f", "\u0c1a\u0c47\u0c2f\u0c02\u0c21\u0c3f"],
        "kannada": ["\u0cbf\u0cb0\u0cbf", "\u0cae\u0cbe\u0ca1\u0cbf"],
    }
    if any(marker in target for marker in expected_markers.get(module, [])):
        return []
    return [QAFinding(
        "indic.master_rules.ui_imperative_hint",
        "Style",
        "Review",
        "Low",
        target,
        target,
        "Master linguistic rules indicate this UI command should be checked for the language's respectful imperative form.",
        rule_source="linguisticrules.md",
        priority=86,
    )]


@registry.register("indic.master_rules.text_expansion_hint", "Layout")
def rule_master_linguistic_text_expansion_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if module not in {"tamil", "telugu", "kannada", "malayalam", "german", "dutch", "nordic"} or not source or not target:
        return []
    if domain.lower() not in {"software ui", "subtitling", "gaming", "auto-detect", "auto detect", "general"}:
        return []
    expansion_limit = 1.45 if module in {"german", "dutch", "nordic"} else 1.65
    if len(target) > max(24, int(len(source) * expansion_limit)):
        return [QAFinding(
            "indic.master_rules.length_expansion",
            "Layout",
            "Review",
            "Medium",
            target[:120],
            "Check button/menu/subtitle truncation in context.",
            "Master linguistic rules note significant text expansion or compound-word truncation risk for this language profile.",
            rule_source="linguisticrules.md",
            priority=72,
        )]
    return []


@registry.register("master_rules.european_punctuation", "Formatting")
def rule_master_linguistic_european_punctuation(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    lang = (target_language or "").lower()
    if not target:
        return []
    findings: List[QAFinding] = []
    if module == "french" and not any(x in lang for x in ["fr-ca", "canadian"]):
        if re.search(r"(?<![\s\u00a0])[:;!?]", target):
            suggestion = re.sub(r"(?<![\s\u00a0])([:;!?])", "\u00a0\\1", target)
            findings.append(QAFinding(
                "master_rules.french_nbsp_before_punctuation",
                "Formatting",
                "Minor",
                "Medium",
                target,
                suggestion,
                "Master linguistic rules indicate European French requires a non-breaking space before : ; ! and ?.",
                rule_source="linguisticrules.md",
                autofix_possible=True,
                priority=36,
            ))
    if module == "greek" and "?" in target:
        findings.append(QAFinding(
            "master_rules.greek_question_mark",
            "Punctuation",
            "Major",
            "High",
            "?",
            target.replace("?", ";"),
            "Master linguistic rules indicate Greek questions use the semicolon-style question mark instead of the English question mark.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=20,
        ))
    return findings


@registry.register("master_rules.locale_spelling", "Spelling")
def rule_master_linguistic_locale_spelling(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    lang = (target_language or "").lower().replace("_", "-")
    if not target:
        return []
    uk_requested = "uk english" in lang or "english uk" in lang or "british" in lang or "en-gb" in lang or "en-uk" in lang
    us_requested = "us english" in lang or "english us" in lang or "american" in lang or "en-us" in lang
    if not (uk_requested or us_requested):
        return []
    pairs = {
        "color": "colour",
        "favorite": "favourite",
        "center": "centre",
        "customize": "customise",
        "customized": "customised",
        "organization": "organisation",
        "organize": "organise",
        "analyze": "analyse",
        "license": "licence",
    }
    if us_requested:
        pairs = {v: k for k, v in pairs.items()}
    for wrong, preferred in pairs.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", flags=re.IGNORECASE)
        if pattern.search(target):
            suggestion = pattern.sub(lambda m: preferred.capitalize() if m.group(0)[0].isupper() else preferred, target)
            return [QAFinding(
                "master_rules.english_locale_spelling",
                "Spelling",
                "Minor",
                "Medium",
                wrong,
                suggestion,
                "Master linguistic rules indicate English locale spelling should match the selected UK/US variant.",
                rule_source="linguisticrules.md",
                autofix_possible=True,
                priority=42,
            )]
    return []


@registry.register("master_rules.malayalam_chillu_encoding", "Unicode Hygiene")
def rule_master_linguistic_malayalam_chillu_encoding(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "malayalam" or not target:
        return []
    if ZWJ in target:
        return [QAFinding(
            "master_rules.malayalam_legacy_chillu_zwj",
            "Unicode Hygiene",
            "Review",
            "Medium",
            "ZWJ",
            "Verify whether this should be a modern atomic Malayalam chillu character.",
            "Master linguistic rules note that legacy Malayalam chillu forms used ZWJ and can cause rendering issues.",
            rule_source="linguisticrules.md",
            priority=58,
        )]
    return []


@registry.register("master_rules.russian_ukrainian_apostrophe", "Typography")
def rule_master_linguistic_cyrillic_apostrophe(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    lang = (target_language or "").lower()
    if not target:
        return []
    if ("ukrainian" in lang or lang == "uk") and ("\u2019" in target or "\u2018" in target):
        return [QAFinding(
            "master_rules.ukrainian_apostrophe",
            "Typography",
            "Minor",
            "Medium",
            "curly apostrophe",
            target.replace("\u2019", "\u02bc").replace("\u2018", "\u02bc"),
            "Master linguistic rules indicate Ukrainian should use a Ukrainian apostrophe or straight apostrophe, not curly English quotes.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=45,
        )]
    return []


@registry.register("master_rules.cjk_punctuation", "Punctuation")
def rule_master_linguistic_cjk_punctuation(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if not target or module not in {"cjk", "japanese"}:
        return []
    if not re.search(r"[\u4E00-\u9FFF\u3040-\u30FF]", target):
        return []
    if not re.search(r"[.,!?;:]", target):
        return []
    if module == "japanese":
        table = str.maketrans({".": "\u3002", ",": "\u3001", "!": "\uff01", "?": "\uff1f", ";": "\uff1b", ":": "\uff1a"})
        explanation = "Master linguistic rules indicate Japanese should use ideographic/full-width punctuation in localized text."
    else:
        table = str.maketrans({".": "\u3002", ",": "\uff0c", "!": "\uff01", "?": "\uff1f", ";": "\uff1b", ":": "\uff1a"})
        explanation = "Master linguistic rules indicate Chinese should use full-width punctuation in localized text."
    return [QAFinding(
        "master_rules.cjk_fullwidth_punctuation",
        "Punctuation",
        "Minor",
        "High",
        "ASCII punctuation",
        target.translate(table),
        explanation,
        rule_source="linguisticrules.md",
        autofix_possible=True,
        priority=24,
    )]


@registry.register("master_rules.east_asian_register", "Style")
def rule_master_linguistic_east_asian_register(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if not target:
        return []
    if module == "cjk" and "\u4f60" in target:
        return [QAFinding(
            "master_rules.chinese_formality",
            "Style",
            "Review",
            "Medium",
            "\u4f60",
            "Consider using \u60a8 if the client requires formal/B2B address.",
            "Master linguistic rules note Chinese B2B/legal UI may require formal/respectful address.",
            rule_source="linguisticrules.md",
            priority=70,
        )]
    if module == "korean" and "\ub2f9\uc2e0" in target:
        return [QAFinding(
            "master_rules.korean_direct_you",
            "Style",
            "Review",
            "Medium",
            "\ub2f9\uc2e0",
            "Omit the direct second-person pronoun or use the client-approved polite phrasing.",
            "Master linguistic rules note direct 'you' can sound rude in professional Korean UI.",
            rule_source="linguisticrules.md",
            priority=70,
        )]
    return []


@registry.register("master_rules.se_asia_punctuation", "Punctuation")
def rule_master_linguistic_se_asia_punctuation(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if not target:
        return []
    if module == "myanmar" and "." in target:
        return [QAFinding(
            "master_rules.myanmar_full_stop",
            "Punctuation",
            "Minor",
            "Medium",
            ".",
            target.replace(".", "\u104b"),
            "Master linguistic rules indicate Burmese/Myanmar should use the native full stop.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=32,
        )]
    if module == "myanmar" and "," in target:
        return [QAFinding(
            "master_rules.myanmar_comma",
            "Punctuation",
            "Minor",
            "Medium",
            ",",
            target.replace(",", "\u104a"),
            "Master linguistic rules indicate Burmese/Myanmar should use the native comma.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=33,
        )]
    if module == "khmer" and "." in target:
        return [QAFinding(
            "master_rules.khmer_khan_full_stop",
            "Punctuation",
            "Minor",
            "Medium",
            ".",
            target.replace(".", "\u17d4"),
            "Master linguistic rules indicate Khmer should use khan as the full stop.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=32,
        )]
    return []


@registry.register("master_rules.se_asia_locale_hints", "Locale Convention")
def rule_master_linguistic_se_asia_locale_hints(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if not target:
        return []
    if module == "thai" and ("\u0e04\u0e23\u0e31\u0e1a" in target or "\u0e04\u0e48\u0e30" in target):
        return [QAFinding(
            "master_rules.thai_gendered_particle",
            "Style",
            "Review",
            "Medium",
            target,
            "Remove gendered politeness particles in neutral software UI unless client rules require them.",
            "Master linguistic rules indicate Thai SaaS UI usually omits gendered particles.",
            rule_source="linguisticrules.md",
            priority=71,
        )]
    if module == "lao" and THAI_RE.search(target):
        return [QAFinding(
            "master_rules.lao_thai_script_contamination",
            "Mixed Script",
            "Major",
            "Medium",
            "Thai script",
            "Replace Thai-script text with native Lao orthography unless client rules explicitly allow Thai.",
            "Master linguistic rules warn against Thai contamination in Lao localization.",
            rule_source="linguisticrules.md",
            priority=23,
        )]
    return []


@registry.register("master_rules.indonesian_malay", "Style")
def rule_master_linguistic_indonesian_malay(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    lang = (target_language or "").lower()
    module = infer_language_module(target_language, "", target)
    if not target:
        return []
    if module == "indonesian" and re.search(r"\bkamu\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.indonesian_formality",
            "Style",
            "Review",
            "Medium",
            "kamu",
            "Consider using Anda for B2B/SaaS UI unless informal tone is approved.",
            "Master linguistic rules indicate Indonesian B2B/SaaS UI should use formal Anda.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "indonesian" and re.search(r"\banda\b", target):
        return [QAFinding(
            "master_rules.indonesian_anda_capitalization",
            "Capitalization",
            "Minor",
            "High",
            "anda",
            re.sub(r"\banda\b", "Anda", target),
            "Master linguistic rules indicate Anda should be capitalized.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=41,
        )]
    if module == "indonesian" and re.search(r"\bRp\s+\d", target):
        return [QAFinding(
            "master_rules.indonesian_rp_spacing",
            "Formatting",
            "Minor",
            "High",
            "Rp space",
            re.sub(r"\bRp\s+(\d)", r"Rp\1", target),
            "Master linguistic rules indicate Indonesian Rp currency has no space before the amount.",
            rule_source="linguisticrules.md",
            autofix_possible=True,
            priority=40,
        )]
    if module == "malay" and re.search(r"\bawak\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.malay_formality",
            "Style",
            "Review",
            "Medium",
            "awak",
            "Consider using Anda for SaaS UI unless informal tone is approved.",
            "Master linguistic rules indicate Malay SaaS UI should use formal Anda.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "malay" and re.search(r"\b(unduh|unggah|kata sandi|sandi)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.malay_indonesian_contamination",
            "Terminology",
            "Major",
            "Medium",
            target,
            "Use Malay-specific SaaS terminology such as muat turun, muat naik, and kata laluan where applicable.",
            "Master linguistic rules warn against Indonesian terminology contamination in Malay.",
            rule_source="linguisticrules.md",
            priority=25,
        )]
    if module == "tagalog" and re.search(r"\b(pook[- ]?sapot|sulatroniko)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.tagalog_overlocalization",
            "Terminology",
            "Review",
            "Medium",
            target,
            "Prefer modern Filipino/Taglish tech terminology unless the client requires pure Tagalog.",
            "Master linguistic rules warn against archaic over-localized Tagalog tech terms.",
            rule_source="linguisticrules.md",
            priority=76,
        )]
    return []


@registry.register("master_rules.remaining_language_profiles", "Style")
def rule_master_linguistic_remaining_language_profiles(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    lang = (target_language or "").lower().replace("_", "-")
    if not target:
        return []
    if module == "portuguese":
        if re.search(r"\btu\b", target, flags=re.IGNORECASE):
            return [QAFinding(
                "master_rules.portuguese_formality",
                "Style",
                "Review",
                "Medium",
                "tu",
                "Verify Portuguese locale and client tone. SaaS UI often uses voce/third-person phrasing rather than informal tu.",
                "Master linguistic rules note Portuguese formality differs by PT-PT/PT-BR locale.",
                rule_source="linguisticrules.md",
                priority=69,
            )]
        if any(x in lang for x in ["pt-pt", "portugal"]) and re.search(r"\b\w+ndo\b", target, flags=re.IGNORECASE):
            return [QAFinding(
                "master_rules.portuguese_ptpt_gerund",
                "Locale Convention",
                "Review",
                "Medium",
                target,
                "Verify if PT-PT should use 'a' + infinitive instead of Brazilian-style gerund phrasing.",
                "Master linguistic rules flag gerund usage as a PT-PT vs PT-BR localization tell.",
                rule_source="linguisticrules.md",
                priority=73,
            )]
        if any(x in lang for x in ["pt-br", "brazil", "brasil"]) and re.search(r"\b(ecr\u00e3|ficheiro)\b", target, flags=re.IGNORECASE):
            return [QAFinding(
                "master_rules.portuguese_brazil_vocabulary",
                "Terminology",
                "Review",
                "Medium",
                target,
                "Verify PT-BR vocabulary. Common SaaS terms usually prefer tela/arquivo over ecrã/ficheiro.",
                "Master linguistic rules warn against mixing Portugal and Brazil Portuguese vocabulary.",
                rule_source="linguisticrules.md",
                priority=74,
            )]
        if any(x in lang for x in ["pt-pt", "portugal"]) and re.search(r"\b(tela|arquivo)\b", target, flags=re.IGNORECASE):
            return [QAFinding(
                "master_rules.portuguese_portugal_vocabulary",
                "Terminology",
                "Review",
                "Medium",
                target,
                "Verify PT-PT vocabulary. Common SaaS terms often prefer ecrã/ficheiro where applicable.",
                "Master linguistic rules warn against mixing Portugal and Brazil Portuguese vocabulary.",
                rule_source="linguisticrules.md",
                priority=74,
            )]
    if module == "polish" and re.search(r"\b(Pan|Pani|Pa\u0144stwo)\b", target):
        return [QAFinding(
            "master_rules.polish_gendered_formality",
            "Style",
            "Review",
            "Medium",
            target,
            "Verify whether an impersonal infinitive or informal UI construction is preferable.",
            "Master linguistic rules note Polish UI often avoids gendered formal Pan/Pani constructions.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    if module == "swahili" and re.search(r"\bsaa\s+(moja|mbili|tatu|nne|tano|sita|saba|nane|tisa|kumi)\b", target, flags=re.IGNORECASE):
        return [QAFinding(
            "master_rules.swahili_time_expression",
            "Locale Convention",
            "Review",
            "Medium",
            target,
            "Verify whether the client wants cultural Swahili time or standard 24-hour UI time.",
            "Master linguistic rules note Swahili time can differ from standard software time conventions.",
            rule_source="linguisticrules.md",
            priority=77,
        )]
    if module == "hausa" and ARABIC_RE.search(target):
        return [QAFinding(
            "master_rules.hausa_ajami_script",
            "Mixed Script",
            "Review",
            "Medium",
            "Arabic/Ajami script",
            "Use Latin Boko script for standard Hausa tech UI unless the client explicitly requests Ajami.",
            "Master linguistic rules indicate standard Hausa software localization uses Latin-based Boko script.",
            rule_source="linguisticrules.md",
            priority=57,
        )]
    return []


@registry.register("master_rules.mongolian_formality", "Style")
def rule_master_linguistic_mongolian_formality(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    if infer_language_module(target_language, "", target) != "mongolian" or not target:
        return []
    if "\u0427\u0438" in target or "\u0447\u0438" in target:
        return [QAFinding(
            "master_rules.mongolian_formality",
            "Style",
            "Review",
            "Medium",
            "\u0427\u0438",
            "Consider using \u0422\u0430 for SaaS/UI address unless informal tone is approved.",
            "Master linguistic rules indicate Mongolian UI uses formal/plural address.",
            rule_source="linguisticrules.md",
            priority=69,
        )]
    return []




# ==========================================================
# EXTRA GLOBAL FORMAT + SCRIPT RULES
# ==========================================================

@registry.register("global.encoding.replacement_character", "Unicode Hygiene")
def rule_replacement_character(segment, rules, target_language, domain):
    _, target = _seg_texts(segment)
    if "�" in target:
        return [QAFinding(
            "global.encoding.replacement_character",
            "Unicode Hygiene",
            "Major",
            "High",
            "�",
            target.replace("�", ""),
            "Replacement character found. This usually indicates broken encoding or damaged copy/paste text.",
            rule_source="Global Unicode rules",
            priority=7,
        )]
    return []


@registry.register("global.bullet_marker.preserve", "Formatting")
def rule_bullet_marker_preserve(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source or not target:
        return []
    src_bullet = BULLET_RE.match(source)
    tgt_bullet = BULLET_RE.match(target)
    if src_bullet and not tgt_bullet:
        marker = src_bullet.group(1)
        return [QAFinding(
            "global.bullet_marker.preserve",
            "Formatting",
            "Minor",
            "High",
            "missing bullet/list marker",
            marker + " " + target.lstrip(),
            "Source begins with a bullet or list marker, so target should preserve an equivalent marker.",
            rule_source="Global source-driven formatting",
            autofix_possible=True,
            priority=18,
        )]
    return []


@registry.register("global.ellipsis.preserve", "Punctuation")
def rule_ellipsis_preserve(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source or not target:
        return []
    if ELLIPSIS_RE.search(source.strip()) and not ELLIPSIS_RE.search(target.strip()):
        return [QAFinding(
            "global.ellipsis.preserve",
            "Punctuation",
            "Minor",
            "High",
            "missing ellipsis",
            target.rstrip() + "…",
            "Source ends with an ellipsis, so target should preserve equivalent ellipsis punctuation.",
            rule_source="Global source-driven punctuation",
            autofix_possible=True,
            priority=19,
        )]
    return []


@registry.register("global.wrapper.brackets", "Formatting")
def rule_wrapper_brackets(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source or not target:
        return []
    wrappers = [("[", "]"), ("(", ")"), ("{", "}"), ("<", ">")]
    for left, right in wrappers:
        if source.strip().startswith(left) and source.strip().endswith(right):
            if not (target.strip().startswith(left) and target.strip().endswith(right)):
                return [QAFinding(
                    "global.wrapper.brackets",
                    "Formatting",
                    "Minor",
                    "High",
                    "missing wrapper bracket",
                    left + target.strip().strip(left + right) + right,
                    f"Source is wrapped with {left}{right}; target should preserve the wrapper.",
                    rule_source="Global source-driven formatting",
                    autofix_possible=True,
                    priority=18,
                )]
    return []


@registry.register("global.linebreak.preserve_count", "Formatting")
def rule_linebreak_preserve_count(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source or not target:
        return []
    # Only flag when source has meaningful line breaks.
    if source.count("\n") >= 1 and abs(source.count("\n") - target.count("\n")) >= 2:
        return [QAFinding(
            "global.linebreak.preserve_count",
            "Formatting",
            "Review",
            "Medium",
            "line break count changed",
            target,
            "Target line break structure differs significantly from source. Verify layout-sensitive content.",
            rule_source="Global layout rules",
            priority=65,
        )]
    return []


@registry.register("global.percent_currency.preserve", "Number")
def rule_percent_currency_preserve(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings = []
    for pattern, label in [(r"\d+\s*%", "percentage"), (r"[$€£₹¥]\s*\d+(?:[.,]\d+)*", "currency value")]:
        src = re.findall(pattern, source or "")
        tgt = re.findall(pattern, target or "")
        missing = [x for x in src if x not in tgt]
        if missing:
            findings.append(QAFinding(
                f"global.number.{label.replace(' ', '_')}.missing",
                "Number",
                "Major",
                "High",
                ", ".join(missing),
                target,
                f"Source {label} is missing or changed in target.",
                rule_source="Global numeric rules",
                priority=6,
            ))
    return findings


@registry.register("global.html_entity.preserve", "Formatting")
def rule_html_entities(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    src = re.findall(r"&[A-Za-z0-9#]+;", source or "")
    tgt = re.findall(r"&[A-Za-z0-9#]+;", target or "")
    missing = [x for x in src if x not in tgt]
    if missing:
        return [QAFinding(
            "global.html_entity.preserve",
            "Formatting",
            "Major",
            "High",
            ", ".join(missing),
            target,
            "HTML/XML entity from source is missing or changed in target.",
            rule_source="Global markup rules",
            priority=6,
        )]
    return []


# ==========================================================
# GLOBAL LANGUAGE MODULES
# ==========================================================

@registry.register("rtl.punctuation.directionality_hint", "Locale Convention")
def rule_rtl_directionality_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if module not in RTL_MODULES:
        return []
    findings = []
    # LRM/RLM controls are not always required; only warn when mixed LTR/RTL with numbers/placeholders can be risky.
    if LATIN_RE.search(target) and (ARABIC_RE.search(target) or HEBREW_RE.search(target)) and not re.search(r"[\u200E\u200F\u202A-\u202E\u2066-\u2069]", target):
        findings.append(QAFinding(
            "rtl.directionality.mixed_text_hint",
            "Locale Convention",
            "Review",
            "Low",
            "mixed RTL/LTR text",
            target,
            "Mixed RTL and Latin text detected. Verify display order around numbers, placeholders, URLs, and product names.",
            rule_source="RTL layout rules",
            priority=88,
        ))
    if module == "arabic" and "," in target and "،" not in target and ARABIC_RE.search(target):
        findings.append(QAFinding(
            "arabic.punctuation.comma_hint",
            "Punctuation",
            "Review",
            "Low",
            ",",
            target.replace(",", "،"),
            "Arabic locale often uses Arabic comma. Verify client style guide before changing.",
            rule_source="Arabic locale hint",
            autofix_possible=False,
            priority=90,
        ))
    return findings


@registry.register("indic.danda.source_driven", "Punctuation")
def rule_indic_danda_source_driven(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if module not in INDIC_MODULES:
        return []
    lang = (target_language or "").lower()
    if (
        source.strip().endswith(".")
        and target
        and not target.strip().endswith((".", "\u0964", "\u0965"))
        and (module in {"gujarati", "telugu", "tamil", "kannada", "malayalam", "sinhala"} or "marathi" in lang or lang == "mr")
    ):
        return [QAFinding(
            "indic.danda.source_driven",
            "Punctuation",
            "Minor",
            "Medium",
            "missing sentence ending",
            target.rstrip() + ".",
            "Source ends with a period. Target should preserve equivalent sentence-ending punctuation according to locale/client style.",
            rule_source="Indic punctuation rules",
            autofix_possible=True,
            priority=34,
        )]
    if (
        source.strip().endswith(".")
        and target
        and not target.strip().endswith((".", "\u0964", "\u0965"))
        and (module in {"bengali", "gurmukhi"} or "hindi" in lang or lang == "hi")
    ):
        return [QAFinding(
            "indic.danda.source_driven",
            "Punctuation",
            "Minor",
            "Medium",
            "missing sentence ending",
            target.rstrip() + "\u0964",
            "Source ends with a period. Target should preserve equivalent sentence-ending punctuation according to locale/client style.",
            rule_source="Indic punctuation rules",
            autofix_possible=True,
            priority=34,
        )]
    # Only a source-driven hint; if source has period and target is Indic script, danda may be preferred by some clients.
    if source.strip().endswith(".") and target and not target.strip().endswith((".", "।", "॥")):
        preferred = "." if module in {"telugu", "tamil", "kannada", "malayalam", "sinhala"} else "।"
        return [QAFinding(
            "indic.danda.source_driven",
            "Punctuation",
            "Minor",
            "Medium",
            "missing sentence ending",
            target.rstrip() + preferred,
            "Source ends with a period. Target should preserve equivalent sentence-ending punctuation according to locale/client style.",
            rule_source="Indic punctuation rules",
            autofix_possible=True,
            priority=34,
        )]
    return []


@registry.register("devanagari.nukta_review_hint", "Unicode Hygiene")
def rule_devanagari_nukta_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "devanagari":
        return []
    # Conservative hint for decomposed nukta patterns.
    if re.search(r"[\u0915-\u0939]\u093C", target):
        return [QAFinding(
            "devanagari.nukta_review_hint",
            "Unicode Hygiene",
            "Review",
            "Low",
            "nukta sequence",
            target,
            "Devanagari nukta sequence detected. Verify normalization and preferred spelling for this locale/client.",
            rule_source="Devanagari Unicode hint",
            priority=92,
        )]
    return []


@registry.register("thai.lao.spacing_hint", "Spacing")
def rule_thai_lao_spacing_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    module = infer_language_module(target_language, source, target)
    if module not in {"thai", "lao", "khmer", "myanmar"}:
        return []
    if re.search(r"[ \t]{2,}", target):
        return [QAFinding(
            f"{module}.spacing.extra_spaces",
            "Spacing",
            "Minor",
            "Medium",
            target,
            re.sub(r"[ \t]{2,}", " ", target),
            "Repeated spaces detected in Southeast Asian script text. Verify phrase spacing.",
            rule_source=f"{module.title()} spacing rules",
            autofix_possible=True,
            priority=42,
        )]
    return []


@registry.register("japanese.fullwidth_punctuation_hint", "Locale Convention")
def rule_japanese_fullwidth_punctuation_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "japanese":
        return []
    if re.search(r"[\u3040-\u30FF\u4E00-\u9FFF]", target) and re.search(r"[!?]", target):
        return [QAFinding(
            "japanese.fullwidth_punctuation_hint",
            "Locale Convention",
            "Review",
            "Low",
            "ASCII !/?",
            target.replace("!", "！").replace("?", "？"),
            "Japanese UI often uses full-width punctuation. Verify client style guide.",
            rule_source="Japanese locale hint",
            priority=90,
        )]
    return []


@registry.register("korean.spacing_review_hint", "Spacing")
def rule_korean_spacing_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "korean":
        return []
    if re.search(r"[ ]{2,}", target):
        return [QAFinding(
            "korean.spacing.extra_spaces",
            "Spacing",
            "Minor",
            "High",
            target,
            re.sub(r" {2,}", " ", target),
            "Multiple spaces detected in Korean text.",
            rule_source="Korean spacing rules",
            autofix_possible=True,
            priority=30,
        )]
    return []


@registry.register("spanish.inverted_punctuation", "Punctuation")
def rule_spanish_inverted_punctuation(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "spanish":
        return []
    findings = []
    stripped = target.strip()
    if source.strip().endswith("?") and "?" in stripped and not stripped.startswith("¿"):
        findings.append(QAFinding(
            "spanish.inverted_question",
            "Punctuation",
            "Minor",
            "Medium",
            "missing ¿",
            "¿" + stripped,
            "Spanish questions usually use opening inverted question mark.",
            rule_source="Spanish locale rules",
            autofix_possible=True,
            priority=38,
        ))
    if source.strip().endswith("!") and "!" in stripped and not stripped.startswith("¡"):
        findings.append(QAFinding(
            "spanish.inverted_exclamation",
            "Punctuation",
            "Minor",
            "Medium",
            "missing ¡",
            "¡" + stripped,
            "Spanish exclamations usually use opening inverted exclamation mark.",
            rule_source="Spanish locale rules",
            autofix_possible=True,
            priority=38,
        ))
    return findings


@registry.register("turkish.case_i_hint", "Locale Convention")
def rule_turkish_i_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "turkish":
        return []
    # Low-confidence hint only when obvious English uppercase I appears in Turkish-looking word.
    if re.search(r"\b[A-Z]*I[A-Z]*[a-zğüşöçıİ]+\b", target):
        return [QAFinding(
            "turkish.case_i_hint",
            "Locale Convention",
            "Review",
            "Low",
            "I/İ/ı casing",
            target,
            "Turkish dotted/dotless I casing may need review.",
            rule_source="Turkish locale hint",
            priority=93,
        )]
    return []


@registry.register("vietnamese.diacritic_density_hint", "Spelling")
def rule_vietnamese_diacritic_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "vietnamese":
        return []
    letters = re.findall(r"[A-Za-zÀ-ỹ]", target)
    if len(letters) < 25:
        return []
    accented = re.findall(r"[À-ỹ]", target)
    if len(accented) / max(len(letters), 1) < 0.03:
        return [QAFinding(
            "vietnamese.diacritic_density_hint",
            "Spelling",
            "Review",
            "Low",
            target[:80],
            target,
            "Vietnamese text has unusually few diacritics. Verify if accents were omitted.",
            rule_source="Vietnamese locale hint",
            priority=94,
        )]
    return []


@registry.register("cyrillic.latin_confusables_hint", "Mixed Script")
def rule_cyrillic_latin_confusables(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "cyrillic":
        return []
    # Only flag words mixing Cyrillic and Latin letters.
    mixed_words = []
    for word in re.findall(r"\b[\w\u0400-\u04FF]+\b", target):
        if LATIN_RE.search(word) and CYRILLIC_RE.search(word):
            mixed_words.append(word)
    if mixed_words:
        return [QAFinding(
            "cyrillic.latin_confusables",
            "Mixed Script",
            "Major",
            "High",
            ", ".join(sorted(set(mixed_words))[:10]),
            target,
            "Word contains mixed Cyrillic and Latin characters, which is usually a copy/paste or spoofing error.",
            rule_source="Cyrillic script rules",
            priority=12,
        )]
    return []


@registry.register("greek.latin_confusables_hint", "Mixed Script")
def rule_greek_latin_confusables(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "greek":
        return []
    mixed_words = []
    for word in re.findall(r"\b[\w\u0370-\u03FF]+\b", target):
        if LATIN_RE.search(word) and GREEK_RE.search(word):
            mixed_words.append(word)
    if mixed_words:
        return [QAFinding(
            "greek.latin_confusables",
            "Mixed Script",
            "Major",
            "High",
            ", ".join(sorted(set(mixed_words))[:10]),
            target,
            "Word contains mixed Greek and Latin characters.",
            rule_source="Greek script rules",
            priority=12,
        )]
    return []


@registry.register("german.capitalization_review_hint", "Style")
def rule_german_capitalization_hint(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if infer_language_module(target_language, source, target) != "german":
        return []
    # Avoid pretending to be a grammar checker; just catch obvious lowercase after article patterns.
    if re.search(r"\b(der|die|das|ein|eine|einen|dem|den)\s+[a-zäöüß]{4,}\b", target):
        return [QAFinding(
            "german.noun_capitalization_hint",
            "Style",
            "Review",
            "Low",
            "possible lowercase noun",
            target,
            "Possible German noun capitalization issue. Human review recommended.",
            rule_source="German locale hint",
            priority=95,
        )]
    return []




# ==========================================================
# OFFLINE CORRECTION DICTIONARIES + CLIENT QA HISTORY RULES
# ==========================================================

# High-precision built-in typo dictionary for common English UI/source-copy issues.
# This is intentionally small. Client/company dictionaries should come from Rules ZIP.
BUILTIN_CORRECTIONS = {
    "global": [
        {"wrong": "teh", "correct": "the", "category": "Spelling", "severity": "Minor"},
        {"wrong": "recieve", "correct": "receive", "category": "Spelling", "severity": "Minor"},
        {"wrong": "recieved", "correct": "received", "category": "Spelling", "severity": "Minor"},
        {"wrong": "seperate", "correct": "separate", "category": "Spelling", "severity": "Minor"},
        {"wrong": "definately", "correct": "definitely", "category": "Spelling", "severity": "Minor"},
        {"wrong": "occured", "correct": "occurred", "category": "Spelling", "severity": "Minor"},
        {"wrong": "sucess", "correct": "success", "category": "Spelling", "severity": "Minor"},
        {"wrong": "sucessfully", "correct": "successfully", "category": "Spelling", "severity": "Minor"},
        {"wrong": "adress", "correct": "address", "category": "Spelling", "severity": "Minor"},
        {"wrong": "wierd", "correct": "weird", "category": "Spelling", "severity": "Minor"},
        {"wrong": "calender", "correct": "calendar", "category": "Spelling", "severity": "Minor"},
        {"wrong": "untill", "correct": "until", "category": "Spelling", "severity": "Minor"},
    ],
    "telugu": [
        {"wrong": "పాస్వర్డ్", "correct": "పాస్‌వర్డ్", "category": "Spelling", "severity": "Minor"},
        {"wrong": "పాస్ వర్డ్", "correct": "పాస్‌వర్డ్", "category": "Spelling", "severity": "Minor"},
        {"wrong": "డౌన్లోడ్", "correct": "డౌన్‌లోడ్", "category": "Spelling", "severity": "Minor"},
        {"wrong": "డౌన్ లోడ్", "correct": "డౌన్‌లోడ్", "category": "Spelling", "severity": "Minor"},
        {"wrong": "అప్లోడ్", "correct": "అప్‌లోడ్", "category": "Spelling", "severity": "Minor"},
        {"wrong": "అప్ లోడ్", "correct": "అప్‌లోడ్", "category": "Spelling", "severity": "Minor"},
        {"wrong": "డాష్బోర్డ్", "correct": "డాష్‌బోర్డ్", "category": "Spelling", "severity": "Minor"},
        {"wrong": "డాష్ బోర్డ్", "correct": "డాష్‌బోర్డ్", "category": "Spelling", "severity": "Minor"},
    ],
}


def _compile_correction_pattern(wrong: str) -> Optional[Pattern[str]]:
    wrong = normalize_for_qa(wrong)
    if not wrong:
        return None

    # For Latin words, use word boundaries to avoid changing inside larger words.
    if re.fullmatch(r"[A-Za-z][A-Za-z'-]*", wrong):
        return re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
    return re.compile(re.escape(wrong))


@lru_cache(maxsize=32)
def _builtin_correction_entries(module: str) -> Tuple[Dict[str, Any], ...]:
    entries: List[Dict[str, Any]] = []
    for item in BUILTIN_CORRECTIONS.get(module, []):
        wrong = normalize_for_qa(item.get("wrong", ""))
        pattern = _compile_correction_pattern(wrong)
        if pattern is None:
            continue
        entries.append({**item, "wrong": wrong, "pattern": pattern})
    return tuple(entries)


def _client_correction_cache_key(rules: Dict[str, Any]) -> str:
    relevant = {
        "corrections": (rules or {}).get("corrections", []),
        "chunks": [
            {
                "source": (chunk or {}).get("source", "Client Rules"),
                "text": (chunk or {}).get("text", ""),
            }
            for chunk in (rules or {}).get("chunks", [])
            if isinstance(chunk, dict)
        ],
    }
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True, default=str)


@lru_cache(maxsize=64)
def _parse_client_correction_lines_cached(rules_key: str) -> Tuple[Dict[str, Any], ...]:
    try:
        rules = json.loads(rules_key)
    except Exception as exc:
        LOGGER.warning("Unable to parse cached client correction rules: %s", exc)
        return tuple()
    return tuple(_parse_client_correction_lines_uncached(rules))


def _parse_client_correction_lines(rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [dict(item) for item in _parse_client_correction_lines_cached(_client_correction_cache_key(rules or {}))]


def _parse_client_correction_lines_uncached(rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract client correction dictionary entries from Rules ZIP chunks.

    Supported high-precision formats inside txt/csv/docx/xlsx rule files:
    - wrong -> correct
    - wrong => correct
    - wrong | correct | error_type | severity
    - wrong,correct,error_type,severity
    - forbidden: X -> preferred: Y

    This lets companies upload their own spelling/grammar/style/terminology
    dictionaries and lets CogniSweep work without API keys.
    """
    corrections: List[Dict[str, str]] = []

    # Also support explicit correction arrays if future parser adds them.
    for item in (rules or {}).get("corrections", []):
        wrong = normalize_for_qa(item.get("wrong", ""))
        correct = normalize_for_qa(item.get("correct", ""))
        if wrong and correct:
            pattern = _compile_correction_pattern(wrong)
            if pattern is None:
                continue
            corrections.append({
                "wrong": wrong,
                "correct": correct,
                "category": item.get("error_type", item.get("category", "Client Rule")),
                "severity": item.get("severity", "Major"),
                "source": item.get("source", "Client Rules"),
                "pattern": pattern,
            })

    for chunk in (rules or {}).get("chunks", []):
        source_name = chunk.get("source", "Client Rules")
        for raw_line in str(chunk.get("text", "")).splitlines():
            line = normalize_for_qa(raw_line)
            if not line or len(line) > 500:
                continue

            # Ignore obvious prose lines.
            if not any(sep in line for sep in ["->", "=>", "|", ","]):
                continue

            category = "Client Rule"
            severity = "Major"
            wrong = correct = ""

            if "->" in line or "=>" in line:
                sep = "->" if "->" in line else "=>"
                left, right = [p.strip() for p in line.split(sep, 1)]
                left = re.sub(r"^(wrong|bad|forbidden|avoid|source)\s*[:=]\s*", "", left, flags=re.I).strip()
                right = re.sub(r"^(correct|preferred|use|target|suggestion)\s*[:=]\s*", "", right, flags=re.I).strip()
                wrong, correct = left, right
            elif "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    wrong, correct = parts[0], parts[1]
                    if len(parts) >= 3 and parts[2]:
                        category = parts[2]
                    if len(parts) >= 4 and parts[3]:
                        severity = parts[3]
            elif "," in line:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2 and all(len(p) < 120 for p in parts[:2]):
                    # Avoid parsing ordinary prose with commas.
                    wrong, correct = parts[0], parts[1]
                    if len(parts) >= 3 and parts[2]:
                        category = parts[2]
                    if len(parts) >= 4 and parts[3]:
                        severity = parts[3]

            wrong = wrong.strip().strip('"“”')
            correct = correct.strip().strip('"“”')
            if not wrong or not correct:
                continue
            if wrong.lower() in {"wrong", "source", "bad", "forbidden"}:
                continue
            if correct.lower() in {"correct", "target", "preferred"}:
                continue
            if wrong == correct:
                continue

            pattern = _compile_correction_pattern(wrong)
            if pattern is None:
                continue
            corrections.append({
                "wrong": wrong,
                "correct": correct,
                "category": category or "Client Rule",
                "severity": severity if severity in {"Critical", "Major", "Minor", "Review"} else "Major",
                "source": source_name,
                "pattern": pattern,
            })

    # Dedupe
    seen = set()
    deduped = []
    for item in corrections:
        key = (item["wrong"], item["correct"], item.get("category", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _apply_correction_to_text(text: str, wrong: str, correct: str, pattern: Optional[Pattern[str]] = None) -> Tuple[str, int]:
    if not wrong and pattern is None:
        return text, 0

    pattern = pattern or _compile_correction_pattern(wrong)
    if pattern is None:
        return text, 0

    return pattern.subn(correct, text)


@registry.register("global.offline_dictionary.client_and_builtin", "Spelling")
def rule_offline_correction_dictionary(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not target:
        return []

    module = infer_language_module(target_language, source, target)
    dictionary_entries = []
    dictionary_entries.extend(_builtin_correction_entries("global"))
    dictionary_entries.extend(_builtin_correction_entries(module))
    dictionary_entries.extend(_parse_client_correction_lines(rules))

    findings: List[QAFinding] = []
    for entry in dictionary_entries:
        wrong = normalize_for_qa(entry.get("wrong", ""))
        correct = normalize_for_qa(entry.get("correct", ""))
        if not wrong or not correct:
            continue
        new_text, count = _apply_correction_to_text(target, wrong, correct, entry.get("pattern"))
        if count <= 0:
            continue
        category = entry.get("category", "Spelling") or "Spelling"
        severity = entry.get("severity", "Minor") or "Minor"
        findings.append(QAFinding(
            "global.offline_dictionary.client_and_builtin",
            category,
            severity if severity in {"Critical", "Major", "Minor", "Review"} else "Major",
            "High",
            wrong,
            new_text,
            "Offline correction dictionary matched this target text. This can come from built-in rules or uploaded client QA history/rule packs.",
            rule_source=entry.get("source", "Offline Dictionary"),
            autofix_possible=True,
            priority=11,
        ))
    return findings


@registry.register("global.offline_semantic_limits.notice", "Offline QA Coverage")
def rule_offline_semantic_limits(segment, rules, target_language, domain):
    """Adds no report row. Kept as registered documentation hook.

    Accuracy, grammar, fluency, and style are not universally solvable offline
    for all languages without client dictionaries, translation memory, or local ML.
    The app should use:
    - deterministic rules for objective checks,
    - client correction dictionaries for spelling/grammar/style/terminology,
    - translation memory for consistency,
    - AI/API or local ML for deep semantic accuracy.
    """
    return []


# ==========================================================
# V5 GLOBAL QUALITY RULES: OFFLINE APPROXIMATIONS
# ==========================================================

@registry.register("global.accuracy.blank_or_too_short", "Accuracy")
def rule_blank_or_too_short_target(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not source:
        return []
    # If extraction includes an empty translation in QA-like context, flag it.
    if not target:
        return [QAFinding(
            "global.accuracy.blank_target",
            "Accuracy",
            "Major",
            "High",
            "blank target",
            "Provide translation or confirm the segment is intentionally blank.",
            "Target translation is blank while source has content.",
            rule_source="Global accuracy rules",
            priority=8,
        )]
    # Conservative omission hint only for clearly long source and very short target.
    src_len = len(re.sub(r"\s+", "", source))
    tgt_len = len(re.sub(r"\s+", "", target))
    if src_len >= 60 and tgt_len <= max(8, int(src_len * 0.12)):
        return [QAFinding(
            "global.accuracy.possible_omission",
            "Accuracy",
            "Review",
            "Medium",
            target,
            target,
            "Target is much shorter than source. Verify possible omission.",
            rule_source="Global accuracy heuristic",
            priority=70,
        )]
    return []


@registry.register("global.terminology.forbidden_target_terms", "Terminology")
def rule_forbidden_target_terms(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings = []
    # Supports rules lines such as:
    # forbidden: old term -> preferred: new term
    # avoid old term -> use new term
    for item in _parse_client_correction_lines(rules):
        category = str(item.get("category", "")).lower()
        source_name = item.get("source", "Client Rules")
        wrong = normalize_for_qa(item.get("wrong", ""))
        correct = normalize_for_qa(item.get("correct", ""))
        if not wrong or not correct:
            continue
        if any(k in category for k in ["forbidden", "avoid", "terminology", "style", "client rule"]):
            # If target contains forbidden term, flag it.
            pattern = item.get("pattern") or re.compile(re.escape(wrong), re.IGNORECASE if re.fullmatch(r"[A-Za-z][A-Za-z0-9' -]*", wrong) else 0)
            if pattern.search(target):
                findings.append(QAFinding(
                    "global.terminology.forbidden_target_terms",
                    "Terminology",
                    "Major",
                    "High",
                    wrong,
                    pattern.sub(correct, target),
                    "Target contains a forbidden/deprecated term from client rules.",
                    rule_source=source_name,
                    autofix_possible=True,
                    priority=9,
                ))
    return findings


@registry.register("global.grammar.client_correction_patterns", "Grammar")
def rule_client_grammar_patterns(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings = []
    for item in _parse_client_correction_lines(rules):
        category = str(item.get("category", "")).lower()
        if "grammar" not in category:
            continue
        wrong = normalize_for_qa(item.get("wrong", ""))
        correct = normalize_for_qa(item.get("correct", ""))
        if not wrong or not correct:
            continue
        new_text, count = _apply_correction_to_text(target, wrong, correct, item.get("pattern"))
        if count > 0:
            findings.append(QAFinding(
                "global.grammar.client_correction_patterns",
                "Grammar",
                item.get("severity", "Major") if item.get("severity") in {"Critical", "Major", "Minor", "Review"} else "Major",
                "High",
                wrong,
                new_text,
                "Grammar correction matched an uploaded client QA-history/rule-pack pattern.",
                rule_source=item.get("source", "Client Grammar Rules"),
                autofix_possible=True,
                priority=10,
            ))
    return findings


@registry.register("global.style.client_correction_patterns", "Style")
def rule_client_style_patterns(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    findings = []
    for item in _parse_client_correction_lines(rules):
        category = str(item.get("category", "")).lower()
        if "style" not in category and "tone" not in category:
            continue
        wrong = normalize_for_qa(item.get("wrong", ""))
        correct = normalize_for_qa(item.get("correct", ""))
        if not wrong or not correct:
            continue
        new_text, count = _apply_correction_to_text(target, wrong, correct, item.get("pattern"))
        if count > 0:
            findings.append(QAFinding(
                "global.style.client_correction_patterns",
                "Style",
                item.get("severity", "Minor") if item.get("severity") in {"Critical", "Major", "Minor", "Review"} else "Minor",
                "High",
                wrong,
                new_text,
                "Style correction matched an uploaded client QA-history/rule-pack pattern.",
                rule_source=item.get("source", "Client Style Rules"),
                autofix_possible=True,
                priority=30,
            ))
    return findings


@registry.register("global.language_profile.info", "Language Profile")
def rule_language_profile_noop(segment, rules, target_language, domain):
    # Documentation/no-op rule: language profiles are used by other rules.
    return []


# ==========================================================
# OPTIONAL NO-OPENAI GLOBAL SPELLING / GRAMMAR / STYLE ENGINE
# ==========================================================

LANGUAGETOOL_CODES = {
    "global": "en-US",
    "latin": "en-US",
    "english": "en-US",
    "french": "fr",
    "spanish": "es",
    "german": "de-DE",
    "italian": "it",
    "portuguese": "pt-PT",
    "turkish": "tr",
    "vietnamese": "vi",
    "cyrillic": "ru-RU",
    "russian": "ru-RU",
    "ukrainian": "uk-UA",
    "greek": "el",
    "arabic": "ar",
    "dutch": "nl",
    "polish": "pl-PL",
    "catalan": "ca-ES",
    "romanian": "ro-RO",
    "slovak": "sk-SK",
    "slovenian": "sl-SI",
    "swedish": "sv",
    "danish": "da-DK",
}


def _language_tool_code(target_language: str, source: str, target: str) -> Optional[str]:
    """Map user-selected language/locale to LanguageTool language code.

    This is used only when the user enables the no-OpenAI grammar engine.
    """
    lang = (target_language or "").strip().lower()
    module = infer_language_module(target_language, source, target)

    for key, code in LANGUAGETOOL_CODES.items():
        if key != "global" and key in lang:
            return code

    locale_map = {
        "en": "en-US", "en-us": "en-US", "en-gb": "en-GB",
        "fr": "fr", "fr-fr": "fr",
        "es": "es", "es-es": "es",
        "de": "de-DE", "de-de": "de-DE",
        "it": "it", "pt": "pt-PT", "pt-br": "pt-BR",
        "tr": "tr", "vi": "vi", "ru": "ru-RU", "uk": "uk-UA",
        "el": "el", "ar": "ar", "nl": "nl", "pl": "pl-PL",
        "ca": "ca-ES", "ro": "ro-RO", "sk": "sk-SK", "sl": "sl-SI",
        "sv": "sv", "da": "da-DK",
    }
    if lang in locale_map:
        return locale_map[lang]

    if module in LANGUAGETOOL_CODES:
        return LANGUAGETOOL_CODES[module]

    # Auto fallback only for Latin text; avoids false grammar engine calls for unsupported scripts.
    if module == "global" and re.search(r"[A-Za-z]", target or ""):
        return "en-US"

    return None


@lru_cache(maxsize=24)
def _get_languagetool(code: str, mode: str = "local"):
    """Create a LanguageTool checker.

    mode = local: attempts local/private LanguageTool. Better privacy, but needs Java/server support.
    mode = public: uses LanguageTool public service. No API key, but text is sent externally.
    """
    if language_tool_python is None:
        return None
    try:
        if mode == "local":
            return language_tool_python.LanguageTool(code)
        return language_tool_python.LanguageToolPublicAPI(code)
    except Exception as exc:
        LOGGER.debug("Unable to initialize LanguageTool %s in %s mode: %s", code, mode, exc)
        return None


def _map_languagetool_category(match: Any) -> Tuple[str, str]:
    category = str(getattr(match, "category", "") or "").lower()
    issue_type = str(getattr(match, "ruleIssueType", "") or "").lower()
    rule_id = str(getattr(match, "ruleId", "") or "").lower()

    if "typ" in category or "misspell" in issue_type or "morfologik" in rule_id or "spelling" in issue_type:
        return "Spelling", "High"
    if "grammar" in category or "grammar" in issue_type:
        return "Grammar", "Medium"
    if "style" in category or "style" in issue_type:
        return "Style", "Medium"
    if "punct" in category or "typography" in category:
        return "Punctuation", "Medium"
    if "confused" in rule_id or "word" in category:
        return "Grammar", "Medium"
    return "Grammar", "Medium"



def _check_languagetool_public_http(text: str, code: str) -> List[Dict[str, Any]]:
    """Check text using LanguageTool HTTP API without OpenAI/Gemini.

    This avoids Java/local package dependency. It may send text to LanguageTool's
    public service, so use only for non-confidential data or testing.
    """
    try:
        res = requests.post(
            "https://api.languagetool.org/v2/check",
            data={"text": text, "language": code, "enabledOnly": "false"},
            timeout=20,
        )
        if res.status_code >= 400:
            return []
        data = res.json()
        return data.get("matches", []) if isinstance(data, dict) else []
    except (requests.RequestException, ValueError) as exc:
        LOGGER.debug("LanguageTool public HTTP check failed for %s: %s", code, exc)
        return []


def _match_dict_to_finding(m: Dict[str, Any], target: str, code: str) -> Optional[QAFinding]:
    try:
        start = int(m.get("offset", 0) or 0)
        length = int(m.get("length", 0) or 0)
    except (TypeError, ValueError) as exc:
        LOGGER.debug("Invalid LanguageTool match offsets: %s", exc)
        return None
    if length <= 0:
        return None
    wrong = target[start:start + length]
    if not wrong.strip():
        return None
    replacements = [r.get("value", "") for r in m.get("replacements", []) if isinstance(r, dict) and r.get("value")]
    replacement = replacements[0] if replacements else ""
    suggestion = target[:start] + replacement + target[start + length:] if replacement else target
    rule = m.get("rule", {}) if isinstance(m.get("rule"), dict) else {}
    category_obj = rule.get("category", {}) if isinstance(rule.get("category"), dict) else {}
    category_name = str(category_obj.get("name", "") or "").lower()
    issue_type = str(rule.get("issueType", "") or "").lower()
    rule_id = str(rule.get("id", "LANGUAGETOOL_RULE") or "LANGUAGETOOL_RULE")
    message = str(m.get("message", "LanguageTool grammar/spelling/style issue.") or "LanguageTool grammar/spelling/style issue.")
    # map category
    low = " ".join([category_name, issue_type, rule_id.lower(), message.lower()])
    if "typ" in low or "spell" in low or "misspell" in low or "morfologik" in low:
        category, confidence = "Spelling", "High"
    elif "grammar" in low or "agreement" in low:
        category, confidence = "Grammar", "Medium"
    elif "style" in low or "redund" in low:
        category, confidence = "Style", "Medium"
    elif "punct" in low or "typography" in low:
        category, confidence = "Punctuation", "Medium"
    else:
        category, confidence = "Grammar", "Medium"
    if wrong in extract_placeholders(target) or wrong in extract_tags(target) or wrong in extract_urls(target) or wrong in extract_emails(target):
        return None
    return QAFinding(
        f"global.languagetool.http.{rule_id}",
        category,
        "Minor" if category in {"Spelling", "Punctuation", "Style"} else "Review",
        confidence,
        wrong,
        suggestion,
        message,
        rule_source=f"LanguageTool HTTP {code}",
        autofix_possible=bool(replacement),
        priority=40 if confidence == "High" else 68,
    )

@registry.register("global.languagetool.spell_grammar_style", "Grammar")
def rule_languagetool_global(segment, rules, target_language, domain):
    """Optional no-OpenAI grammar/spell/style layer using LanguageTool.

    This is not semantic accuracy. It detects rule-based spelling, grammar,
    punctuation, and style issues supported by LanguageTool for the selected language.
    """
    if not bool(rules.get("_enable_languagetool", False)):
        return []

    source, target = _seg_texts(segment)
    if not target or len(target) < 3:
        return []
    if len(target) > int(rules.get("_languagetool_max_chars", 1200) or 1200):
        return []

    code = _language_tool_code(target_language, source, target)
    if not code:
        return []

    mode = str(rules.get("_languagetool_mode", "local")).lower()
    if mode not in {"public", "public-http", "http", "local"}:
        mode = "local"

    findings: List[QAFinding] = []

    # Public HTTP mode works without OpenAI/Gemini and without Java.
    if mode in {"public", "public-http", "http"}:
        matches = _check_languagetool_public_http(target, code)
        for m in matches[:12]:
            finding = _match_dict_to_finding(m, target, code)
            if finding:
                findings.append(finding)
        return findings

    # Local mode uses language_tool_python if available.
    tool = _get_languagetool(code, mode)
    if tool is None:
        return []

    try:
        matches = tool.check(target)
    except Exception as exc:
        LOGGER.debug("Local LanguageTool check failed for %s: %s", code, exc)
        return []

    for m in matches[:12]:
        start = int(getattr(m, "offset", 0) or 0)
        length = int(getattr(m, "errorLength", 0) or 0)
        if length <= 0:
            continue
        wrong = target[start:start + length]
        if not wrong.strip():
            continue

        replacements = list(getattr(m, "replacements", []) or [])
        replacement = replacements[0] if replacements else ""
        suggestion = target[:start] + replacement + target[start + length:] if replacement else target
        category, confidence = _map_languagetool_category(m)
        message = str(getattr(m, "message", "") or "LanguageTool grammar/spelling/style issue.")
        rule_id = str(getattr(m, "ruleId", "") or "LANGUAGETOOL_RULE")

        if wrong in extract_placeholders(target) or wrong in extract_tags(target) or wrong in extract_urls(target) or wrong in extract_emails(target):
            continue

        findings.append(QAFinding(
            f"global.languagetool.{rule_id}",
            category,
            "Minor" if category in {"Spelling", "Punctuation", "Style"} else "Review",
            confidence,
            wrong,
            suggestion,
            message,
            rule_source=f"LanguageTool {code}",
            autofix_possible=bool(replacement),
            priority=40 if confidence == "High" else 68,
        ))
    return findings



# ==========================================================
# V7 NO-API TARGET LANGUAGE + UNTRANSLATED TEXT DETECTION
# ==========================================================

def _expected_script_regex_for_module(module: str) -> Optional[Pattern[str]]:
    mapping = {
        "telugu": TELUGU_RE,
        "devanagari": DEVANAGARI_RE,
        "bengali": BENGALI_RE,
        "gurmukhi": GURMUKHI_RE,
        "gujarati": GUJARATI_RE,
        "odia": ODIA_RE,
        "tamil": TAMIL_RE,
        "kannada": KANNADA_RE,
        "malayalam": MALAYALAM_RE,
        "sinhala": SINHALA_RE,
        "arabic": ARABIC_RE,
        "hebrew": HEBREW_RE,
        "thai": THAI_RE,
        "lao": LAO_RE,
        "khmer": KHMER_RE,
        "myanmar": MYANMAR_RE,
        "cyrillic": CYRILLIC_RE,
        "greek": GREEK_RE,
        "cjk": CJK_RE,
        "japanese": CJK_RE,
        "korean": CJK_RE,
    }
    return mapping.get(module)


def _selected_target_is_auto(target_language: str) -> bool:
    value = (target_language or "").strip().lower()
    return value in {"", "auto", "auto-detect", "autodetect", "detect"}


@registry.register("global.language.expected_script_missing", "Mixed Script")
def rule_expected_script_missing(segment, rules, target_language, domain):
    """When target language is explicitly selected, flag targets that look untranslated.

    This is critical for no-API mode. If the user selects Hindi/Telugu/Arabic/etc.
    and target is still English/Latin, Auto-detect cannot infer intent unless we
    use the selected target_language as the authority.
    """
    source, target = _seg_texts(segment)
    if not target or _selected_target_is_auto(target_language):
        return []

    module = infer_language_module(target_language, source, target)
    expected_re = _expected_script_regex_for_module(module)
    if expected_re is None:
        return []

    protected = set(protected_terms_from_rules(rules))
    protected.update(extract_urls(target))
    protected.update(extract_emails(target))
    protected.update(extract_skus(target))
    protected.update(extract_placeholders(target))
    protected.update(extract_tags(target))

    # If there is no expected-script text but target contains Latin words, it is likely untranslated.
    if not expected_re.search(target) and LATIN_RE.search(target):
        stripped = target.strip()
        if stripped in protected or any(stripped in p for p in protected):
            return []
        return [QAFinding(
            "global.language.expected_script_missing",
            "Mixed Script",
            "Major",
            "High",
            target,
            "Translate this segment into the selected target language, unless it is approved DNT/brand text.",
            f"Target language is set to '{target_language}', but the target does not contain the expected script/language pattern.",
            rule_source="Global target-language check",
            priority=7,
        )]

    # If there is expected-script text but also unprotected Latin words, flag leftovers.
    if expected_re.search(target) and LATIN_RE.search(target):
        latin_words = re.findall(r"\b[A-Za-z][A-Za-z0-9._-]*\b", target)
        leftovers = []
        for word in latin_words:
            if word in protected or any(word in p for p in protected):
                continue
            if word.isupper() and len(word) <= 6:
                continue
            leftovers.append(word)
        if leftovers:
            return [QAFinding(
                "global.language.untranslated_latin_leftover",
                "Mixed Script",
                "Major",
                "High",
                ", ".join(sorted(set(leftovers))[:12]),
                target,
                f"Untranslated Latin/English words appear in a '{target_language}' target. Add allowed words to DNT/glossary if intentional.",
                rule_source="Global target-language check",
                priority=8,
            )]
    return []


@registry.register("global.readability.basic_repetition", "Readability")
def rule_basic_repetition_readability(segment, rules, target_language, domain):
    """No-API readability heuristic: repeated adjacent words/tokens."""
    _, target = _seg_texts(segment)
    if not target:
        return []
    words = re.findall(r"\b[\wÀ-ỹ\u0900-\u097F\u0C00-\u0C7F]+\b", target.lower())
    repeated = []
    for a, b in zip(words, words[1:]):
        if a == b and len(a) > 2:
            repeated.append(a)
    if repeated:
        return [QAFinding(
            "global.readability.basic_repetition",
            "Readability",
            "Minor",
            "High",
            " ".join(repeated[:5]),
            target,
            "Repeated adjacent word found. This is usually a readability or copy/paste issue.",
            rule_source="Global no-API readability rules",
            priority=26,
        )]
    return []


@registry.register("global.grammar.simple_english_patterns", "Grammar")
def rule_simple_english_grammar_patterns(segment, rules, target_language, domain):
    """Small no-API English grammar safety net.

    This is intentionally limited. Broader grammar requires LanguageTool, local ML,
    or client correction dictionaries.
    """
    source, target = _seg_texts(segment)
    lang = (target_language or "").strip().lower()
    module = infer_language_module(target_language, source, target)
    if module not in {"global", "latin", "english"} and "english" not in lang and lang not in {"en", "en-us", "en-gb"}:
        return []

    patterns = [
        (r"\bI has\b", "I have", "Subject-verb agreement: 'I has' should be 'I have'."),
        (r"\bThis are\b", "This is", "Subject-verb agreement: 'This are' should be 'This is'."),
        (r"\bThese is\b", "These are", "Subject-verb agreement: 'These is' should be 'These are'."),
        (r"\bYou was\b", "You were", "Subject-verb agreement: 'You was' should be 'You were'."),
        (r"\bWe was\b", "We were", "Subject-verb agreement: 'We was' should be 'We were'."),
        (r"\ba document are\b", "a document is", "Subject-verb agreement issue."),
    ]

    findings = []
    for pattern, replacement, explanation in patterns:
        if re.search(pattern, target, flags=re.IGNORECASE):
            suggestion = re.sub(pattern, replacement, target, flags=re.IGNORECASE)
            findings.append(QAFinding(
                "global.grammar.simple_english_patterns",
                "Grammar",
                "Minor",
                "High",
                re.search(pattern, target, flags=re.IGNORECASE).group(0),
                suggestion,
                explanation,
                rule_source="Built-in English grammar patterns",
                autofix_possible=True,
                priority=21,
            ))
    return findings


@registry.register("global.brackets.localized_ui_structure", "Formatting")
def rule_localized_square_bracket_structure(segment, rules, target_language, domain):
    """Square-bracketed UI labels can be localized, but bracket delimiters should survive.

    Correct examples:
    [Welcome Screen] -> [வெல்கம் திரை]
    Already have an account? [Log In] -> ... [உள்நுழைக]

    Incorrect examples:
    [Welcome Screen] -> வெல்கம் திரை       # brackets dropped
    Already have an account? [Log In] -> ... உள்நுழைக  # bracketed action lost
    """
    source, target = _seg_texts(segment)
    src_tokens = re.findall(r"\[[^\[\]\n]{1,120}\]", source or "")
    if not src_tokens:
        return []

    tgt_tokens = re.findall(r"\[[^\[\]\n]{1,120}\]", target or "")
    findings = []

    # If whole source segment is bracketed, target can localize the inside text,
    # but should still be bracketed.
    src_clean = (source or "").strip()
    tgt_clean = (target or "").strip()
    if len(src_tokens) == 1 and src_clean == src_tokens[0]:
        if not (tgt_clean.startswith("[") and tgt_clean.endswith("]")):
            findings.append(QAFinding(
                "global.brackets.localized_ui_structure",
                "Formatting",
                "Minor",
                "High",
                src_tokens[0],
                f"[{tgt_clean.strip('[] ')}]" if tgt_clean else src_tokens[0],
                "Square-bracketed UI label can be localized, but bracket delimiters should be preserved.",
                rule_source="Global localization format rules",
                autofix_possible=True,
                priority=18,
            ))
        return findings

    # For inline bracketed UI actions, do not require exact source text, but require
    # the same number of bracketed groups unless client rules say otherwise.
    if len(tgt_tokens) < len(src_tokens):
        findings.append(QAFinding(
            "global.brackets.localized_ui_structure",
            "Formatting",
            "Minor",
            "Medium",
            ", ".join(src_tokens),
            target,
            "Source contains bracketed UI/action label(s). The text inside can be localized, but bracketed structure appears missing in target.",
            rule_source="Global localization format rules",
            autofix_possible=False,
            priority=45,
        ))
    return findings



# ==========================================================
# V15 GLOBAL PREFIX/AFFIX PRESERVATION RULES
# ==========================================================

GLOBAL_LEADING_AFFIX_RE = re.compile(r"^(\s*(?:(?:[•∙◦▪▫●○\-–—*])\s*)?(?:(?:[\U0001F300-\U0001FAFF\u2600-\u27BF]\ufe0f?)\s*)*)")

@registry.register("global.affix.leading_icon_preserve", "Formatting")
def rule_leading_icon_affix_preserve(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    src_m = GLOBAL_LEADING_AFFIX_RE.match(source or "")
    if not src_m or not src_m.group(1).strip():
        return []
    src_affix = src_m.group(1)
    if target.startswith(src_affix.strip()) or target.startswith(src_affix):
        return []
    suggestion = src_affix + target.lstrip()
    return [QAFinding(
        "global.affix.leading_icon_preserve",
        "Formatting",
        "Minor",
        "High",
        src_affix.strip(),
        suggestion,
        "Source begins with a bullet/icon/emoji prefix. The prefix should be preserved exactly in the target while the following text can be localized.",
        rule_source="Global localization format rules",
        autofix_possible=True,
        priority=14,
    )]

# ==========================================================
# SCORING + PUBLIC API
# ==========================================================

SEVERITY_ORDER = {"Critical": 0, "Major": 1, "Minor": 2, "Review": 3}
CONFIDENCE_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def dedupe_and_score(findings: List[QAFinding]) -> List[QAFinding]:
    seen = set()
    output: List[QAFinding] = []
    for f in findings:
        key = (f.rule_id, f.category, f.wrong_part, f.suggestion)
        if key in seen:
            continue
        seen.add(key)
        output.append(f)

    output.sort(
        key=lambda f: (
            CONFIDENCE_ORDER.get(f.confidence, 2),
            SEVERITY_ORDER.get(f.severity, 3),
            f.priority,
            f.rule_id,
        )
    )
    return output


def deterministic_checks_v2(
    segment: Dict[str, Any],
    rules: Optional[Dict[str, Any]] = None,
    target_language: str = "Auto-detect",
    domain: str = "Auto-detect",
    enable_zwnj: bool = True,
    enable_language_tool: bool = False,
    language_tool_mode: str = "local",
    language_tool_max_chars: int = 1200,
) -> List[Dict[str, Any]]:
    """Drop-in replacement for app.py deterministic_checks."""
    source, target = _seg_texts(segment)
    if not target:
        return []
    if target.lstrip().startswith("="):
        return []

    runtime_rules = dict(rules or {})
    runtime_rules["_enable_languagetool"] = bool(enable_language_tool)
    runtime_rules["_languagetool_mode"] = language_tool_mode
    runtime_rules["_languagetool_max_chars"] = int(language_tool_max_chars or 1200)

    findings = registry.run(segment, runtime_rules, target_language, domain)

    if not enable_zwnj:
        findings = [f for f in findings if not f.rule_id.startswith("telugu.zwnj")]

    findings = dedupe_and_score(findings)
    return [to_report_row(segment, f) for f in findings]
