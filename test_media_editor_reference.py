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
    assert 'anchor.target = "_top"' in html
    assert '"back_url": app_page_link("Subtitle / Transcription Editor")' in app_source
    assert '<div class="logo"><img src="{escape(logo_data_uri, quote=True)}" alt="CogniSweep logo" /></div>' in app_source


if __name__ == "__main__":
    test_reference_media_editor_has_timing_quick_actions()
    test_reference_media_editor_updates_timing_metrics()
    test_reference_media_editor_uses_fixed_viewport_shell()
    test_reference_media_editor_has_real_logo_slot_and_route_back_button()
    print("Media editor reference checks passed.")
