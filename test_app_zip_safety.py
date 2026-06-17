from pathlib import Path


APP = Path("app.py")
WORKFLOW = Path(".github/workflows/release-gate.yml")
RELEASE_CHECK = Path("deploy/release_check.py")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_source(text: str, name: str) -> str:
    marker = f"def {name}("
    start = text.index(marker)
    next_def = text.find("\ndef ", start + len(marker))
    next_class = text.find("\nclass ", start + len(marker))
    candidates = [idx for idx in (next_def, next_class) if idx != -1]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


def test_app_zip_safety_helpers_are_present():
    app = source(APP)
    for token in [
        "RULE_ZIP_MAX_EXPANDED_BYTES",
        "RULE_ZIP_MEMBER_MAX_BYTES",
        "OFFICE_ZIP_MAX_FILES",
        "OFFICE_ZIP_MAX_EXPANDED_BYTES",
        "OFFICE_XML_MEMBER_MAX_BYTES",
        "class ZipSafetyError(ValueError)",
        "def read_uploaded_file_limited",
        "def _safe_zip_members",
        "def _safe_zip_read",
        "def _validate_office_zip_archive",
    ]:
        assert token in app


def test_rules_zip_parser_uses_limited_upload_and_member_reads():
    app = source(APP)
    inspect_source = function_source(app, "inspect_rules_zip")
    parse_source = function_source(app, "parse_rules_zip")

    assert "uploaded_file.getvalue()" not in inspect_source
    assert "uploaded_file.getvalue()" not in parse_source
    assert "zf.read(" not in parse_source
    assert "read_uploaded_file_limited(uploaded_file, RULE_ZIP_MAX_BYTES" in inspect_source
    assert "read_uploaded_file_limited(uploaded_file, RULE_ZIP_MAX_BYTES" in parse_source
    assert "_safe_zip_members(" in inspect_source
    assert "_safe_zip_members(" in parse_source
    assert "_safe_zip_read(zf, info, RULE_ZIP_MEMBER_MAX_BYTES" in parse_source
    assert "if not report.get(\"ok\", False):" in parse_source
    assert "except ZipSafetyError" in inspect_source
    assert "except ZipSafetyError" in parse_source


def test_office_zip_parsers_use_safe_member_reads():
    app = source(APP)
    for name in [
        "_docx_table_rows",
        "_docx_body_paragraph_export_rows",
        "_pptx_text_items",
        "pptx_export_rows",
    ]:
        body = function_source(app, name)
        assert "archive.read(" not in body
        assert "_validate_office_zip_archive(archive)" in body
        assert "_safe_zip_read(" in body


def test_zip_safety_runs_in_release_gate():
    workflow = source(WORKFLOW)
    release_check = source(RELEASE_CHECK)
    assert "python test_app_zip_safety.py" in workflow
    assert "python test_app_zip_safety.py" in release_check


if __name__ == "__main__":
    test_app_zip_safety_helpers_are_present()
    test_rules_zip_parser_uses_limited_upload_and_member_reads()
    test_office_zip_parsers_use_safe_member_reads()
    test_zip_safety_runs_in_release_gate()
    print("App ZIP safety checks passed.")
