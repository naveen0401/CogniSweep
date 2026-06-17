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


if __name__ == "__main__":
    test_reference_media_editor_has_timing_quick_actions()
    test_reference_media_editor_updates_timing_metrics()
    test_reference_media_editor_uses_fixed_viewport_shell()
    print("Media editor reference checks passed.")
