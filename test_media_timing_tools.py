from media_timing_tools import adjust_media_segment_timing, media_timing_summary


def test_move_clamps_at_zero_and_preserves_duration():
    rows = [{"id": 1, "start": 1.0, "end": 3.5, "target": "Hello world"}]

    updated = adjust_media_segment_timing(rows, 0, "move", -4.0)

    assert updated[0]["start"] == 0.0
    assert updated[0]["end"] == 2.5


def test_trim_start_respects_minimum_duration():
    rows = [{"id": 1, "start": 4.0, "end": 5.0}]

    updated = adjust_media_segment_timing(rows, 0, "trim_start", 5.0)

    assert updated[0]["start"] == 4.9
    assert updated[0]["end"] == 5.0


def test_snap_actions_close_neighbor_gaps():
    rows = [
        {"id": 1, "start": 0.0, "end": 2.0},
        {"id": 2, "start": 2.5, "end": 4.5},
        {"id": 3, "start": 5.0, "end": 7.0},
    ]

    start_snapped = adjust_media_segment_timing(rows, 1, "snap_start_previous")
    end_snapped = adjust_media_segment_timing(rows, 1, "snap_end_next")

    assert start_snapped[1]["start"] == 2.0
    assert start_snapped[1]["end"] == 4.5
    assert end_snapped[1]["start"] == 2.5
    assert end_snapped[1]["end"] == 5.0


def test_summary_reports_gaps_and_reading_speed():
    rows = [
        {"id": 1, "start": 0.0, "end": 1.0},
        {"id": 2, "start": 1.5, "end": 3.5, "target": "1234567890"},
        {"id": 3, "start": 4.0, "end": 5.0},
    ]

    summary = media_timing_summary(rows, 1)

    assert summary["duration"] == 2.0
    assert summary["cps"] == 5
    assert summary["previous_gap"] == 0.5
    assert summary["next_gap"] == 0.5


if __name__ == "__main__":
    test_move_clamps_at_zero_and_preserves_duration()
    test_trim_start_respects_minimum_duration()
    test_snap_actions_close_neighbor_gaps()
    test_summary_reports_gaps_and_reading_speed()
    print("Media timing tool checks passed.")
