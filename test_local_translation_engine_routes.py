from pathlib import Path

import local_translation_engine as engine


def test_local_translation_engine_has_no_libretranslate_route():
    source = Path("local_translation_engine.py").read_text(encoding="utf-8").lower()
    forbidden = "libre" + "translate"

    assert forbidden not in source
    assert "translate_with_" + forbidden not in source


def test_unsupported_self_hosted_provider_does_not_call_network():
    calls = []
    original_post = engine._post_json

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unsupported provider must not call network")

    try:
        engine._post_json = fake_post
        rows = engine.self_hosted_translate_batch(
            [{"location": "1", "source": "Hello"}],
            endpoint="https://mt.example.com/translate",
            provider="unsupported",
            target_language="French",
        )
    finally:
        engine._post_json = original_post

    assert calls == []
    assert rows == [{"location": "1", "translation": ""}]


if __name__ == "__main__":
    test_local_translation_engine_has_no_libretranslate_route()
    test_unsupported_self_hosted_provider_does_not_call_network()
    print("Local translation engine route tests passed.")
