
"""
ErrorSweep QA Engine v2
-----------------------
Modular, source-driven offline QA rule engine.

This module is designed to sit beside the Streamlit app. It does not replace
file extraction/output. It only receives segment dictionaries and returns
report rows compatible with the existing ErrorSweep report schema.

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

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple


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
LATIN_RE = re.compile(r"[A-Za-z]")

URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
TAG_RE = re.compile(r"<[^>]+>")
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

    if any(x in lang for x in ["arabic", "urdu", "persian", "farsi"]) or lang in {"ar", "ur", "fa"} or ARABIC_RE.search(target):
        return "arabic"
    if "hebrew" in lang or lang == "he" or HEBREW_RE.search(target):
        return "hebrew"

    if any(x in lang for x in ["thai"]) or lang == "th" or THAI_RE.search(target):
        return "thai"
    if "lao" in lang or lang == "lo" or LAO_RE.search(target):
        return "lao"
    if "khmer" in lang or "cambodian" in lang or lang == "km" or KHMER_RE.search(target):
        return "khmer"
    if "myanmar" in lang or "burmese" in lang or lang == "my" or MYANMAR_RE.search(target):
        return "myanmar"

    if any(x in lang for x in ["chinese", "japanese", "korean", "cjk", "mandarin", "cantonese"]) or lang in {"zh", "ja", "ko"} or has_cjk(target):
        if "japanese" in lang or lang == "ja" or re.search(r"[\u3040-\u30FF]", target):
            return "japanese"
        if "korean" in lang or lang == "ko" or re.search(r"[\uAC00-\uD7AF]", target):
            return "korean"
        return "cjk"

    if any(x in lang for x in ["russian", "ukrainian", "bulgarian", "serbian", "macedonian", "cyrillic"]) or lang in {"ru", "uk", "bg", "sr", "mk"} or CYRILLIC_RE.search(target):
        return "cyrillic"
    if "greek" in lang or lang == "el" or GREEK_RE.search(target):
        return "greek"

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
    if "turkish" in lang or lang.startswith("tr"):
        return "turkish"
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


def extract_skus(text: str) -> List[str]:
    return SKU_RE.findall(text or "")


def protected_terms_from_rules(rules: Dict[str, Any]) -> List[str]:
    protected: List[str] = []
    for item in (rules or {}).get("dnt", [])[:1000]:
        term = normalize_for_qa(item.get("term", ""))
        if term:
            protected.append(term)
    for item in (rules or {}).get("glossary", [])[:1000]:
        src = normalize_for_qa(item.get("source_term", ""))
        tgt = normalize_for_qa(item.get("target_term", ""))
        if src:
            protected.append(src)
        if tgt:
            protected.append(tgt)
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
    for d in (rules or {}).get("dnt", [])[:1000]:
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
    for g in (rules or {}).get("glossary", [])[:1000]:
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
    if infer_language_module(target_language, source, target) != "telugu":
        return []
    findings: List[QAFinding] = []
    # Telugu virama should normally be followed by Telugu consonant, ZWJ/ZWNJ, or combining behavior.
    # This is a conservative hint, not a grammar checker.
    if re.search(r"\u0C4D(?![\u0C15-\u0C39\u0C58-\u0C5A\u200C\u200D])", target):
        findings.append(QAFinding(
            "telugu.unicode.malformed_cluster_hint",
            "Unicode Hygiene",
            "Review",
            "Medium",
            "Telugu virama sequence",
            target,
            "Possible malformed Telugu combining sequence. Human review recommended.",
            rule_source="Built-in Telugu Unicode hygiene",
            priority=55,
        ))
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


def _parse_client_correction_lines(rules: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract client correction dictionary entries from Rules ZIP chunks.

    Supported high-precision formats inside txt/csv/docx/xlsx rule files:
    - wrong -> correct
    - wrong => correct
    - wrong | correct | error_type | severity
    - wrong,correct,error_type,severity
    - forbidden: X -> preferred: Y

    This lets companies upload their own spelling/grammar/style/terminology
    dictionaries and lets ErrorSweep work without API keys.
    """
    corrections: List[Dict[str, str]] = []

    # Also support explicit correction arrays if future parser adds them.
    for item in (rules or {}).get("corrections", [])[:5000]:
        wrong = normalize_for_qa(item.get("wrong", ""))
        correct = normalize_for_qa(item.get("correct", ""))
        if wrong and correct:
            corrections.append({
                "wrong": wrong,
                "correct": correct,
                "category": item.get("error_type", item.get("category", "Client Rule")),
                "severity": item.get("severity", "Major"),
                "source": item.get("source", "Client Rules"),
            })

    for chunk in (rules or {}).get("chunks", [])[:200]:
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

            corrections.append({
                "wrong": wrong,
                "correct": correct,
                "category": category or "Client Rule",
                "severity": severity if severity in {"Critical", "Major", "Minor", "Review"} else "Major",
                "source": source_name,
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
    return deduped[:5000]


def _apply_correction_to_text(text: str, wrong: str, correct: str) -> Tuple[str, int]:
    if not wrong:
        return text, 0

    # For Latin words, use word boundaries to avoid changing inside larger words.
    if re.fullmatch(r"[A-Za-z][A-Za-z'-]*", wrong):
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
    else:
        pattern = re.compile(re.escape(wrong))

    return pattern.subn(correct, text)


@registry.register("global.offline_dictionary.client_and_builtin", "Spelling")
def rule_offline_correction_dictionary(segment, rules, target_language, domain):
    source, target = _seg_texts(segment)
    if not target:
        return []

    module = infer_language_module(target_language, source, target)
    dictionary_entries = []
    dictionary_entries.extend(BUILTIN_CORRECTIONS.get("global", []))
    dictionary_entries.extend(BUILTIN_CORRECTIONS.get(module, []))
    dictionary_entries.extend(_parse_client_correction_lines(rules))

    findings: List[QAFinding] = []
    for entry in dictionary_entries[:6000]:
        wrong = normalize_for_qa(entry.get("wrong", ""))
        correct = normalize_for_qa(entry.get("correct", ""))
        if not wrong or not correct:
            continue
        new_text, count = _apply_correction_to_text(target, wrong, correct)
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
) -> List[Dict[str, Any]]:
    """Drop-in replacement for app.py deterministic_checks."""
    source, target = _seg_texts(segment)
    if not target:
        return []
    if target.lstrip().startswith("="):
        return []

    findings = registry.run(segment, rules or {}, target_language, domain)

    if not enable_zwnj:
        findings = [f for f in findings if not f.rule_id.startswith("telugu.zwnj")]

    findings = dedupe_and_score(findings)
    return [to_report_row(segment, f) for f in findings]