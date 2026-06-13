import math
from typing import Any, Dict, List, Optional


MIN_MEDIA_SEGMENT_DURATION = 0.1


def as_seconds(value: Any, fallback: float = 0.0) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    if math.isnan(seconds) or math.isinf(seconds):
        return float(fallback)
    return seconds


def media_timing_summary(rows: List[Dict[str, Any]], index: int, min_duration: float = MIN_MEDIA_SEGMENT_DURATION) -> Dict[str, Any]:
    if not rows or index < 0 or index >= len(rows):
        return {
            "start": 0.0,
            "end": min_duration,
            "duration": min_duration,
            "cps": 0,
            "previous_gap": None,
            "next_gap": None,
        }

    row = rows[index]
    start = max(0.0, as_seconds(row.get("start"), 0.0))
    end = as_seconds(row.get("end"), start + min_duration)
    if end <= start:
        end = start + min_duration
    duration = max(min_duration, end - start)
    text = str(row.get("target") or row.get("source") or "")
    cps = round(len(text) / duration) if text else 0

    previous_gap: Optional[float] = None
    if index > 0:
        previous_end = as_seconds(rows[index - 1].get("end"), start)
        previous_gap = round(start - previous_end, 3)

    next_gap: Optional[float] = None
    if index + 1 < len(rows):
        next_start = as_seconds(rows[index + 1].get("start"), end)
        next_gap = round(next_start - end, 3)

    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(duration, 3),
        "cps": cps,
        "previous_gap": previous_gap,
        "next_gap": next_gap,
    }


def adjust_media_segment_timing(
    rows: List[Dict[str, Any]],
    index: int,
    action: str,
    amount: float = 0.0,
    min_duration: float = MIN_MEDIA_SEGMENT_DURATION,
) -> List[Dict[str, Any]]:
    new_rows = [dict(row) for row in rows or []]
    if not new_rows or index < 0 or index >= len(new_rows):
        return new_rows

    row = new_rows[index]
    start = max(0.0, as_seconds(row.get("start"), 0.0))
    end = as_seconds(row.get("end"), start + min_duration)
    if end <= start:
        end = start + min_duration

    action = (action or "").strip().lower()
    amount = as_seconds(amount, 0.0)

    if action == "move":
        next_start = max(0.0, start + amount)
        actual_delta = next_start - start
        start = next_start
        end = end + actual_delta
    elif action == "trim_start":
        start = max(0.0, min(start + amount, end - min_duration))
    elif action == "trim_end":
        end = max(start + min_duration, end + amount)
    elif action == "set_duration":
        end = start + max(min_duration, amount)
    elif action == "snap_start_previous" and index > 0:
        start = max(0.0, as_seconds(new_rows[index - 1].get("end"), start))
        if end <= start:
            end = start + min_duration
    elif action == "snap_end_next" and index + 1 < len(new_rows):
        next_start = as_seconds(new_rows[index + 1].get("start"), end)
        end = max(start + min_duration, next_start)

    row["start"] = round(start, 3)
    row["end"] = round(max(end, start + min_duration), 3)
    return new_rows
