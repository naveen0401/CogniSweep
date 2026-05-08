
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
    lang = (target_language or "").strip().lower()
    if "telugu" in lang or "te-" in lang or lang in {"te", "tel"} or has_telugu(target):
        return "telugu"
    if any(x in lang for x in ["hindi", "marathi", "nepali", "devanagari"]) or has_devanagari(target):
        return "devanagari"
    if any(x in lang for x in ["arabic", "urdu", "persian", "farsi"]) or ARABIC_RE.search(target or ""):
        return "arabic"
    if "hebrew" in lang or HEBREW_RE.search(target or ""):
        return "hebrew"
    if any(x in lang for x in ["chinese", "japanese", "korean", "cjk"]) or has_cjk(target):
        return "cjk"
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
    if module not in {"telugu", "devanagari", "arabic", "hebrew", "cjk"}:
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