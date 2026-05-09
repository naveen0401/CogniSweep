"""
ErrorSweep Quality Gate QA Engine
---------------------------------
Global, conservative no-API QA layer for ErrorSweep.

This module is designed to reduce false positives:
- Confirmed Error = high-evidence deterministic/client-rule issue
- Needs Review = lower-confidence grammar/style/fluency warning
- Never turns vague preference into an error

It does not replace AI or human review for deep semantic accuracy.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

try:
    import language_tool_python
except Exception:  # package may be missing in local/dev
    language_tool_python = None

NBSP = "\u00a0"
ZWSP = "\u200b"
ZWNJ = "\u200c"
ZWJ = "\u200d"

PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|\b\w+_id\b|<[^>]+>)")
NUMBER_RE = re.compile(r"\d+(?:[.,:/-]\d+)*")
URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
TAG_RE = re.compile(r"<[^>]+>")
SKU_RE = re.compile(r"\b[A-Z]{2,}[-_][A-Z0-9][A-Z0-9_-]*\b|\b[A-Z0-9]{4,}-[A-Z0-9-]{2,}\b")
LATIN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9._-]*\b")

SCRIPT_PATTERNS = {
    "telugu": re.compile(r"[\u0C00-\u0C7F]"),
    "devanagari": re.compile(r"[\u0900-\u097F]"),
    "bengali": re.compile(r"[\u0980-\u09FF]"),
    "gurmukhi": re.compile(r"[\u0A00-\u0A7F]"),
    "gujarati": re.compile(r"[\u0A80-\u0AFF]"),
    "odia": re.compile(r"[\u0B00-\u0B7F]"),
    "tamil": re.compile(r"[\u0B80-\u0BFF]"),
    "kannada": re.compile(r"[\u0C80-\u0CFF]"),
    "malayalam": re.compile(r"[\u0D00-\u0D7F]"),
    "sinhala": re.compile(r"[\u0D80-\u0DFF]"),
    "arabic": re.compile(r"[\u0600-\u06FF]"),
    "hebrew": re.compile(r"[\u0590-\u05FF]"),
    "thai": re.compile(r"[\u0E00-\u0E7F]"),
    "lao": re.compile(r"[\u0E80-\u0EFF]"),
    "khmer": re.compile(r"[\u1780-\u17FF]"),
    "myanmar": re.compile(r"[\u1000-\u109F]"),
    "cjk": re.compile(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]"),
    "cyrillic": re.compile(r"[\u0400-\u04FF]"),
    "greek": re.compile(r"[\u0370-\u03FF]"),
}

LANGUAGE_MODULE_ALIASES = {
    "telugu": "telugu", "te": "telugu",
    "hindi": "devanagari", "marathi": "devanagari", "nepali": "devanagari", "sanskrit": "devanagari", "hi": "devanagari", "mr": "devanagari",
    "bengali": "bengali", "bangla": "bengali", "assamese": "bengali", "bn": "bengali",
    "punjabi": "gurmukhi", "gurmukhi": "gurmukhi", "pa": "gurmukhi",
    "gujarati": "gujarati", "gu": "gujarati",
    "odia": "odia", "oriya": "odia", "or": "odia",
    "tamil": "tamil", "ta": "tamil",
    "kannada": "kannada", "kn": "kannada",
    "malayalam": "malayalam", "ml": "malayalam",
    "sinhala": "sinhala", "si": "sinhala",
    "arabic": "arabic", "urdu": "arabic", "persian": "arabic", "farsi": "arabic", "ar": "arabic", "ur": "arabic", "fa": "arabic",
    "hebrew": "hebrew", "he": "hebrew",
    "thai": "thai", "th": "thai",
    "lao": "lao", "lo": "lao",
    "khmer": "khmer", "km": "khmer",
    "myanmar": "myanmar", "burmese": "myanmar", "my": "myanmar",
    "chinese": "cjk", "japanese": "cjk", "korean": "cjk", "zh": "cjk", "ja": "cjk", "ko": "cjk",
    "russian": "cyrillic", "ukrainian": "cyrillic", "bulgarian": "cyrillic", "serbian": "cyrillic", "ru": "cyrillic", "uk": "cyrillic",
    "greek": "greek", "el": "greek",
}

LANGUAGETOOL_CODES = {
    "english": "en-US", "en": "en-US", "en-us": "en-US", "en-gb": "en-GB",
    "french": "fr", "fr": "fr",
    "spanish": "es", "es": "es",
    "german": "de-DE", "de": "de-DE",
    "italian": "it", "it": "it",
    "portuguese": "pt-PT", "pt": "pt-PT", "pt-br": "pt-BR",
    "dutch": "nl", "nl": "nl",
    "polish": "pl-PL", "pl": "pl-PL",
    "turkish": "tr", "tr": "tr",
    "russian": "ru-RU", "ru": "ru-RU",
    "ukrainian": "uk-UA", "uk": "uk-UA",
    "greek": "el", "el": "el",
    "arabic": "ar", "ar": "ar",
    "catalan": "ca-ES", "ca": "ca-ES",
    "romanian": "ro-RO", "ro": "ro-RO",
    "slovak": "sk-SK", "sk": "sk-SK",
    "slovenian": "sl-SI", "sl": "sl-SI",
    "swedish": "sv", "sv": "sv",
    "danish": "da-DK", "da": "da-DK",
}

BUILTIN_CORRECTIONS = [
    ("teh", "the", "Spelling", "Minor"),
    ("recieve", "receive", "Spelling", "Minor"),
    ("recieved", "received", "Spelling", "Minor"),
    ("seperate", "separate", "Spelling", "Minor"),
    ("definately", "definitely", "Spelling", "Minor"),
    ("occured", "occurred", "Spelling", "Minor"),
    ("sucess", "success", "Spelling", "Minor"),
    ("sucessfully", "successfully", "Spelling", "Minor"),
    ("adress", "address", "Spelling", "Minor"),
    ("wierd", "weird", "Spelling", "Minor"),
    ("calender", "calendar", "Spelling", "Minor"),
    ("untill", "until", "Spelling", "Minor"),
    ("I has", "I have", "Grammar", "Minor"),
    ("This are", "This is", "Grammar", "Minor"),
    ("These is", "These are", "Grammar", "Minor"),
    ("You was", "You were", "Grammar", "Minor"),
]

TELUGU_CORRECTIONS = [
    ("పాస్వర్డ్", "పాస్‌వర్డ్", "Spelling", "Minor"),
    ("పాస్ వర్డ్", "పాస్‌వర్డ్", "Spelling", "Minor"),
    ("డౌన్లోడ్", "డౌన్‌లోడ్", "Spelling", "Minor"),
    ("డౌన్ లోడ్", "డౌన్‌లోడ్", "Spelling", "Minor"),
    ("అప్లోడ్", "అప్‌లోడ్", "Spelling", "Minor"),
    ("అప్ లోడ్", "అప్‌లోడ్", "Spelling", "Minor"),
    ("డాష్బోర్డ్", "డాష్‌బోర్డ్", "Spelling", "Minor"),
    ("డాష్ బోర్డ్", "డాష్‌బోర్డ్", "Spelling", "Minor"),
]


def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFC", str(text))
    text = text.replace(NBSP, " ").replace(ZWSP, "")
    return text.strip("\r\n")


def compact(text: Any) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).strip()


def is_auto_language(target_language: str) -> bool:
    return (target_language or "").strip().lower() in {"", "auto", "auto-detect", "autodetect"}


def infer_module(target_language: str, source: str, target: str) -> str:
    lang = (target_language or "").strip().lower()
    for key, module in LANGUAGE_MODULE_ALIASES.items():
        if lang == key or key in lang:
            return module
    for module, pattern in SCRIPT_PATTERNS.items():
        if pattern.search(target or ""):
            return module
    return "global"


def extract_placeholders(text: str) -> List[str]: return PLACEHOLDER_RE.findall(text or "")
def extract_numbers(text: str) -> List[str]: return NUMBER_RE.findall(text or "")
def extract_urls(text: str) -> List[str]: return URL_RE.findall(text or "")
def extract_emails(text: str) -> List[str]: return EMAIL_RE.findall(text or "")
def extract_tags(text: str) -> List[str]: return TAG_RE.findall(text or "")
def extract_skus(text: str) -> List[str]: return SKU_RE.findall(text or "")


def make_row(segment: Dict[str, Any], error_type: str, severity: str, wrong: str, suggestion: str,
             explanation: str, check_source: str, rule_source: str, confidence: str,
             qa_status: str, evidence: str, action: str, autofix: str = "No", rule_id: str = "") -> Dict[str, Any]:
    return {
        "Sheet": segment.get("sheet", ""),
        "Location": segment.get("location", ""),
        "Mode": segment.get("mode", ""),
        "Source Text": normalize_text(segment.get("source", ""))[:500],
        "Translation": normalize_text(segment.get("translation", segment.get("text", "")))[:500],
        "Error Type": error_type,
        "Severity": severity,
        "Wrong Part": str(wrong)[:300],
        "Suggestion": str(suggestion)[:500],
        "Explanation": explanation,
        "Check Source": check_source,
        "Rule Source": rule_source,
        "Confidence": confidence,
        "QA Status": qa_status,
        "Evidence Level": evidence,
        "Action Required": action,
        "Autofix Possible": autofix,
        "Rule ID": rule_id,
    }


def protected_terms(rules: Dict[str, Any], target: str) -> set:
    items = set()
    for d in (rules or {}).get("dnt", [])[:1000]:
        term = normalize_text(d.get("term", ""))
        if term: items.add(term)
    for g in (rules or {}).get("glossary", [])[:1000]:
        for k in ("source_term", "target_term"):
            term = normalize_text(g.get(k, ""))
            if term: items.add(term)
    items.update(extract_placeholders(target))
    items.update(extract_urls(target))
    items.update(extract_emails(target))
    items.update(extract_tags(target))
    items.update(extract_skus(target))
    return items


def client_corrections_from_rules(rules: Dict[str, Any]) -> List[Tuple[str, str, str, str, str]]:
    out: List[Tuple[str, str, str, str, str]] = []
    for item in (rules or {}).get("corrections", [])[:5000]:
        wrong, correct = normalize_text(item.get("wrong", "")), normalize_text(item.get("correct", ""))
        if wrong and correct:
            out.append((wrong, correct, item.get("error_type", "Client Rule"), item.get("severity", "Major"), item.get("source", "Client Rules")))
    for chunk in (rules or {}).get("chunks", [])[:300]:
        src_name = chunk.get("source", "Client Rules")
        for line in str(chunk.get("text", "")).splitlines():
            line = normalize_text(line)
            if not line or len(line) > 500:
                continue
            wrong = correct = ""
            category, severity = "Client Rule", "Major"
            if "->" in line or "=>" in line:
                sep = "->" if "->" in line else "=>"
                left, right = [p.strip() for p in line.split(sep, 1)]
                wrong = re.sub(r"^(wrong|bad|forbidden|avoid|source)\s*[:=]\s*", "", left, flags=re.I).strip()
                correct = re.sub(r"^(correct|preferred|use|target|suggestion)\s*[:=]\s*", "", right, flags=re.I).strip()
            elif "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    wrong, correct = parts[0], parts[1]
                    if len(parts) >= 3 and parts[2]: category = parts[2]
                    if len(parts) >= 4 and parts[3]: severity = parts[3]
            elif "," in line:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2 and all(len(x) < 120 for x in parts[:2]):
                    wrong, correct = parts[0], parts[1]
                    if len(parts) >= 3 and parts[2]: category = parts[2]
                    if len(parts) >= 4 and parts[3]: severity = parts[3]
            wrong, correct = wrong.strip().strip('"“”'), correct.strip().strip('"“”')
            if wrong and correct and wrong.lower() not in {"wrong", "source", "bad"} and correct.lower() not in {"correct", "target"}:
                out.append((wrong, correct, category, severity, src_name))
    # dedupe
    seen, result = set(), []
    for x in out:
        key = x[:2]
        if key not in seen:
            seen.add(key); result.append(x)
    return result[:5000]


def apply_phrase(text: str, wrong: str, correct: str) -> Tuple[str, int]:
    flags = re.IGNORECASE if re.fullmatch(r"[A-Za-z][A-Za-z' -]*", wrong) else 0
    pattern = re.compile(rf"\b{re.escape(wrong)}\b", flags) if flags else re.compile(re.escape(wrong))
    return pattern.subn(correct, text)


@lru_cache(maxsize=32)
def get_languagetool(code: str, mode: str):
    if language_tool_python is None:
        return None
    try:
        if mode == "local":
            return language_tool_python.LanguageTool(code)
        return language_tool_python.LanguageToolPublicAPI(code)
    except Exception:
        return None


def language_tool_code(target_language: str, target: str) -> Optional[str]:
    lang = (target_language or "").strip().lower()
    if lang in LANGUAGETOOL_CODES:
        return LANGUAGETOOL_CODES[lang]
    short = re.split(r"[-_ ]", lang)[0]
    if short in LANGUAGETOOL_CODES:
        return LANGUAGETOOL_CODES[short]
    if is_auto_language(target_language) and re.search(r"[A-Za-z]", target):
        return "en-US"
    return None


def classify_lt(match: Any) -> Tuple[str, str, str]:
    category = str(getattr(match, "category", "") or "").lower()
    issue = str(getattr(match, "ruleIssueType", "") or "").lower()
    rule_id = str(getattr(match, "ruleId", "") or "")
    rid_low = rule_id.lower()
    if "morfologik" in rid_low or "typ" in category or "misspell" in issue or "spelling" in issue:
        return "Spelling", "Minor", rule_id
    if "style" in category or "style" in issue:
        return "Style", "Review", rule_id
    if "punct" in category or "typography" in category:
        return "Punctuation", "Minor", rule_id
    return "Grammar", "Review", rule_id


def quality_gate_checks(segment: Dict[str, Any], rules: Dict[str, Any], target_language: str = "Auto-detect",
                        domain: str = "Auto-detect", enable_zwnj: bool = True,
                        enable_language_tool: bool = False, language_tool_mode: str = "public",
                        language_tool_max_chars: int = 1200) -> List[Dict[str, Any]]:
    source = normalize_text(segment.get("source", ""))
    target = normalize_text(segment.get("translation", "") or segment.get("text", ""))
    rows: List[Dict[str, Any]] = []

    if not target or target.lstrip().startswith("="):
        return rows

    # Confirmed deterministic checks
    if re.search(r"[ \t]{2,}", target):
        suggestion = re.sub(r"[ \t]{2,}", " ", target)
        rows.append(make_row(segment, "Spacing", "Minor", target, suggestion, "Multiple consecutive spaces found.", "Rule Engine", "Global Formatting", "High", "Confirmed Error", "Deterministic", "Fix spacing", "Yes", "spacing.extra"))

    if target != target.strip():
        rows.append(make_row(segment, "Spacing", "Minor", target, target.strip(), "Leading or trailing spaces found.", "Rule Engine", "Global Formatting", "High", "Confirmed Error", "Deterministic", "Trim spaces", "Yes", "spacing.trim"))

    # Source-driven ending punctuation only if source has it.
    equivalents = {".": {".", "。", "．", "।", "॥"}, "!": {"!", "！"}, "?": {"?", "？"}, ";": {";", "；"}, ":": {":", "："}}
    if source.strip() and target.strip():
        src_end, tgt_end = source.strip()[-1], target.strip()[-1]
        if src_end in equivalents and tgt_end not in equivalents[src_end]:
            rows.append(make_row(segment, "Punctuation", "Minor", "missing ending punctuation", target.strip() + src_end, f"Source ends with '{src_end}', so target should preserve equivalent ending punctuation.", "Rule Engine", "Source-driven punctuation", "High", "Confirmed Error", "Source comparison", "Add equivalent punctuation", "Yes", "punct.source_end"))

    # Placeholders, numbers, URLs, emails, tags, SKUs
    for label, extractor in [("Placeholder", extract_placeholders), ("Number", extract_numbers), ("URL", extract_urls), ("Email", extract_emails), ("Tag", extract_tags), ("SKU", extract_skus)]:
        src_items, tgt_items = extractor(source), extractor(target)
        missing = [x for x in src_items if x not in tgt_items]
        if source and missing:
            rows.append(make_row(segment, label if label not in {"URL","Email","Tag","SKU"} else "Formatting", "Major", ", ".join(missing), target, f"{label} from source is missing or changed in target.", "Rule Engine", "Protected content", "High", "Confirmed Error", "Source comparison", f"Restore missing {label.lower()}", "No", f"protected.{label.lower()}"))

    # Bracket balance
    for left, right in [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">")]:
        if target.count(left) != target.count(right):
            rows.append(make_row(segment, "Formatting", "Minor", f"Unbalanced {left}{right}", target, "Unbalanced brackets detected.", "Rule Engine", "Global Formatting", "High", "Confirmed Error", "Deterministic", "Review/fix brackets", "No", "format.bracket_balance"))
            break

    # DNT and glossary confirmed issues
    for d in (rules or {}).get("dnt", [])[:1000]:
        term = normalize_text(d.get("term", ""))
        if term and term.lower() in source.lower() and term not in target:
            rows.append(make_row(segment, "DNT", "Major", term, f"Keep '{term}' unchanged.", "Do-not-translate term from client rules is missing or changed.", "Company Rules", d.get("source", "DNT"), "High", "Confirmed Error", "Client rule", "Restore DNT term", "No", "client.dnt"))

    for g in (rules or {}).get("glossary", [])[:1000]:
        src_term, tgt_term = normalize_text(g.get("source_term", "")), normalize_text(g.get("target_term", ""))
        if src_term and tgt_term and src_term.lower() in source.lower() and tgt_term not in target:
            rows.append(make_row(segment, "Terminology", "Major", src_term, tgt_term, "Required glossary term is missing in target.", "Company Rules", g.get("source", "Glossary"), "High", "Confirmed Error", "Client glossary", "Use required glossary term", "No", "client.glossary"))

    # Client dictionaries and built-in correction dictionaries
    corrections = BUILTIN_CORRECTIONS[:]
    if infer_module(target_language, source, target) == "telugu":
        corrections.extend(TELUGU_CORRECTIONS)
    corrections.extend(client_corrections_from_rules(rules))

    for wrong, correct, category, severity, *rest in corrections:
        rule_source = rest[0] if rest else "Offline Dictionary"
        new_text, count = apply_phrase(target, wrong, correct)
        if count > 0:
            cat = category or "Spelling"
            status = "Confirmed Error" if rule_source != "Offline Dictionary" or cat in {"Spelling", "Grammar"} else "Needs Review"
            rows.append(make_row(segment, cat, severity if severity in {"Critical", "Major", "Minor", "Review"} else "Major", wrong, new_text, "Matched offline correction dictionary or uploaded client QA-history rule.", "Rule Engine", rule_source, "High", status, "Dictionary/client rule", "Apply suggested correction", "Yes", "offline.dictionary"))

    # Target-language/script checks. Critical for catching English left in target.
    module = infer_module(target_language, source, target)
    expected = SCRIPT_PATTERNS.get(module)
    protected = protected_terms(rules, target)
    if expected and not is_auto_language(target_language):
        if not expected.search(target) and re.search(r"[A-Za-z]", target):
            rows.append(make_row(segment, "Mixed Script", "Major", target, "Translate target into selected language or add terms to DNT/glossary if allowed.", f"Target language is '{target_language}', but target does not contain expected script.", "Rule Engine", "Language profile", "High", "Confirmed Error", "Target-language selection", "Translate or mark as DNT", "No", "language.expected_script_missing"))
        elif expected.search(target) and re.search(r"[A-Za-z]", target):
            leftovers = []
            for word in LATIN_WORD_RE.findall(target):
                if word in protected or any(word in p for p in protected) or (word.isupper() and len(word) <= 6):
                    continue
                leftovers.append(word)
            if leftovers:
                rows.append(make_row(segment, "Mixed Script", "Major", ", ".join(sorted(set(leftovers))[:15]), target, "Unapproved English/Latin words found inside selected target language.", "Rule Engine", "Language profile", "High", "Confirmed Error", "Target-language selection", "Translate leftover words or add allowed terms to DNT/glossary", "No", "language.latin_leftover"))

    # Source copied to target
    if source and len(source) > 5 and compact(source).lower() == compact(target).lower() and re.search(r"[A-Za-z]", source):
        rows.append(make_row(segment, "Accuracy", "Major", target, "Translate this segment or confirm it is intentionally DNT.", "Target appears copied from source.", "Rule Engine", "Source comparison", "High", "Confirmed Error", "Source/target comparison", "Translate or mark DNT", "No", "accuracy.source_copied"))

    # Omission/readability hints (not confirmed errors)
    if source and target:
        src_len, tgt_len = len(re.sub(r"\s+", "", source)), len(re.sub(r"\s+", "", target))
        if src_len >= 60 and tgt_len <= max(8, int(src_len * 0.12)):
            rows.append(make_row(segment, "Accuracy", "Review", target, target, "Target is much shorter than source. Possible omission.", "Rule Engine", "Length heuristic", "Medium", "Needs Review", "Heuristic", "Human review", "No", "accuracy.too_short"))

    # Repeated word readability
    words = re.findall(r"\b[\wÀ-ỹ\u0900-\u097F\u0C00-\u0C7F]+\b", target.lower())
    repeated = [a for a, b in zip(words, words[1:]) if a == b and len(a) > 2]
    if repeated:
        rows.append(make_row(segment, "Readability", "Minor", " ".join(repeated[:5]), target, "Repeated adjacent word found.", "Rule Engine", "Readability heuristic", "High", "Confirmed Error", "Deterministic", "Remove repeated word", "No", "readability.repetition"))

    # Optional LanguageTool spelling/grammar/style layer = Needs Review by default.
    if enable_language_tool and target and len(target) <= int(language_tool_max_chars or 1200):
        code = language_tool_code(target_language, target)
        tool = get_languagetool(code, language_tool_mode) if code else None
        if tool:
            try:
                matches = tool.check(target)
            except Exception:
                matches = []
            for m in matches[:12]:
                start = int(getattr(m, "offset", 0) or 0)
                length = int(getattr(m, "errorLength", 0) or 0)
                if length <= 0:
                    continue
                wrong = target[start:start + length]
                if not wrong.strip() or wrong in protected:
                    continue
                repls = list(getattr(m, "replacements", []) or [])
                repl = repls[0] if repls else ""
                suggestion = target[:start] + repl + target[start+length:] if repl else target
                cat, sev, rid = classify_lt(m)
                message = str(getattr(m, "message", "Grammar/spelling/style issue."))
                rows.append(make_row(segment, cat, sev, wrong, suggestion, message, "No-API Grammar Engine", f"LanguageTool {code}", "Medium", "Needs Review", "Grammar engine", "Review suggestion", "Yes" if repl else "No", f"languagetool.{rid}"))

    # Sort: confirmed high confidence first, then review.
    order = {"Confirmed Error": 0, "Needs Review": 1}
    sev_order = {"Critical": 0, "Major": 1, "Minor": 2, "Review": 3}
    rows.sort(key=lambda r: (order.get(r.get("QA Status", "Needs Review"), 1), sev_order.get(r.get("Severity", "Review"), 3), r.get("Rule ID", "")))
    return rows