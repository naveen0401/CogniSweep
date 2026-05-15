
from __future__ import annotations

import re
from typing import Any, Dict, List


PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|<[^>]+>)")
URL_RE = re.compile(r"https?://[^\s\]\)<>\"']+")
EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}")
TAG_RE = re.compile(r"</?[^>\s]+(?:\s+[^>]*)?>")
NUMBER_RE = re.compile(r"\d+(?:[.,:]\d+)*")
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "\u200D"
    "]+",
    re.UNICODE,
)
BULLET_RE = re.compile(r"^\s*([•∙·\-\*]+|\d+[.)])\s*")

SCRIPT_RANGES = {
    "arabic": r"[\u0600-\u06FF]",
    "urdu": r"[\u0600-\u06FF]",
    "telugu": r"[\u0C00-\u0C7F]",
    "hindi": r"[\u0900-\u097F]",
    "marathi": r"[\u0900-\u097F]",
    "nepali": r"[\u0900-\u097F]",
    "tamil": r"[\u0B80-\u0BFF]",
    "malayalam": r"[\u0D00-\u0D7F]",
    "kannada": r"[\u0C80-\u0CFF]",
    "bengali": r"[\u0980-\u09FF]",
    "gujarati": r"[\u0A80-\u0AFF]",
    "odia": r"[\u0B00-\u0B7F]",
    "punjabi": r"[\u0A00-\u0A7F]",
    "greek": r"[\u0370-\u03FF]",
    "russian": r"[\u0400-\u04FF]",
    "ukrainian": r"[\u0400-\u04FF]",
    "japanese": r"[\u3040-\u30FF\u4E00-\u9FFF]",
    "chinese": r"[\u4E00-\u9FFF]",
    "korean": r"[\uAC00-\uD7AF]",
}


def normalize_text_for_qa(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00A0", " ")
    text = text.replace("\u200B", "")
    return text.strip()


def _find_all(pattern: re.Pattern, text: str) -> List[str]:
    return pattern.findall(text or "")


def _row(segment: Dict[str, Any], error_type: str, severity: str, wrong: str, suggestion: str, explanation: str, confidence: str = "High") -> Dict[str, Any]:
    return {
        "Sheet": segment.get("sheet", ""),
        "Location": segment.get("location", ""),
        "Mode": segment.get("mode", ""),
        "Source Text": segment.get("source", ""),
        "Translation": segment.get("translation", segment.get("text", "")),
        "Error Type": error_type,
        "Severity": severity,
        "Wrong Part": wrong,
        "Suggestion": suggestion,
        "Explanation": explanation,
        "Check Source": "Offline Rule Engine",
        "Rule Source": "Global deterministic QA",
        "Confidence": confidence,
    }


def target_script_ok(target: str, target_language: str) -> bool:
    lang = (target_language or "").strip().lower().replace("_", " ")
    if not lang or lang in {"auto", "auto-detect", "english", "en"}:
        return True
    for key, pat in SCRIPT_RANGES.items():
        if key in lang:
            return bool(re.search(pat, target or ""))
    return True


def looks_untranslated(source: str, target: str, target_language: str) -> bool:
    src = normalize_text_for_qa(source)
    tgt = normalize_text_for_qa(target)
    if not tgt:
        return True
    if src.lower() == tgt.lower() and target_language.lower() not in {"english", "en"}:
        return True
    # placeholder-only target
    remainder = PLACEHOLDER_RE.sub("", tgt)
    remainder = NUMBER_RE.sub("", remainder)
    remainder = EMOJI_RE.sub("", remainder)
    remainder = re.sub(r"[\s\[\]{}():;,.!?\"'`~\-–—_/\\|•∙·*]+", "", remainder)
    if remainder == "" and re.search(r"[A-Za-z]{3,}", src):
        return True
    if not target_script_ok(tgt, target_language):
        if target_language.lower() in {"telugu", "hindi", "tamil", "malayalam", "kannada", "arabic", "urdu", "bengali", "gujarati", "odia", "punjabi"}:
            return True
    return False


def deterministic_checks_v2(
    segment: Dict[str, Any],
    rules: Dict[str, Any] | None = None,
    target_language: str = "Auto-detect",
    domain: str = "General",
    enable_zwnj: bool = True,
    **_: Any,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    source = normalize_text_for_qa(segment.get("source", ""))
    target = normalize_text_for_qa(segment.get("translation", segment.get("text", "")))

    if not target:
        rows.append(_row(segment, "Translation Missing", "Major", "blank target", "Translate this segment.", "Target is blank while source has content."))
        return rows

    if looks_untranslated(source, target, target_language):
        rows.append(_row(segment, "Accuracy", "Major", target[:120], "Translate into the selected target language.", "Target appears blank, placeholder-only, source-copied, or wrong-language.", "High"))

    # Placeholder / tag / URL / email preservation
    checks = [
        ("Placeholder", PLACEHOLDER_RE, "Source placeholder/tag is missing or changed."),
        ("URL", URL_RE, "Source URL is missing or changed."),
        ("Email", EMAIL_RE, "Source email is missing or changed."),
        ("Tag", TAG_RE, "Source HTML/XML tag is missing or changed."),
    ]
    for label, pattern, explanation in checks:
        src_items = _find_all(pattern, source)
        tgt_items = _find_all(pattern, target)
        missing = [x for x in src_items if x not in tgt_items]
        if missing:
            rows.append(_row(segment, label, "Major", ", ".join(missing), target, explanation))

    # Numbers
    src_nums = _find_all(NUMBER_RE, source)
    tgt_nums = _find_all(NUMBER_RE, target)
    missing_nums = [n for n in src_nums if n not in tgt_nums]
    if missing_nums:
        rows.append(_row(segment, "Number", "Major", ", ".join(missing_nums), target, "Source number is missing or changed."))

    # Emoji and bullet preservation
    src_emojis = EMOJI_RE.findall(source)
    missing_emojis = [e for e in src_emojis if e not in target]
    if missing_emojis:
        rows.append(_row(segment, "Formatting", "Minor", "".join(missing_emojis), "".join(missing_emojis) + " " + target, "Source emoji/icon is missing from target.", "High"))

    src_bullet = BULLET_RE.match(source)
    if src_bullet and not target.startswith(src_bullet.group(1)):
        rows.append(_row(segment, "Formatting", "Minor", "missing bullet/list marker", src_bullet.group(1) + " " + target.lstrip(), "Source leading bullet/list marker should be preserved.", "High"))

    # Bracket structure: UI label inside brackets can localize, brackets should remain
    if source.strip().startswith("[") and source.strip().endswith("]"):
        if not (target.strip().startswith("[") and target.strip().endswith("]")):
            rows.append(_row(segment, "Formatting", "Minor", "missing square brackets", f"[{target.strip('[] ')}]", "Bracketed UI label can be localized, but bracket structure should remain.", "Medium"))

    # Extra spaces
    if re.search(r"[ \t]{2,}", target):
        rows.append(_row(segment, "Spacing", "Minor", target, re.sub(r"[ \t]{2,}", " ", target), "Repeated spaces found.", "High"))

    # DNT/glossary from rule packs
    rules = rules or {}
    for d in rules.get("dnt", [])[:500]:
        term = normalize_text_for_qa(d.get("term", ""))
        if term and term.lower() in source.lower() and term not in target:
            rows.append(_row(segment, "DNT", "Major", term, f"Keep '{term}' unchanged.", "DNT term from rule pack is missing or changed.", "High"))

    for g in rules.get("glossary", [])[:500]:
        src = normalize_text_for_qa(g.get("source_term", ""))
        tgt = normalize_text_for_qa(g.get("target_term", ""))
        if src and tgt and src.lower() in source.lower() and tgt not in target:
            rows.append(_row(segment, "Glossary", "Major", src, tgt, "Required glossary translation is missing.", "High"))

    # Dedupe
    seen = set()
    out = []
    for row in rows:
        key = (row["Location"], row["Error Type"], row["Wrong Part"], row["Suggestion"])
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


# Backward-compatible name used by older app.py versions
def deterministic_checks(segment: Dict[str, Any], rules: Dict[str, Any] | None = None, enable_zwnj: bool = True) -> List[Dict[str, Any]]:
    return deterministic_checks_v2(segment, rules or {}, target_language="Auto-detect", enable_zwnj=enable_zwnj)

