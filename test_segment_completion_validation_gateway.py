from pathlib import Path


ROOT = Path(__file__).parent
APP = ROOT / "app.py"
CAT_EDITOR = ROOT / "assets" / "cat_editor_reference.html"
MEDIA_EDITOR = ROOT / "assets" / "media_editor_reference.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_python_shared_completion_validation_gateway_contract() -> None:
    source = read(APP)

    assert 'COMPLETED_WITH_WARNINGS_STATUS = "Completed with warnings"' in source
    assert "def segment_completion_validation_findings(" in source
    assert "def render_completion_validation_popover(" in source
    assert "def row_completion_ignored_findings(" in source
    assert "def store_ignored_completion_findings(" in source
    assert "def set_segment_confirmed(" in source
    assert "ignored_findings: Optional[List[Dict[str, Any]]] = None" in source
    assert "delivery_quality_findings([candidate]" in source
    assert "Transcript text is blank." in source
    assert "Target subtitle text is blank." in source
    assert '"completed_with_warnings_count": len(completed_with_warnings)' in source
    assert '"ignored_completion_finding_count": len(ignored_completion_findings)' in source
    assert 'add_audit(\n            "Editor validation warnings ignored"' in source


def test_cat_editor_completion_uses_row_popover_and_explicit_ignore() -> None:
    html = read(CAT_EDITOR)

    assert 'id="validationPopover"' in html
    assert "function requestRowCompletion(idx, options = {})" in html
    assert "function validationFindingsForRow(row, idx)" in html
    assert "function storeIgnoredValidationFindings(row, findings)" in html
    assert "function markRowComplete(idx, options = {})" in html
    assert "Return to segment" in html
    assert "Ignore and mark complete" in html
    assert "Completion cancelled" in html
    assert "requestRowCompletion(i, { anchor: tr })" in html
    assert "showValidationPopover(idx, findings, options)" in html
    assert "COMPLETED_WITH_WARNINGS_STATUS" in html
    assert "completed-warning-row" in html
    assert "Ignored completion warning:" in html
    assert "row.qa =" not in html
    assert "if (!row || isCompletedWithWarnings(row)) return [];" not in html
    assert "DNT term changed or missing" in html
    assert "Glossary target missing" in html
    assert "No glossary, DNT, or TM resources match the selected segment." in html
    assert "function segmentResourceList(name, row)" in html
    assert "renderLanguageResources();" in html
    assert "rows.forEach(row => { if (row.target.trim())" not in html


def test_media_editor_completion_uses_gateway_for_subtitling_and_transcription() -> None:
    html = read(MEDIA_EDITOR)

    assert 'id="validationPopover"' in html
    assert 'const COMPLETED_WITH_WARNINGS_STATUS = "Completed with warnings";' in html
    assert "function requestRowCompletion(idx, options = {})" in html
    assert "function validationFindingsForRow(row, idx)" in html
    assert "function storeIgnoredValidationFindings(row, findings)" in html
    assert "function markRowComplete(idx, options = {})" in html
    assert "Return to segment" in html
    assert "Ignore and mark complete" in html
    assert "Completion cancelled" in html
    assert 'requestedStatus === "Approved" || requestedStatus === COMPLETED_WITH_WARNINGS_STATUS' in html
    assert "function setAllSegmentsConfirmed(checked)" in html
    assert "showValidationPopover(idx, findings, options)" in html
    assert "isTranscriptionMode() ? \"Transcript text is blank.\"" in html
    assert "if (!isTranscriptionMode() && end > start)" in html
    assert "completed-warning-row" in html
    assert "Ignored completion warning:" in html
    assert "row_count: rows.length,\n            rows," in html
    assert "if (!row || isCompletedWithWarnings(row)) return [];" not in html
    assert "const text = safe(row.target);" in html
    assert "DNT term changed or missing" in html
    assert "Glossary target missing" in html
    assert 'id="dntMatches"' in html


def test_header_done_is_smart_bulk_not_select_all() -> None:
    source = read(APP)
    cat_html = read(CAT_EDITOR)
    media_html = read(MEDIA_EDITOR)

    assert "def apply_validated_completion_flags(" in source
    assert "blocked += 1" in source
    assert "Smart Done left {blocked_completion_count} segment(s) unmarked" in source

    for html in (cat_html, media_html):
        assert "let completed = 0;" in html
        assert "let blocked = 0;" in html
        assert "blocked += 1;" in html
        assert "continue;" in html
        assert "markRowComplete(idx);" in html
        assert "Smart Done marked ${completed} clean segment" in html
        assert "left unmarked for review" in html
        assert "requestAnimationFrame(() => showValidationPopover" not in html
        assert "if (findings.length)" in html
    assert "if (rows[idx].done) continue;" not in cat_html
    assert "if (rows[idx].confirmed || isCompletedWithWarnings(rows[idx])) continue;" not in media_html


def test_streamlit_fallback_completion_paths_are_guarded() -> None:
    source = read(APP)

    assert "def request_focused_completion(action_prefix: str, success_message: str) -> bool:" in source
    assert "def save_focused_row(action_prefix: str, advance: bool = False) -> None:" in source
    assert "completion_requested = status in {\"Approved\", COMPLETED_WITH_WARNINGS_STATUS}" in source
    assert "segment_completion_validation_findings(\n                rows[idx]," in source
    assert "render_completion_validation_popover(rows[idx], pending_findings, action_prefix" in source
    assert "blocked_media_completion = apply_validated_completion_flags(" in source
    assert "blocked_completion_count = apply_validated_completion_flags(" in source
    assert "if is_segment_confirmed(row) and is_completed_with_warnings(row):" not in source
    assert 'requested_complete = bool(row.get("confirmed") or row.get("done"))' in source
    assert 'text_value = candidate["target"]' in source


if __name__ == "__main__":
    test_python_shared_completion_validation_gateway_contract()
    test_cat_editor_completion_uses_row_popover_and_explicit_ignore()
    test_media_editor_completion_uses_gateway_for_subtitling_and_transcription()
    test_header_done_is_smart_bulk_not_select_all()
    test_streamlit_fallback_completion_paths_are_guarded()
    print("Segment completion validation gateway checks passed.")
