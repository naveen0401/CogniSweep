from pathlib import Path


REFERENCE_HTML = Path("assets/media_editor_reference.html")


def test_reference_media_editor_has_timing_quick_actions():
    html = REFERENCE_HTML.read_text(encoding="utf-8")

    assert 'id="timingStepInput"' in html
    assert 'id="timingMoveBackBtn"' in html
    assert 'id="timingSnapPrevBtn"' in html
    assert 'id="timingApplyDurationBtn"' in html
    assert "function activeTimingStats()" in html
    assert "function adjustActiveTiming(action, amount = 0)" in html
    assert "MIN_MEDIA_SEGMENT_DURATION" in html


def test_reference_media_editor_updates_timing_metrics():
    html = REFERENCE_HTML.read_text(encoding="utf-8")

    assert 'id="metricDuration"' in html
    assert 'id="metricPrevGap"' in html
    assert 'id="metricNextGap"' in html
    assert 'el("metricDuration").textContent' in html
    assert 'el("timingDurationInput")' in html


def test_reference_media_editor_uses_fixed_viewport_shell():
    html = REFERENCE_HTML.read_text(encoding="utf-8")

    assert "width: 100vw;" in html
    assert "max-width: 100vw;" in html
    assert "overscroll-behavior: none;" in html
    assert "grid-template-columns: minmax(0, 1fr) minmax(320px, 340px);" in html
    assert "width: 340px;" in html
    assert "max-width: 340px;" in html


def test_reference_media_editor_has_real_logo_slot_and_route_back_button():
    html = REFERENCE_HTML.read_text(encoding="utf-8")
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert ".logo img" in html
    assert 'id="backBtn"' in html
    assert "payload.back_url" in html
    assert 'anchor.target = "_self"' in html
    assert 'back_url = editor_back_link("Subtitle / Transcription Editor")' in app_source
    assert '"back_url": back_url' in app_source
    assert "render_editor_back_navigation_bridge(back_url)" in app_source
    assert 'window.parent.postMessage({ type: "errorsweep-editor-back", url: target }, "*")' in html
    assert '<div class="logo"><img src="{escape(logo_data_uri, quote=True)}" alt="CogniSweep logo" /></div>' in app_source


def test_reference_media_editor_has_mobile_working_layout():
    html = REFERENCE_HTML.read_text(encoding="utf-8")
    mobile_start = html.index("@media (max-width: 760px)")
    mobile_end = html.index("@media (max-width: 430px)", mobile_start)
    mobile_css = html[mobile_start:mobile_end]

    assert ".header-actions {" in mobile_css
    assert "overflow-x: auto;" in mobile_css
    assert ".editor-layout {" in mobile_css
    assert "grid-template-columns: minmax(0, 1fr);" in mobile_css
    assert ".left-column {" in mobile_css
    assert "grid-template-rows: minmax(240px, 42vh) auto minmax(0, 1fr) auto;" in mobile_css
    assert ".media-strip {" in mobile_css
    assert "grid-template-columns: 1fr;" in mobile_css
    assert ".table-wrap {" in mobile_css
    assert "-webkit-overflow-scrolling: touch;" in mobile_css
    assert "body.transcription-mode table" in mobile_css


if __name__ == "__main__":
    test_reference_media_editor_has_timing_quick_actions()
    test_reference_media_editor_updates_timing_metrics()
    test_reference_media_editor_uses_fixed_viewport_shell()
    test_reference_media_editor_has_real_logo_slot_and_route_back_button()
    test_reference_media_editor_has_mobile_working_layout()
    print("Media editor reference checks passed.")
