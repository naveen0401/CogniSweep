from pathlib import Path


APP = Path("app.py")
WORKFLOW = Path(".github/workflows/release-gate.yml")
RELEASE_CHECK = Path("deploy/release_check.py")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(text: str, name: str, next_name: str) -> str:
    start = text.index(f"def {name}")
    if next_name.startswith("def ") or next_name.startswith("#"):
        end = text.index(next_name, start)
    else:
        end = text.index(f"def {next_name}", start)
    return text[start:end]


def test_subtitle_creation_only_launches_external_media_editor():
    text = source(APP)
    setup = function_body(text, "render_subtitle_transcription_setup", "render_focused_subtitle_workspace")

    assert 'enter_subtitle_workspace("Subtitling"' not in setup
    assert 'enter_subtitle_workspace("Transcription"' not in setup
    assert 'save_media_session_to_store("Subtitling"' in setup
    assert 'save_media_session_to_store("Transcription"' in setup
    assert 'render_external_editor_link("Open Subtitle Editor", "media", job_id)' in setup
    assert 'render_external_editor_link("Open Transcription Editor", "media", job_id)' in setup
    assert "st.session_state.subtitle_segments = []" in setup
    assert "render_last_media_editor_link()" in setup


def test_subtitle_page_no_longer_auto_renders_legacy_workspace():
    text = source(APP)
    page = function_body(text, "page_subtitle_transcription_editor", "page_human_review")
    route = function_body(text, "render_subtitle_transcription_editor", "page_subtitle_transcription_editor")

    assert "render_focused_subtitle_workspace()" not in page
    assert "render_focused_subtitle_workspace()" not in route
    assert "st.session_state.subtitle_editor_active = False" in page
    assert "st.session_state.subtitle_editor_active = False" in route


def test_legacy_subtitle_workspace_routes_redirect_to_external_setup():
    text = source(APP)
    subtitle = function_body(text, "page_subtitle_workspace", "page_transcription_workspace")
    transcription = function_body(text, "page_transcription_workspace", "# ==========================================================")

    assert "render_focused_subtitle_workspace()" not in subtitle
    assert "render_focused_subtitle_workspace()" not in transcription
    assert "render_subtitle_transcription_setup()" in subtitle
    assert "render_subtitle_transcription_setup()" in transcription
    assert "in-page subtitle workspace has been retired" in subtitle
    assert "in-page transcription workspace has been retired" in transcription


def test_media_studio_setup_uses_compact_professional_shell():
    text = source(APP)
    setup = function_body(text, "render_subtitle_transcription_setup", "render_focused_subtitle_workspace")
    page = function_body(text, "page_subtitle_transcription_editor", "page_human_review")

    assert "Create a media workspace" in setup
    assert "Prepare a subtitle or transcript job" not in setup
    assert "Separate workspace" in setup
    assert "External workspace" not in setup
    assert 'st.container(key="media_workflow_card")' in setup
    assert 'st.container(key="media_source_card")' in setup
    assert 'st.container(key="media_compliance_panel")' in setup
    assert "Media intake" in setup
    assert "es-media-status-note" in setup
    assert ".st-key-media_workflow_card" in page
    assert ".st-key-media_source_card" in page
    assert ".st-key-media_compliance_panel" in page


def test_subtitle_external_editor_regression_is_in_release_gate():
    assert "python test_subtitle_external_editor_only.py" in source(WORKFLOW)
    assert "python test_subtitle_external_editor_only.py" in source(RELEASE_CHECK)


if __name__ == "__main__":
    test_subtitle_creation_only_launches_external_media_editor()
    test_subtitle_page_no_longer_auto_renders_legacy_workspace()
    test_legacy_subtitle_workspace_routes_redirect_to_external_setup()
    test_media_studio_setup_uses_compact_professional_shell()
    test_subtitle_external_editor_regression_is_in_release_gate()
    print("Subtitle external editor-only checks passed.")
