import managed_ai_router as router


def test_extract_json_prefers_items_after_prose_braces():
    payload = router._extract_json_object(
        'Explanation with template braces {source} before the result.\n'
        'Result: {"items":[{"id":1,"issue":"ok"}]}'
    )

    assert payload["items"] == [{"id": 1, "issue": "ok"}]


def test_extract_json_skips_earlier_valid_non_items_object():
    payload = router._extract_json_object(
        'Diagnostic: {"note":"not the answer"}\n'
        'Final JSON: {"items":[{"id":2,"severity":"Major"}]}'
    )

    assert payload["items"] == [{"id": 2, "severity": "Major"}]


def test_extract_json_accepts_fenced_array():
    payload = router._extract_json_object(
        '```json\n[{"id":3,"ok":true}]\n```'
    )

    assert payload["items"] == [{"id": 3, "ok": True}]


if __name__ == "__main__":
    test_extract_json_prefers_items_after_prose_braces()
    test_extract_json_skips_earlier_valid_non_items_object()
    test_extract_json_accepts_fenced_array()
    print("AI JSON extraction tests passed.")
